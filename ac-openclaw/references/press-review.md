# Press Review — Daily News Digest (Optional Phase)

Ship-ready daily news digest delivered to the user's messaging channel every morning. Aggregates RSS feeds + Hacker News, dedupes against a 30-day cache, uses HTTP conditional GETs to save tokens, and asks the OpenClaw agent to synthesize a single merged digest (cross-source headlines, no per-source repetition).

**Why a "ready-to-use use-case":** a fresh OpenClaw install ends up feeling like a passthrough LLM until something *proactive* happens. The press review is the quickest proactive feature to demo — 1 script + 1 cron job = one-month-retention value.

This phase is OPTIONAL. Ask the user during install; skip if they say no. The whole thing installs in under a minute.

## What the user gets

- A Signal (or Telegram/Discord/...) message every morning at a chosen time.
- Format: **Top Stories** (2-3 items that multiple sources covered) + domain sections (AI, Web Dev & Python, Crypto, DevOps & Security, Industry, HN). Every bullet has clickable links.
- No duplication across sections. No repeat of items already sent in the last 30 days.

## When to offer it

During Phase 11 (Additional integrations), **after the user has**:

- A working messaging channel (Phase 8) — we need a delivery target.
- A configured agent — the cron job runs as a specific agent ID.

If either is missing, note it and move on. Do NOT install without a delivery channel.

## Install wizard (ask in order)

**1. Ask whether to install at all.**

```
OpenClaw can send you a daily "Press Review" — an aggregated tech/AI news digest
synthesised by the agent and delivered to your messaging channel. It's ~60 lines
of Python + 1 cron job, and it dedupes content across a 30-day window so you
never read the same headline twice.

Install it? (yes/no)
```

**2. Which agent should own the job?** List the agents found under `~/.openclaw/agents/` and ask. Default to the user's primary agent (the non-built-in one — skip `main`, `darwin`).

**3. Which channel + recipient?** Read from the agent's configuration if possible (e.g., `allowFrom.signal`). Confirm with the user; the recipient identifier must match what the channel expects:

| Channel  | Recipient format                                            |
|----------|-------------------------------------------------------------|
| Signal   | `uuid:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (agent's UUID)  |
| Telegram | numeric chat ID                                             |
| Discord  | user or channel snowflake ID                                |

**4. Schedule?** Default `0 8 * * *` (08:00 daily). Ask for timezone — default to the OS tz (`timedatectl show --value --property=Timezone`).

**5. Which sources?** Present the default pack. Let the user toggle:

```
Default sources (dedup across all, fetched in parallel):
  [x] TLDR AI          (daily)
  [x] TLDR Web Dev     (daily)
  [x] TLDR Crypto      (daily)
  [x] TLDR DevOps      (daily)
  [x] TLDR InfoSec     (daily)
  [x] Pragmatic Engineer  (weekly)
  [x] PyCoder's Weekly (weekly)
  [x] Django News      (weekly)
  [x] Real Python      (multiple/week)
  [x] PSF Blog         (sporadic)
  [x] Hacker News top stories (filtered for tech/AI)

Keep all, or remove some? (Enter to keep all)
```

For anything outside this default pack, ask for the RSS URL and a bucket label (`ai`, `webdev`, `crypto`, `devops`, `infosec`, `python`, `industry`).

**6. Which model?** Default `openrouter/openai/gpt-oss-120b` (cheap, strong synthesis). Offer the agent's default model if set.

## Installation steps

Assume `AGENT_ID`, `CHANNEL`, `RECIPIENT`, `SCHEDULE`, `TZ`, `MODEL` are collected from the wizard.

**Step 1 — install the runtime dep.** The script parses RSS/Atom with `defusedxml` (stdlib `xml.etree` is vulnerable to XML attacks). Install once on the target host:

```bash
ssh "$SSH_HOST" "python3 -m pip install --user defusedxml"
# OR, on Debian/Ubuntu:
ssh "$SSH_HOST" "sudo apt-get install -y python3-defusedxml"
```

**Step 2 — upload the script.** Copy `references/scripts/press-review.py` into the agent's workspace:

```bash
WORKSPACE="$HOME/.openclaw/workspace-${AGENT_ID}"
mkdir -p "$WORKSPACE/scripts" "$WORKSPACE/state"
scp references/scripts/press-review.py "$SSH_HOST:$WORKSPACE/scripts/press-review.py"
ssh "$SSH_HOST" "chmod 755 $WORKSPACE/scripts/press-review.py"
```

The script derives its state dir from its own location (`../state/`), so it works in any workspace.

**Step 3 — smoke-test the script over SSH:**

```bash
ssh "$SSH_HOST" "python3 $WORKSPACE/scripts/press-review.py | head -40"
```

Expect a `# Press Review Sources — <date>` header and at least 2-3 fetched sections. If everything is empty, check egress connectivity from the VPS.

**Step 4 — add the cron job.** Patch `~/.openclaw/cron/jobs.json` directly with `jq` — **never use the `openclaw cron add` CLI on the same VPS** (it cycles the gateway; see `troubleshooting-and-maintenance.md`).

```bash
NOW_MS=$(date +%s%N | cut -c1-13)
JOB_ID=$(uuidgen)

jq --arg id "$JOB_ID" \
   --arg agent "$AGENT_ID" \
   --arg expr "$SCHEDULE" \
   --arg tz "$TZ" \
   --arg msg "$(cat press-review-prompt.txt)" \
   --arg model "$MODEL" \
   --arg channel "$CHANNEL" \
   --arg to "$RECIPIENT" \
   --argjson now "$NOW_MS" '
  .jobs += [{
    id: $id, agentId: $agent, name: "press-review", enabled: true,
    createdAtMs: $now, updatedAtMs: $now,
    schedule: {kind: "cron", expr: $expr, tz: $tz},
    sessionTarget: "isolated", wakeMode: "now",
    payload: {kind: "agentTurn", message: $msg, model: $model, timeoutSeconds: 180},
    delivery: {mode: "none", channel: $channel, to: $to},
    state: {
      nextRunAtMs: $now, lastRunAtMs: null,
      lastRunStatus: null, lastStatus: null, lastDurationMs: null,
      lastDeliveryStatus: "not-requested",
      consecutiveErrors: 0, lastError: null
    }
  }]
' ~/.openclaw/cron/jobs.json > ~/.openclaw/cron/jobs.json.new \
  && python3 -c 'import json,sys; json.load(open("/tmp/j"))' < ~/.openclaw/cron/jobs.json.new \
  && mv ~/.openclaw/cron/jobs.json.new ~/.openclaw/cron/jobs.json
```

OpenClaw's cron loader watches `jobs.json` and picks up the new entry without a service restart (see `subsystem: "restart"` in the troubleshooting reference). Confirm by:

```bash
ssh "$SSH_HOST" 'systemctl show openclaw.service -p NRestarts --value'
# should NOT have incremented from the baseline
```

**Step 5 — tell the user how to trigger on-demand.** The cron fires daily at `SCHEDULE`, but they can also message `run press review` to their bot and it'll invoke the script + synthesise + reply. Add to `USER.md` or the agent's SOUL.md if appropriate.

## Prompt template (`press-review-prompt.txt`)

Write this verbatim to a file before the `jq` call above. Substitute `{RECIPIENT}` before uploading.

```
Fetch today's press review sources:

  python3 $WORKSPACE/scripts/press-review.py

The script already dedupes against items sent in the last 30 days and uses HTTP
conditional GETs — you only receive FRESH content. If a section is empty, it's
because nothing new was published since the last run.

Synthesise the fresh sources into ONE aggregated press review using this exact
structure. Do not add preamble, disclaimers, or trailing summaries — the output
is the final message.

## Press Review — {YYYY-MM-DD}

### Top Stories
Pick the 2-3 biggest stories across ALL sources. A story qualifies as "top" if
(a) two or more sources cover it, OR (b) it's a Hacker News top-20 item with
score > 300 and genuinely notable. Merge coverage into one bullet per story.
Include every link that reports it.

- **{headline}** — {2-3 sentence synthesis drawing from all covering sources}.
  Sources: [TLDR AI]({url}) · [HN]({url}) · [Pragmatic]({url})

### AI
Short bullets on AI/ML news. Every item has a clickable link. No duplicates
with Top Stories.

- {short headline, <12 words} — [{source}]({url})

### Web Dev & Python
Same format. Merge TLDR Web Dev, PyCoder's, Django News, Real Python, PSF.

### Crypto
Same format.

### DevOps & Security
Same format. Merge TLDR DevOps + TLDR InfoSec.

### Industry & Trends
Pragmatic Engineer content and any broader industry/business stories.

### Trending on Hacker News
Only HN items that did NOT land in Top Stories and aren't already covered by
a newsletter above. Include score.

- {headline} (score: N) — [discuss]({hn_url})

Rules:
1. Every bullet MUST contain at least one clickable markdown link.
2. Never repeat a story across sections. If it's in Top Stories, skip elsewhere.
3. Merge near-duplicate headlines from different sources into ONE bullet with
   multiple links.
4. Omit any section entirely if it has no fresh content.
5. Keep individual headlines under 12 words. Prefer paraphrasing over quoting.
6. Skip filler: sponsored items, "job of the week", generic round-ups,
   promotional content.
7. Output only the markdown press review — no "Here's your briefing" intro,
   no sign-off.

After generating, send the message via {CHANNEL} to {RECIPIENT}.
```

Replace `{CHANNEL}` and `{RECIPIENT}` with the wizard's values.

## Customisation after install

- **Change sources** — edit the `SOURCES` list at the top of `press-review.py`. Each entry is `(bucket, label, rss_url, max_items)`.
- **Change schedule** — patch `jobs.json` `schedule.expr` + `schedule.tz`. Gateway picks it up automatically.
- **Change format** — edit the prompt stored in `jobs.json` `payload.message`. Pure prose, no restart needed.
- **Reset dedup cache** — `rm ~/.openclaw/workspace-<agent>/state/press-review-seen.json` (next run will re-fetch everything; use when sources change dramatically).
- **Force 304 cache invalidation** — `rm ~/.openclaw/workspace-<agent>/state/press-review-feeds.json`.

## What to NOT do

- **Don't** use `openclaw cron add` / `openclaw cron list` on the same VPS as the running gateway — it SIGTERMs the service every call (see `troubleshooting-and-maintenance.md` § Common Mistakes row "Running `openclaw` CLI on VPS").
- **Don't** put API keys or secrets into the cron payload — the prompt is agent-visible, but any tokens belong in `pass` and are injected via the gateway wrapper, never inline.
- **Don't** hard-code absolute paths in the script. The canonical script uses `Path(__file__).resolve().parent.parent / "state"` so it works for any agent workspace.
- **Don't** set `delivery.mode` to anything other than `none` unless you've verified the gateway's current delivery driver behaviour for that channel. The agent calling the send tool is the portable path.

## Verification after install

1. Run the script manually once: `ssh $SSH_HOST "python3 $WORKSPACE/scripts/press-review.py | wc -l"` — expect 300+ lines on first run.
2. Check the cron was picked up: `ssh $SSH_HOST "jq '.jobs[] | select(.name == \"press-review\") | .enabled'" ~/.openclaw/cron/jobs.json` — expect `true`.
3. Confirm the gateway didn't restart: `systemctl show openclaw.service -p NRestarts --value` — unchanged vs. baseline.
4. Ask the user to test end-to-end by messaging `run press review` to the bot. If that succeeds, the daily cron will work too.

## Operational notes

- First run has an empty dedup cache, so the resulting digest is larger than subsequent ones. Warn the user.
- The script keeps state under `<workspace>/state/`. Back that up along with the rest of the agent workspace.
- If a feed breaks (moved/removed RSS URL), the script logs a warning to stderr and continues with the other sources — a failing feed never blocks the digest.
