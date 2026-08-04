#!/usr/bin/env python3
"""press-review-watchdog.py — same-day delivery watchdog for the OpenClaw press review.

Runs once daily AFTER the press-review cron is due. Verifies the press review
actually DELIVERED today by reading OpenClaw's own cron store (the consolidated
state sqlite, with a fallback to the legacy jobs.json), and ALSO checks for the
specific failure CLASS that silently broke delivery on 2026-06-04: the gateway
auto-updated on disk and migrated the cron store, but the running process was
never restarted, so the in-memory scheduler lost its store and stopped firing.

On any miss it alerts the user over the SAME channel the press review uses
(signal-cli JSON-RPC), so a silent failure surfaces the same day, not days later.

Dependency-free: Python stdlib only. No openclaw CLI is invoked (the CLI cycles
the running gateway on this host). State reads are read-only.

Exit codes: 0 = delivered today (healthy); 0 also on alert-sent (a miss is not a
crash — we want the timer to stay green and just notify). Non-zero only on the
watchdog's own internal error.
"""

import json
import os
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

HOME = Path(os.environ.get("HOME", "/home/openclaw"))
OPENCLAW_DIR = HOME / ".openclaw"
STATE_DB = OPENCLAW_DIR / "state" / "openclaw.sqlite"
LEGACY_JOBS = OPENCLAW_DIR / "cron" / "jobs.json"
PACKAGE_JSON = HOME / ".npm-global" / "lib" / "node_modules" / "openclaw" / "package.json"

JOB_NAME = "press-review"
RPC_URL = "http://127.0.0.1:8080/api/v1/rpc"  # NO trailing slash (trailing slash 404s)
SERVICE = "openclaw.service"

# Recipient for the alert = the same target the press-review cron delivers to.
# Resolved at runtime from the cron job's delivery_to; this constant is only the
# last-resort fallback. Set it to the user's own Signal UUID at install time
# (bare UUID, no "uuid:" prefix). Placeholder below — replace before deploy.
FALLBACK_RECIPIENT = "00000000-0000-0000-0000-000000000000"

# One alert per day: marker keyed by date so a 30-min-ish retry never spams.
# ~/.local is often root-owned on these hosts; keep state + log under the
# openclaw-owned ~/.openclaw tree. File logging degrades gracefully (journald
# still captures stderr via the systemd unit) if the dir is ever unwritable.
MARKER_DIR = OPENCLAW_DIR / "state"
LOG = OPENCLAW_DIR / "logs" / "press-review-watchdog.log"


def now_local() -> datetime:
    return datetime.now().astimezone()


def today_str() -> str:
    return now_local().date().isoformat()


def log(msg: str) -> None:
    line = f"{now_local().isoformat()} {msg}"
    print(line, file=sys.stderr)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def strip_uuid_prefix(target: str) -> str:
    """signal-cli raw JSON-RPC wants a bare UUID / E.164, not OpenClaw's 'uuid:' form."""
    if target.startswith("uuid:"):
        return target[len("uuid:") :]
    return target


# ---------------------------------------------------------------------------
# Read the press-review job state from the cron store
# ---------------------------------------------------------------------------


def read_job_from_sqlite() -> dict | None:
    if not STATE_DB.exists():
        return None
    try:
        uri = f"file:{STATE_DB}?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=8)
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT name, enabled, last_run_at_ms, last_run_status, "
            "last_delivery_status, last_delivered, delivery_to, next_run_at_ms "
            "FROM cron_jobs WHERE name = ?",
            (JOB_NAME,),
        )
        row = cur.fetchone()
        con.close()
    except sqlite3.Error as exc:
        log(f"WARN sqlite read failed: {exc}")
        return None
    if row is None:
        return None
    return dict(row)


def read_job_from_legacy_json() -> dict | None:
    if not LEGACY_JOBS.exists():
        return None
    try:
        data = json.loads(LEGACY_JOBS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log(f"WARN legacy jobs.json read failed: {exc}")
        return None
    for job in data.get("jobs", []):
        if job.get("name") == JOB_NAME:
            st = job.get("state", {})
            return {
                "name": JOB_NAME,
                "enabled": 1 if job.get("enabled") else 0,
                "last_run_at_ms": st.get("lastRunAtMs"),
                "last_run_status": st.get("lastRunStatus") or st.get("lastStatus"),
                "last_delivery_status": st.get("lastDeliveryStatus"),
                "last_delivered": 1 if st.get("lastDelivered") else 0,
                "delivery_to": (job.get("delivery") or {}).get("to"),
                "next_run_at_ms": st.get("nextRunAtMs"),
            }
    return None


def read_job() -> tuple[dict | None, str]:
    job = read_job_from_sqlite()
    if job is not None:
        return job, "sqlite"
    job = read_job_from_legacy_json()
    if job is not None:
        return job, "legacy-json"
    return None, "none"


# ---------------------------------------------------------------------------
# Failure-CLASS detection: disk version newer than the running process
# ---------------------------------------------------------------------------


def disk_version() -> str | None:
    try:
        return json.loads(PACKAGE_JSON.read_text(encoding="utf-8")).get("version")
    except (json.JSONDecodeError, OSError):
        return None


def gateway_start_epoch() -> int | None:
    """Start time of the running gateway process, in epoch seconds.

    Deterministic: ask systemd for the MainPID, read its start time from
    /proc/<pid> (ctime of the proc dir == process start). No log scraping.
    """
    try:
        pid = subprocess.run(
            ["systemctl", "show", SERVICE, "-p", "MainPID", "--value"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None
    if not pid or pid == "0":
        return None
    try:
        return int(Path(f"/proc/{pid}").stat().st_ctime)
    except OSError:
        return None


def code_mtime_epoch() -> int | None:
    """Newest mtime across the on-disk entrypoint + package manifest."""
    newest = None
    for p in (PACKAGE_JSON, PACKAGE_JSON.parent / "dist" / "index.js"):
        try:
            m = int(p.stat().st_mtime)
        except OSError:
            continue
        newest = m if newest is None else max(newest, m)
    return newest


def version_mismatch_alert() -> str | None:
    """Detect 'auto-update landed on disk but the process was not restarted'.

    Signal: on-disk code mtime NEWER than the running process start time.
    That is exactly the 2026-06-04 failure class — the running scheduler keeps
    a stale view of the (now-migrated) cron store and silently stops firing.
    A small slack avoids flagging an update that happened during this very run.
    """
    started = gateway_start_epoch()
    code_m = code_mtime_epoch()
    if started is None or code_m is None:
        return None
    slack_seconds = 120
    if code_m > started + slack_seconds:
        disk = disk_version() or "?"
        return (
            f"gateway code on disk (v{disk}) was updated AFTER the running process "
            f"started — an auto-update landed without a process restart. This is the "
            f"failure class that silently broke the 2026-06-04 brief (the migrated "
            f"cron store is invisible to the stale process). Fix: "
            f"`sudo systemctl restart {SERVICE}`."
        )
    return None


# ---------------------------------------------------------------------------
# Delivery verdict
# ---------------------------------------------------------------------------


def ms_to_local_date(ms: int | str | None) -> str | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, UTC).astimezone().date().isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def delivered_today(job: dict) -> bool:
    last_date = ms_to_local_date(job.get("last_run_at_ms"))
    delivered = bool(job.get("last_delivered")) or job.get("last_delivery_status") == "delivered"
    status_ok = job.get("last_run_status") == "ok"
    return last_date == today_str() and delivered and status_ok


# ---------------------------------------------------------------------------
# Alerting via signal-cli JSON-RPC (same channel as the press review)
# ---------------------------------------------------------------------------


def send_alert(recipient: str, message: str) -> bool:
    payload = {
        "jsonrpc": "2.0",
        "method": "send",
        "id": 1,
        "params": {"recipient": [strip_uuid_prefix(recipient)], "message": message},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        log(f"ERROR alert send failed: {exc}")
        return False
    results = (body.get("result") or {}).get("results") or []
    ok = any(r.get("type") == "SUCCESS" for r in results)
    if not ok:
        log(f"ERROR alert send non-success: {json.dumps(body)[:300]}")
    return ok


def already_alerted_today() -> bool:
    marker = MARKER_DIR / f"press-review-watchdog-alerted-{today_str()}.marker"
    return marker.exists()


def mark_alerted_today() -> None:
    try:
        MARKER_DIR.mkdir(parents=True, exist_ok=True)
        (MARKER_DIR / f"press-review-watchdog-alerted-{today_str()}.marker").write_text(
            now_local().isoformat(), encoding="utf-8"
        )
    except OSError as exc:
        log(f"WARN could not write alert marker: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    job, source = read_job()

    problems: list[str] = []

    if job is None:
        problems.append(
            "press-review cron job NOT FOUND in any store (sqlite or legacy jobs.json). "
            "The job may have been dropped by a migration."
        )
    else:
        if not job.get("enabled"):
            problems.append("press-review cron job is DISABLED.")
        if not delivered_today(job):
            last_date = ms_to_local_date(job.get("last_run_at_ms")) or "never"
            problems.append(
                f"press-review did NOT deliver today ({today_str()}). "
                f"last_run={last_date} status={job.get('last_run_status')} "
                f"delivery={job.get('last_delivery_status')} (store={source})."
            )

    vmis = version_mismatch_alert()
    if vmis:
        problems.append(vmis)

    if not problems:
        log(f"OK press review delivered today ({today_str()}); store={source}.")
        return 0

    if already_alerted_today():
        log("MISS but already alerted today; not re-sending. Problems: " + " | ".join(problems))
        return 0

    recipient = (job or {}).get("delivery_to") or FALLBACK_RECIPIENT
    header = f"⚠️ OpenClaw press-review watchdog — {today_str()}\n\n"
    msg = header + "\n".join(f"- {p}" for p in problems)
    msg += (
        "\n\nLikely fix: `sudo systemctl restart openclaw.service` (then the cron "
        "fires on its next schedule). This alert is sent once per day."
    )

    if send_alert(recipient, msg):
        log("ALERT sent. Problems: " + " | ".join(problems))
        mark_alerted_today()
    else:
        log("ALERT SEND FAILED. Problems: " + " | ".join(problems))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
