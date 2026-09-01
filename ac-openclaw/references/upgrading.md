# Upgrading an existing OpenClaw instance

Covers upgrading a running box in place to `2026.8.1`.

Order: **pre-flight → upgrade → config migration → verification → rollback**. Each blocker has a
symptom → cause → fix entry in
[`troubleshooting-and-maintenance.md`](troubleshooting-and-maintenance.md) § "Upgrade blockers";
this file is the order to hit them in.

---

## 1. Pre-flight

### 1.1 Capture the rollback target

The current version string is what you reinstall if the upgrade goes wrong. Capture it, plus the
runtime it was working against, **before** touching anything:

```bash
node -v
npm -v
npm ls -g --depth=0                                  # records the exact openclaw version
systemctl cat openclaw.service                       # the unit, incl. any hard-coded paths
openclaw --version
```

Keep the output. `npm ls -g --depth=0` is the rollback target — a version you remember is not one.

### 1.2 Stop the service first

The state store is WAL-mode SQLite and sessions are append-only JSONL. Both are mid-write while
the gateway runs, so a backup taken against a live box captures a torn state:

```bash
sudo systemctl stop openclaw.service
```

### 1.3 Back up

```bash
tar --zstd -cf ~/backups/openclaw-pre-upgrade-$(date +%Y-%m-%d).tar.zst \
  ~/.openclaw \
  ~/.local/share/signal-cli \
  ~/.npmrc \
  /etc/systemd/system/openclaw.service /etc/systemd/system/openclaw.service.d 2>/dev/null
```

### 1.4 Verify the backup by RESTORING from it, not by listing it

`tar -tf` proves the archive has a table of contents. It does not prove the bytes are readable or
that the SQLite files inside are intact. Restore into a scratch dir and check:

```bash
BK=~/backups/openclaw-pre-upgrade-$(date +%Y-%m-%d).tar.zst
SCRATCH=$(mktemp -d)

zstd -t "$BK"                                        # decompresses end to end
tar --zstd -tf "$BK" | wc -l                         # entry count
tar --zstd -tf "$BK" | grep -c 'agents/'             # control: a count you can predict

tar --zstd -xf "$BK" -C "$SCRATCH"
diff <(jq -S . "$SCRATCH"/home/*/.openclaw/openclaw.json) <(jq -S . ~/.openclaw/openclaw.json)

find "$SCRATCH" -name '*.sqlite' -exec sh -c \
  'echo "== $1"; sqlite3 "$1" "PRAGMA integrity_check;"' _ {} \;
```

The `grep -c 'agents/'` line is the control: a count you can predict in advance distinguishes "the
archive is fine" from "my listing command is broken". A verification with no control returns a
clean-looking result either way.

> **macOS `sqlite3` does not accept `file:...?mode=ro` URI syntax.** Passing a URI there fails with
> `unable to open database file (14)` — which reads exactly like a corrupt database and sends you
> looking for a problem you do not have. Use a plain path.

### 1.5 If the box has its own backup job, confirm it RAN

A configured backup job is not a backup. A script that exits before its `tar` step — a failed
`mkdir`, an unset variable under `set -u`, a stopped service it waits on — leaves nothing behind
while still looking configured in cron:

```bash
ls -lt ~/backups | head                              # is the newest archive recent?
```

An empty or stale directory means the job has not produced a restorable artifact, whatever
`crontab -l` says.

---

## 2. Upgrade

```bash
npm i -g openclaw@2026.8.1 --allow-scripts=openclaw   # npm >= 11.16
npm i -g openclaw@2026.8.1                            # npm <= 11.15 — the flag does not exist
```

Without `--allow-scripts=openclaw` on npm >= 11.16 the bundled plugins are silently skipped — the
install succeeds and the plugins are simply absent.

`preinstall` aborts if Node is outside `>=22.22.3 <23 || >=24.15.0 <25 || >=25.9.0`. Upgrade Node
first if it refuses.

**Re-check any path the systemd unit hard-codes.** A unit pointing at
`.../node_modules/openclaw/dist/index.js` breaks silently when the entry point moves between
releases:

```bash
systemctl cat openclaw.service | grep -E 'ExecStart|dist/'
ls -l "$(npm root -g)/openclaw/dist/index.js"
```

Do not start the service yet.

---

## 3. Config migration

```bash
openclaw doctor --lint          # what 2.0 rejects in the existing config
openclaw doctor --fix           # migrate what it can
```

Config validation is **fail-closed**, and `doctor --fix` cannot self-heal a config it cannot load —
it will tell you to run the command you just ran. When that happens, hand-migrate the specific
rejected keys with `jq`, then re-run `doctor --fix` for the rest. The loop, the retired keys, the
Signal plugin deadlock, and the OpenRouter/perplexity blocker are all in
[`troubleshooting-and-maintenance.md`](troubleshooting-and-maintenance.md) § "Upgrade blockers".

The service is already stopped from § 1.2 — **keep it stopped**. `doctor --fix` refuses to run
while the gateway is up (`OpenClaw refused shared state schema mutation ... another Gateway owns
that state directory`), and it aborts on the *first* blocker it cannot migrate, so clearing one
only reveals the next. Re-run the `doctor --fix` above until it **exits 0** — a non-zero exit means
nothing was persisted, however much it printed.

Blockers seen after a real upgrade, beyond the retired-key table: `agents.list` (rewrite as keyed
`agents.entries` + `agents.ownership: "explicit"`), `gateway.controlUi.dangerouslyDisableDeviceAuth`
(drop), and a legacy `exec-approvals.json` (copy it aside, archive it, fix, then restore the policy
you copied). **Read the caveats there before acting on either**: `ownership: "explicit"` makes
channels, heartbeat, cron and bare CLI calls fail closed unless a binding resolves an owner, and
archiving `exec-approvals.json` leaves no exec-approval policy in force until you restore it. Full
procedure in
[`troubleshooting-and-maintenance.md`](troubleshooting-and-maintenance.md)
§ "After an upgrade, `doctor --fix` deadlocks on a CHAIN of legacy keys".

**A clean `doctor --lint` (or `openclaw config validate`) is not proof the upgrade landed.** Workspace setup state migrates
separately, and while it is pending *every agent turn fails* with `Legacy workspace setup state
requires migration` while the service still reports `active (running)` and the channel reports OK.
Always finish by running one real agent turn.

Work through them until `openclaw doctor --lint` is clean, then:

```bash
sudo systemctl restart openclaw.service
```

---

## 4. Verification

`systemctl is-active` returns `active` for an entire crash loop, because `Restart=always` keeps
restarting the process. It is not evidence. Verify three things:

```bash
systemctl show openclaw.service -p NRestarts         # stable, not climbing
ss -ltnp | grep 18789                                # a listener actually exists
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18789/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:1     # control: must be 000
```

Sample `NRestarts` twice a minute apart — one reading cannot show a trend. The unused-port probe is
the control: without it, a `curl` that returns `000` for every port on the box looks the same as a
dead gateway.

Then exercise the paths that only break end to end:

- send the assistant an inbound message and confirm it replies (the outbound path can work while
  inbound is dead — see the signal-cli version floor in
  [`channel-setup.md`](channel-setup.md))
- run one cron job and read its outcome from the run records, not the CLI's return

---

## 5. Rollback

In place, while the legacy session store still exists:

```bash
sudo systemctl stop openclaw.service
npm i -g openclaw@<version-from-step-1.1> --allow-scripts=openclaw
sudo systemctl start openclaw.service
```

If config was migrated past the point where the old version accepts it, restore `~/.openclaw` from
the pre-upgrade archive first.

> **Never run `openclaw update cleanup` until end-to-end verification passes.** It destroys the
> legacy transcripts, and with them the in-place rollback path.
