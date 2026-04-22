#!/usr/bin/env python3
"""press-review.py — Aggregated tech/AI press review for OpenClaw.

Fetches RSS + Hacker News, dedupes against local cache (URL-normalised),
uses HTTP conditional GETs (ETag / Last-Modified) to skip unchanged feeds,
and outputs markdown-ready source data for the `press-review` cron agent
to synthesise into a single aggregated digest.

State files (all under <workspace>/state/):

    press-review-seen.json
        {"<normalised_url>": "<iso_date>", ...}
        URLs already surfaced in a previous run.
        Entries older than RETENTION_DAYS pruned.

    press-review-feeds.json
        {"<feed_url>": {"etag": "...", "last_modified": "...", "fetched_at": "..."}}
        Per-feed conditional-GET headers.

Called by the `press-review` cron job (daily at a chosen time) and
on-demand via messaging ("run press review").

Requires: `defusedxml` (stdlib's `xml.etree` is vulnerable to XML attacks).
Install with:  pip install defusedxml   (or `apt install python3-defusedxml`)
"""

import json
import operator
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from defusedxml import ElementTree

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LOCAL_NOW = datetime.now().astimezone()
TODAY = LOCAL_NOW.date()
UA = "Mozilla/5.0 (compatible; OpenClaw-PressReview/1.0; +https://openclaw.ai)"
TIMEOUT = 12
RETENTION_DAYS = 30
HTTP_NOT_MODIFIED = 304
ALLOWED_SCHEMES = ("http", "https")

STATE_DIR = Path(__file__).resolve().parent.parent / "state"
SEEN_PATH = STATE_DIR / "press-review-seen.json"
FEEDS_PATH = STATE_DIR / "press-review-feeds.json"

STATE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def prune_seen(seen: dict) -> dict:
    cutoff = (TODAY - timedelta(days=RETENTION_DAYS)).isoformat()
    return {url: d for url, d in seen.items() if d >= cutoff}


# ---------------------------------------------------------------------------
# URL normalisation
# ---------------------------------------------------------------------------

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "ref_src",
    "ref_url",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "source",
    "share",
    "__twitter_impression",
}


def normalise_url(url: str) -> str:
    """Strip tracking params, fragments, trailing slashes; lowercase scheme+host."""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return url
    if not p.netloc:
        return url
    query_items = [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in TRACKING_PARAMS]
    path = p.path.rstrip("/") or "/"
    return urlunparse(
        (
            p.scheme.lower(),
            p.netloc.lower(),
            path,
            "",
            urlencode(query_items),
            "",
        )
    )


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _safe_request(url: str, headers: dict) -> Request | None:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        print(f"  [warn] refusing non-HTTP(S) URL: {url}", file=sys.stderr)
        return None
    return Request(url, headers=headers)  # noqa: S310 — scheme pre-validated above


def fetch(url: str, headers: dict | None = None) -> tuple[str | None, dict]:
    """Return (body, response_headers). body is None on 304 or error."""
    req_headers = {"User-Agent": UA}
    if headers:
        req_headers.update(headers)
    req = _safe_request(url, req_headers)
    if req is None:
        return None, {}
    try:
        with urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 — scheme pre-validated
            body = r.read().decode("utf-8", errors="replace")
            resp_hdrs = dict(r.headers.items())
            return body, resp_hdrs
    except HTTPError as e:
        if e.code == HTTP_NOT_MODIFIED:
            return None, {"_status": str(HTTP_NOT_MODIFIED)}
        print(f"  [warn] HTTP {e.code} — {url}", file=sys.stderr)
    except (URLError, TimeoutError, OSError) as e:
        print(f"  [warn] {e.__class__.__name__}: {url}", file=sys.stderr)
    return None, {}


def fetch_feed(url: str, feeds_state: dict) -> str | None:
    """Fetch with conditional GET. Updates feeds_state in place. Returns body or None."""
    prior = feeds_state.get(url, {})
    headers = {}
    if prior.get("etag"):
        headers["If-None-Match"] = prior["etag"]
    if prior.get("last_modified"):
        headers["If-Modified-Since"] = prior["last_modified"]

    body, resp = fetch(url, headers=headers)
    if resp.get("_status") == str(HTTP_NOT_MODIFIED):
        print(f"  [cache] 304 — {url}", file=sys.stderr)
        return None
    if body is None:
        return None

    feeds_state[url] = {
        "etag": resp.get("ETag") or resp.get("etag"),
        "last_modified": resp.get("Last-Modified") or resp.get("last-modified"),
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    return body


# ---------------------------------------------------------------------------
# RSS / Atom parsing (via defusedxml — safe against XML attacks)
# ---------------------------------------------------------------------------


def parse_feed(raw: str, max_items: int = 15) -> list[dict]:
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[dict] = []

    for item in root.findall(".//item"):  # RSS 2.0
        t = (item.findtext("title") or "").strip()
        u = (item.findtext("link") or "").strip()
        d = (item.findtext("description") or "").strip()[:300]
        if t and u:
            items.append({"title": t, "url": u, "desc": d})

    if not items:  # Atom fallback
        for entry in root.findall(".//atom:entry", ns):
            t = (entry.findtext("atom:title", "", ns) or "").strip()
            lel = entry.find("atom:link", ns)
            u = lel.get("href", "") if lel is not None else ""
            d = (entry.findtext("atom:summary", "", ns) or "").strip()[:300]
            if t and u:
                items.append({"title": t, "url": u, "desc": d})

    return items[:max_items]


# ---------------------------------------------------------------------------
# Hacker News
# ---------------------------------------------------------------------------

HN_KEYWORDS = {
    "ai",
    "llm",
    "gpt",
    "claude",
    "gemini",
    "mistral",
    "openai",
    "anthropic",
    "ml",
    "model",
    "agent",
    "python",
    "django",
    "rust",
    "go ",
    "javascript",
    "typescript",
    "devops",
    "docker",
    "kubernetes",
    "wasm",
    "web",
    "open source",
    "github",
    "security",
    "crypto",
    "blockchain",
    "programming",
    "software",
    "startup",
    "database",
    "cloud",
    "linux",
    "vim",
    "neovim",
}


def fetch_hn(limit: int = 25) -> list[dict]:
    raw, _ = fetch("https://hacker-news.firebaseio.com/v0/beststories.json")
    if not raw:
        return []
    try:
        ids = json.loads(raw)[:80]
    except json.JSONDecodeError:
        return []
    stories: list[dict] = []
    for sid in ids:
        body, _ = fetch(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
        if not body:
            continue
        try:
            item = json.loads(body)
        except json.JSONDecodeError:
            continue
        title = (item.get("title") or "").strip()
        if any(k in title.lower() for k in HN_KEYWORDS):
            stories.append(
                {
                    "title": title,
                    "url": item.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                    "score": item.get("score", 0),
                    "hn_url": f"https://news.ycombinator.com/item?id={sid}",
                }
            )
        if len(stories) >= limit:
            break
    return sorted(stories, key=operator.itemgetter("score"), reverse=True)


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


def dedupe(items: list[dict], seen: dict, today_iso: str) -> list[dict]:
    """Drop items whose normalised URL is in seen. Mark kept items as seen."""
    fresh = []
    for it in items:
        norm = normalise_url(it["url"])
        if norm in seen:
            continue
        it["_norm_url"] = norm
        fresh.append(it)
        seen[norm] = today_iso
    return fresh


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def print_section(title: str, items: list[dict]) -> None:
    print(f"\n{'=' * 60}")
    print(f"## {title}")
    print(f"{'=' * 60}")
    if not items:
        print("(no fresh items — either nothing new or source unavailable)")
        return
    for i, it in enumerate(items, 1):
        print(f"\n{i}. {it['title']}")
        if it.get("url"):
            print(f"   {it['url']}")
        if it.get("desc"):
            print(f"   {it['desc'][:250]}")
        if it.get("score"):
            print(f"   [HN score: {it['score']}]  {it.get('hn_url', '')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SOURCES = [
    ("ai", "TLDR AI", "https://tldr.tech/api/rss/ai", 15),
    ("webdev", "TLDR Web Dev", "https://tldr.tech/api/rss/webdev", 15),
    ("crypto", "TLDR Crypto", "https://tldr.tech/api/rss/crypto", 10),
    ("devops", "TLDR DevOps", "https://tldr.tech/api/rss/devops", 10),
    ("infosec", "TLDR InfoSec", "https://tldr.tech/api/rss/infosec", 10),
    ("industry", "Pragmatic Engineer", "https://newsletter.pragmaticengineer.com/feed", 6),
    ("python", "PyCoder's Weekly", "https://pycoders.com/feed", 8),
    ("python", "Django News", "https://django-news.com/issues.rss", 6),
    ("python", "Real Python", "https://realpython.com/atom.xml", 5),
    ("python", "PSF Blog", "https://blog.python.org/feeds/posts/default", 4),
]


def main() -> None:
    today_iso = TODAY.isoformat()
    seen = prune_seen(load_json(SEEN_PATH))
    feeds_state = load_json(FEEDS_PATH)

    print(f"# Press Review Sources — {today_iso}")
    print(f"# Generated: {datetime.now(UTC).isoformat()}")
    print(f"# Cache: {len(seen)} URLs previously seen (retention {RETENTION_DAYS}d)\n")

    buckets: dict[str, list[tuple[str, list[dict]]]] = {}
    stats: list[str] = []

    for bucket, label, url, limit in SOURCES:
        raw = fetch_feed(url, feeds_state)
        if raw is None:
            stats.append(f"{label}: cached/304/error")
            continue
        parsed = parse_feed(raw, max_items=limit)
        fresh = dedupe(parsed, seen, today_iso)
        buckets.setdefault(bucket, []).append((label, fresh))
        stats.append(f"{label}: {len(parsed)} fetched, {len(fresh)} fresh")

    hn = fetch_hn(25)
    hn_fresh = dedupe(hn, seen, today_iso)
    stats.append(f"Hacker News: {len(hn)} fetched, {len(hn_fresh)} fresh")

    for s in stats:
        print(f"  {s}", file=sys.stderr)

    for bucket in ("ai", "webdev", "crypto", "devops", "infosec", "python", "industry"):
        for label, items in buckets.get(bucket, []):
            print_section(label, items)

    print_section("Hacker News — top tech/AI stories", hn_fresh)

    print(f"\n{'=' * 60}")
    print("# End of fresh sources.")
    print(f"{'=' * 60}")

    save_json(SEEN_PATH, seen)
    save_json(FEEDS_PATH, feeds_state)


if __name__ == "__main__":
    main()
