# OpenClaw Reference — read when troubleshooting or verifying installation

## Common Mistakes

| Mistake | Why it's bad | Do this instead |
|---------|-------------|-----------------|
| Binding gateway to `0.0.0.0` | Exposes OpenClaw to the internet without auth | Bind to `loopback`, use Tailscale Serve |
| Publishing Docker ports directly | Docker bypasses UFW — ports are public | Bind to `127.0.0.1`, add DOCKER-USER iptables rules |
| Using personal phone for Signal bot | Registering can de-auth your main Signal app | Get a dedicated SIM/number for the bot |
| Storing API keys in config files | Plaintext secrets on disk | Use `pass` or env vars sourced from encrypted store |
| Skipping `openclaw security audit` | Misconfigurations go unnoticed | Run `openclaw security audit --deep` after every config change |
| Running OpenClaw as root | Unnecessary privilege escalation | Create dedicated `openclaw` user |
| Asking all questions at once | Overwhelms the user | Ask ONE question, wait for answer, proceed |
| Not refreshing research before starting | OpenClaw evolves rapidly; cached data may be stale | Web search for latest version + breaking changes first |
| Running `curl \| bash` without verifying the script | Remote scripts can change between visits — supply chain risk | Download first (`curl -fsSL url -o install.sh`), inspect, then run. Reference files use vendor install commands for convenience but the agent should prefer download-then-inspect when practical |
| Skipping tool-use question | Security recommendation (Docker sandboxing) depends on whether user plans to use tools. Assuming chat-only leads to wrong advice | Always ask § 1.5 before security preferences |
| Moving on without confirming specific local model | User chose "BYOK + Ollama" but doesn't know which model will be installed | Explicitly confirm the model (e.g., "Qwen 3 4B on 4 GB — OK?") before proceeding |
| Generating a new SSH key without checking existing ones | User already has keys locally and/or registered with the provider | List `~/.ssh/*.pub` + provider keys first, ask which to use |
| Guessing API permission names instead of researching | Provider UIs change frequently; guessed names confuse the user | Web-search for the current UI or ask the user for a screenshot. The skill includes a snapshot but warns it may be stale |
| Not recommending dedicated account + restricted key + budget limit | Personal API key with full permissions is a security and billing risk | Always guide: dedicated account → service account → restricted permissions → budget limit |
| Not warning about Signal dedicated phone number during channel selection | User discovers too late (Phase 8) that they need a separate SIM | Warn in Phase 1.6 channel selection, not just Phase 8 |
| Not storing generated secrets in `pass` immediately | User can't retrieve the token later; secret only exists on the server | Every secret generated during setup (gateway token, API keys) goes into `pass` on the user's machine immediately |
| Not setting `gateway.mode` before starting gateway | Gateway refuses to start with "gateway start blocked: set gateway.mode" | Set `gateway.mode local` in Phase 5.3, before the systemd service is created |
| Not configuring `allowedOrigins` before user opens dashboard | User gets "origin not allowed" error | Configure `allowedOrigins` with the Tailscale/Cloudflare/Caddy hostname in Phase 5.3 |
| Not explaining device pairing before user hits "pairing required" | User sees cryptic error, doesn't know what to do | Warn the user before they open the dashboard, then approve the device with `openclaw devices approve` |
| Not fetching OpenClaw docs before starting installation | Agent guesses configs and commands, hits errors repeatedly | Fetch docs at the start of the install (Phase 5), not midway through debugging |
| Installing BOTH a user-level `~/.config/systemd/user/openclaw-gateway.service` AND a system-level `/etc/systemd/system/openclaw.service` | They race for port 18789 on every restart, each one killing the other ("killing N stale gateway process(es) before restart"). Looks like the gateway "breaks constantly." | Pick ONE install method from the start. If both are already present, disable the one you don't want (`systemctl --user disable --now openclaw-gateway.service` + rename the unit file), then `systemctl daemon-reload`. |
| Putting API keys in `Environment=` lines of a systemd unit file | Unit files are mode 664 by default — every logged-in user on the host can read them | Use `EnvironmentFile=` pointing at a `chmod 600` env file, OR a startup wrapper that reads from `pass` (the user's existing `~/.openclaw/start-gateway.sh` pattern). Rotate any key that was ever in a world/group-readable unit file. |
| Running `openclaw` CLI commands on the same host as a running `openclaw.service` | In v2026.4.x, `openclaw cron list`/`doctor`/etc. detect the running gateway PID and SIGTERM it before trying to start their own in-process gateway, which then fails to resolve `OPENCLAW_GATEWAY_TOKEN` (not in interactive shells) and exits. Systemd restarts the real service, signal-cli dies for 20-30 s. Every CLI call causes a messaging outage. | Edit `~/.openclaw/cron/jobs.json` directly for cron tweaks, call signal-cli JSON-RPC at `http://127.0.0.1:8080/api/v1/rpc` (no trailing slash) for sends/probes, and use the Tailscale-served dashboard for everything else. If you must use the CLI, do it from a different machine against a remote gateway. |
| Auto-update landed new code but gateway still errors `ERR_MODULE_NOT_FOUND` | OpenClaw's npm auto-update replaces files on disk but the running Node.js process still references old content-hashed chunk filenames that aren't in the new tarball. Every outbound send throws. | Restart the service: `sudo systemctl restart openclaw.service`. Disk and package.json will show the newer version; `start-gateway.sh` loads the new `dist/index.js` on startup. Consider enabling an auto-restart-after-update hook if OpenClaw doesn't ship one. |
| Leaving `thinkingDefault` unset when the primary model requires reasoning | Sessions default to `thinkingLevel: "off"`. On reasoning-required models (OpenRouter `gpt-oss-120b`, GPT-5 series, o3/o4, `deepseek-r1`, etc.) the provider rejects with `400 Reasoning is mandatory for this endpoint and cannot be disabled`. OpenClaw swallows the error and the user only sees degraded output: hallucinated URLs, weird tag leaks (`</analysis>`, `<\|end_of_turn\|>`), low-quality synthesis. This is the "bot feels stupid" symptom. | Set `agents.defaults.thinkingDefault: "medium"` in `~/.openclaw/openclaw.json`. **Prefer `"medium"` over `"high"` as the global default** — `"high"` causes output starvation on long-synthesis tasks (see next row). Valid values: `off`, `minimal`, `low`, `medium`, `high`, `xhigh` (via `max`), `adaptive` (= `medium`). This is DIFFERENT from `agents/<id>/agent/models.json` `"reasoning": true` — that declares the *model's capability*; `thinkingDefault` controls the *session's default level*. Both must be correct. Restart `openclaw.service`, then verify with `jq 'select(.type=="thinking_level_change") \| .thinkingLevel' <new session>.jsonl` — should be `"medium"`, not `"off"`. For per-task escalation, see § Per-Task Reasoning Overrides. |
| Setting `thinkingDefault: "high"` globally on reasoning models doing long outputs | Reasoning models like `gpt-oss-120b` burn enormous amounts of internal reasoning tokens at `high`. Those tokens count against the per-response `max_tokens` budget. On a press-review / long-summary / large-codegen task the model produces 8000+ tokens of thinking and ZERO visible output before hitting the cap — the trace shows `stopReason: "length"`, `thinking_chars: 16616, text_chars: 0`. OpenClaw's cron fallback then ships the generic `⚠️ Agent couldn't generate a response. Note: some tool actions may have already been executed` message to the user. Script state (e.g., press-review's dedup cache) is still mutated, so retrying without un-marking yields an empty message next time. | Keep `thinkingDefault: "medium"` globally. Use `"high"` ONLY for sessions that need extended chain-of-thought (hard reasoning puzzles, complex debugging). For press-review and other long-synthesis cron jobs, medium plus generous `maxTokens` is strictly better. Real-world quality delta between medium and high on `gpt-oss-120b` is <3 pts on GPQA/MMLU-Pro but 3-5x more tokens burned at high. |
| Relying on dynamic OpenRouter model resolution (no explicit `models.json` entry) | If `openclaw.json` points `agents.defaults.model.primary` / `agents.list[].model` at a provider model that is NOT explicitly declared in the agent's `agents/<id>/agent/models.json`, OpenClaw resolves metadata dynamically from the OpenRouter catalog but falls back to `DEFAULT_MODEL_MAX_TOKENS = 8192` (see `dist/io-*.js:1069`) for the per-request `max_tokens` — regardless of what the model actually supports. On a reasoning model at high/medium thinking, 8192 is often not enough for reasoning + visible output, so responses silently truncate with `stopReason: "length"`. | Always declare the default model explicitly under `providers.<provider>.models` in EACH agent's `models.json`, with an explicit `maxTokens` matching the model's real cap. For `openai/gpt-oss-120b` (context 131072, OpenRouter's `max_completion_tokens: None`), use `maxTokens: 65536`. Example entry: `{"id": "openai/gpt-oss-120b", "name": "GPT-OSS 120B", "api": "openai-completions", "reasoning": true, "input": ["text"], "contextWindow": 131072, "maxTokens": 65536, "compat": {"supportsReasoningEffort": true, "supportsUsageInStreaming": true}}`. Restart `openclaw.service` to load. Verify: `jq '.providers.openrouter.models[] \| select(.id == "openai/gpt-oss-120b") \| .maxTokens' ~/.openclaw/agents/<id>/agent/models.json` — should NOT be null/missing. |
| Leaving `delivery.mode: "none"` on a cron job you want the user to receive | OpenClaw's `resolveCronDeliveryPlan` (in `dist/server-plugin-bootstrap-*.js`) sets `requested: false` when `mode == "none"`, which skips `appendCronDeliveryInstruction` — so the cron prompt never gets "your final plain-text reply will be delivered automatically." The agent treats the output as "handle internally, do not relay" and produces a correct-looking message that never ships. The session jsonl shows a clean `stopReason: "stop"` so it's silent — only `openclaw cron runs --id <jobId>` exposes `"delivered": false`. | Set `"delivery": { "mode": "announce", "channel": "signal", "to": "uuid:<agent-uuid>" }` in `~/.openclaw/cron/jobs.json` for every job that should reach the user. Restart `openclaw.service`. Verify with `openclaw cron runs --id <jobId>` — expect `"delivered": true, "deliveryStatus": "delivered"` in the JSON output. |
| Press-review dedup cache conflates "script processed" with "user delivered" | `scripts/press-review.py` dedupes URLs against `workspace-<agent>/state/press-review-seen.json`. The cache only tracks what the script has PROCESSED — it knows nothing about whether the cron actually delivered to the user. If delivery is broken (e.g., `mode: "none"`), items get burned in the "seen" cache and silently skipped on subsequent runs once delivery is fixed. User then receives a header-only press review. | Short-term recovery: `jq 'to_entries \| map(select(.value != "<today>")) \| from_entries' seen.json > tmp && mv tmp seen.json` to un-mark today's entries so the next run delivers them. Long-term: split the cache into `processed.json` + `delivered.json`, only marking "delivered" after `cron runs` confirms `deliveryStatus: "delivered"`. |

## Troubleshooting Quick Reference

| Problem | Check |
|---------|-------|
| OpenClaw won't start | `openclaw doctor`, check Node version (`node -v` >= 22) |
| Gateway unreachable | `openclaw status`, check the configured service (`systemctl --user status openclaw` or `sudo systemctl status openclaw`) |
| Channel not receiving messages | `openclaw channels status --probe` |
| Signal: daemon not reachable | `pgrep -af signal-cli`, check signal-cli HTTP port |
| Signal: "User is not registered" | Verify `getUserStatus` first, then restart gateway and restore the latest signal-cli backup before attempting destructive re-registration. See [`channel-setup.md`](channel-setup.md) § "Troubleshooting: Signal Registration Lost" |
| Signal: "This person is not on Signal" (after re-registration) | Identity key changed. Contact must delete old conversation and start a new one |
| WhatsApp: QR expired | Re-run `openclaw channels login --channel whatsapp` |
| Tailscale: can't reach dashboard | `tailscale status`, verify both devices on same tailnet |
| Docker bypasses firewall | Add DOCKER-USER iptables rules (see [`references/security-hardening.md`](references/security-hardening.md) § Docker + Firewall) |
| API key rate limited | OpenClaw auto-rotates keys; add backup keys with `_1`, `_2` suffixes |
| High memory usage (Ollama) | Check model size vs RAM; use smaller quantization or smaller model |
| SSH custom port not working (Ubuntu 24.04) | Ubuntu 24.04 uses systemd socket activation. Do NOT put `Port` directives in `sshd_config` — use a systemd socket override at `/etc/systemd/system/ssh.socket.d/override.conf` with explicit `0.0.0.0:PORT` and `[::]:PORT` format. Bare port numbers (e.g., `ListenStream=2222`) don't bind IPv4. Always keep the old port open in UFW until the new port is confirmed working from outside. |
| Locked out of SSH | Use `hcloud server enable-rescue <name> --ssh-key <key>` then `hcloud server reset <name>` to boot into rescue mode. Mount disk at `/mnt` via `mount /dev/sda1 /mnt`, fix configs, unmount, disable rescue, reset. |
| Gateway constantly cycling / "breaks every few minutes" | Check for a DUPLICATE unit. Run `systemctl --user list-units --type=service --no-pager` AND `sudo systemctl list-units --type=service --no-pager \| grep openclaw`. If you see **both** a user-level `openclaw-gateway.service` and a system-level `openclaw.service`, they race for port 18789 — each tries to kill the other on startup ("killing N stale gateway process(es) before restart"). Disable whichever you don't want with `systemctl --user disable --now openclaw-gateway.service` (then rename the unit file to stop systemd still seeing it) or equivalent sudo-level commands. Pick ONE install method and delete the other. |
| `ERR_MODULE_NOT_FOUND: Cannot find module '.../dist/*.runtime-*.js'` in gateway logs | An `npm update -g openclaw` landed new code on disk but the running process still references old code-split chunk filenames (content-hashed — new tarball ships new hashes). Fix: `sudo systemctl restart openclaw.service`. This is visible via `/home/openclaw/.npm-global/lib/node_modules/openclaw/package.json` showing a version newer than what the gateway logs report at startup. |
| Health check `signal-cli getUserStatus` hangs indefinitely | Classic data-dir lock contention. `signal-cli daemon` holds the exclusive lock on `~/.local/share/signal-cli/data/`; a second `signal-cli` subprocess waits forever on the lock without printing the "in use by another instance" error immediately. **Fix the script**: probe `http://127.0.0.1:8080/api/v1/rpc` (**no trailing slash**) instead of spawning a second `signal-cli` subprocess, and wrap with `timeout 10 curl`. Also add `TimeoutStartSec=90` to the health service unit so systemd kills any residual hang after 90 s. |
| signal-cli JSON-RPC `send` returns `UNREGISTERED_FAILURE` | Check the `recipient` format. signal-cli's JSON-RPC `send` takes E.164 phone numbers (`+33612345678`) in `recipient`, NOT `uuid:...` strings. If you pass `"recipient": ["uuid:..."]`, signal-cli strips non-digits and treats it as a phone number — always fails. OpenClaw's internal `delivery.to: "uuid:..."` is fine because OpenClaw translates before calling signal-cli; only raw JSON-RPC calls need the phone-number format. |
| `openclaw` CLI kills the running gateway every time I invoke it | Do NOT run `openclaw cron list` / `openclaw doctor` / any CLI command on the same host as a running `openclaw.service`. The CLI in v2026.4.x detects the running gateway PID and SIGTERMs it ("service-mode: cleared N stale gateway pid(s) before bind on port 18789") before trying to start its own in-process gateway — which usually fails because `OPENCLAW_GATEWAY_TOKEN` env var isn't set in the interactive shell. Use direct file edits for cron changes, signal-cli JSON-RPC for sends, or the Tailscale dashboard for everything else. |
| Plaintext API keys visible in `~/.config/systemd/user/*.service` | Never put `Environment=OPENAI_API_KEY=sk-...` or similar in unit files — they end up mode 664 (group+world readable by default). Use `EnvironmentFile=%h/.openclaw/gateway.env` with `chmod 600`, OR a startup wrapper script that reads from `pass`. Rotate any key that was ever committed as plaintext in a user-readable file. |
| Chat replies feel degraded: hallucinated URLs, weird tag leaks (`</analysis>`, `<\|end_of_turn\|>`), low-quality synthesis | `jq -c 'select(.type=="thinking_level_change")' ~/.openclaw/agents/<id>/sessions/<uuid>.jsonl` — if `thinkingLevel` is `"off"` and the model is reasoning-required (OpenRouter `gpt-oss-120b`, GPT-5 series, o3/o4), look for `400 Reasoning is mandatory` errors with `jq -c 'select(.type=="message" and .message.errorMessage != null)'`. Fix: set `agents.defaults.thinkingDefault: "high"` in `~/.openclaw/openclaw.json` and restart `openclaw.service`. |
| Cron job shows `delivered: false` or `deliveryStatus: "skipped"` even though session output looks correct | `jq '.jobs[] \| select(.name=="<jobname>") \| .delivery' ~/.openclaw/cron/jobs.json` — if `mode: "none"`, OpenClaw silently skips delivery and never injects the `appendCronDeliveryInstruction` into the prompt, so the agent's output is treated as "internal, do not relay." Fix: `mode: "announce"`, plus `channel` and `to` fields. Restart `openclaw.service`, then `openclaw cron run <jobId>` to re-trigger. |
| Press review shows up empty (just the date header) after a delivery outage | `jq '[.[] \| select(. == "<today>")] \| length' ~/.openclaw/workspace-<agent>/state/press-review-seen.json` — the script's dedup cache burned today's items when delivery was broken. They're marked "seen" but never shipped. Remove today's entries from the JSON and re-run. Long-term: split `seen.json` into `processed.json` + `delivered.json`, only mark "delivered" after `cron runs` confirms `deliveryStatus: "delivered"`. |
| Want to diagnose agent quality issues end-to-end from CLI | `ls -lt ~/.openclaw/agents/<agent>/sessions/*.jsonl \| head -5` → pick the session, then run this one-liner to see thinking level + errors + message count per session: `for f in ~/.openclaw/agents/<agent>/sessions/*.jsonl; do lvl=$(jq -r 'select(.type=="thinking_level_change") \| .thinkingLevel' "$f" \| head -1); errs=$(jq -c 'select(.message.errorMessage != null)' "$f" \| wc -l); ok=$(jq -c 'select(.type=="message" and .message.stopReason=="stop")' "$f" \| wc -l); printf "%s  thinking=%-6s  err=%s  ok=%s\n" "$(basename $f)" "$lvl" "$errs" "$ok"; done`. Sessions with `thinking=off` and `err > 0` are the broken ones on reasoning-required models. |
| Heartbeat configured but does nothing | `cat ~/.openclaw/workspace-<agent>/HEARTBEAT.md` — heartbeat needs TWO things: (1) `agents.list[i].heartbeat = { every: "30m" }` in `openclaw.json`, AND (2) a populated `HEARTBEAT.md` describing what to check proactively. An empty template means the heartbeat fires but the agent no-ops silently. Logs `heartbeat: started {intervalMs: 1800000}` confirms only the timer, not useful behavior. |
| Cron or chat delivers "⚠️ Agent couldn't generate a response. Note: some tool actions may have already been executed" | `jq -c 'select(.type=="message" and .message.stopReason=="length") \| {output: .message.usage.output, thinking_chars: ([.message.content[]? \| select(.type=="thinking") \| .thinking] \| join("") \| length), text_chars: ([.message.content[]? \| select(.type=="text") \| .text] \| join("") \| length)}' <session>.jsonl` — if `text_chars == 0` and `thinking_chars` is large, the model hit `max_tokens` mid-reasoning and never produced visible output. Two fixes: (a) lower `thinkingDefault` to `medium`/`low`, (b) raise `maxTokens` in `models.json`. Do both if the task is both hard and long-output. |
| Model in `openclaw.json` is not declared in `agents/<id>/agent/models.json` | `jq --arg m "$(jq -r '.agents.list[] \| select(.id=="<agent>") \| .model' ~/.openclaw/openclaw.json)" '.providers \| to_entries \| map(select(.value.models[].id == ($m \| sub("^[^/]+/"; "")))) \| length' ~/.openclaw/agents/<agent>/agent/models.json` — returns 0 when the configured model has no explicit entry. That agent will use the 8192-token default cap. Fix: add an explicit entry to `providers.<provider>.models` on that agent. |
| Gateway restart needed to pick up `models.json` changes | `models.json` is read at gateway startup and cached in-process. Changes are NOT hot-reloaded. After editing, run `sudo systemctl restart openclaw.service` and poll `curl http://127.0.0.1:18789/healthz` until HTTP 200 (typically 6-12 s). Verify new limits took effect in the next session: `jq -r '.message.usage.output' <new-session>.jsonl \| sort -n \| tail -5` should now show values above the old cap when the model has output to produce. |

---

## Per-Task Reasoning Overrides

**Problem.** `thinkingDefault` is a session-level policy. `/think high` changes it for the rest of the session (not one-shot — see `dist/directive-handling.persist.runtime-*.js` → `persistInlineDirectives`, which sets `sessionEntry.thinkingLevel = directives.thinkLevel`). That means a user who wants "high effort just for this task" has to remember to revert to medium afterward, which they won't.

**Solution (agent-managed).** Put an instruction block in the agent's `workspace-<agent>/AGENTS.md` telling the agent to self-wrap the high-effort turn:

```markdown
## Per-Task Reasoning Override ("use high effort for this")

The global default is `thinkingDefault: medium`. When the user asks for more reasoning on a specific task — e.g., "use high effort for this", "think harder", "this is hard", "take your time on this one", "deep dive" — apply it for the current turn only:

1. At the START of your response (before any tool calls or text), emit the directive on its own line:

   /think high

2. Do the work with high reasoning.

3. At the END of your response, emit on its own line:

   /think medium

This gives a one-shot boost without the user needing to remember to revert. Do NOT do this proactively — only when the user's wording explicitly signals they want more reasoning. For normal conversation, stay at medium.

If the user says "use high effort from now on" or "stay on high", only emit `/think high` (no revert) — that's an explicit session-level request.
```

**Why this works.** OpenClaw parses `/think <level>` as an inline directive in any user OR assistant message via `extractLevelDirective` (`dist/directive-handling.parse-*.js`). The directive persists to `sessionEntry.thinkingLevel` at the point it's seen — so emitting `/think high` at the start, then `/think medium` at the end, sticks the level to medium for the NEXT turn. The current turn still ran at high because the change was applied before the model's response was scheduled.

**What scopes isolate themselves without this pattern.** Cron jobs and heartbeat wake-ups run in their own sessions (not the chat session), so a chat-session `/think high` never leaks into scheduled tasks. The global `thinkingDefault` is always the starting point for cron/heartbeat sessions.

**Verification.** After implementing:

- Send a chat message like "use high effort for this: <question>".
- `jq -c 'select(.type=="thinking_level_change") | .thinkingLevel' ~/.openclaw/agents/<agent>/sessions/<chat-session>.jsonl` — expect two events: `"high"` then `"medium"`.
- Send a follow-up normal message → thinkingLevel should remain `"medium"`.

---

## Automated Maintenance (Post-Install)

Use `systemd --user` for ongoing OpenClaw automation unless you deliberately standardized on a root-managed system service. That keeps the gateway, health checks, and update timers in the same supervision model.

### Signal Health Check (user timer, every 30 min)

The health-check script should be conservative:

1. Probe the running `signal-cli` daemon via its HTTP JSON-RPC endpoint — **never** spawn a second `signal-cli` subprocess. The daemon holds an exclusive lock on the data directory; a subprocess will block indefinitely waiting for it.
2. If the RPC answers `version`, exit 0.
3. If it doesn't, restart the gateway once and poll again for up to 30 s.
4. Only if the daemon still doesn't answer, restore the latest backup of `~/.local/share/signal-cli/data/`, start the gateway, and notify via the same RPC.
5. Do not auto-run `deleteLocalAccountData` or re-register without human approval.

Example script skeleton (updated 2026-04-22 after a wedge-incident. The previous example spawned a second `signal-cli` subprocess to call `getUserStatus` — that contends for the data-dir lock and hangs forever. Use the HTTP JSON-RPC path instead; mind the exact URL `http://127.0.0.1:8080/api/v1/rpc` **with no trailing slash** — the trailing-slash variant silently 404s):

```bash
#!/usr/bin/env bash
set -uo pipefail  # NOT -e: we manage exits manually

ACCOUNT="${OPENCLAW_SIGNAL_ACCOUNT:?set OPENCLAW_SIGNAL_ACCOUNT in the service environment}"
BACKUP_ROOT="$HOME/backups/signal-cli"
STATE_DIR="$HOME/.local/share/signal-cli/data"
RPC="http://127.0.0.1:8080/api/v1/rpc"   # NO trailing slash
LOGFILE="${OPENCLAW_HEALTH_LOG:-/var/log/openclaw-health.log}"
# Grant sudo with: echo "openclaw ALL=(root) NOPASSWD: /usr/bin/systemctl start openclaw.service, /usr/bin/systemctl stop openclaw.service, /usr/bin/systemctl restart openclaw.service" | sudo tee /etc/sudoers.d/openclaw-systemctl

log() { echo "$(date -Iseconds) $1" >> "$LOGFILE"; }

# 0. Gateway must be alive before we bother probing.
if ! systemctl is-active --quiet openclaw.service; then
  log "WARN: gateway not running, skipping check"
  exit 0
fi

# 1. Probe signal-cli daemon via HTTP with a hard timeout. timeout 10 guarantees we NEVER wedge.
payload='{"jsonrpc":"2.0","method":"version","id":1}'
resp=$(timeout 10 curl -sS -m 8 -H 'Content-Type: application/json' -X POST -d "$payload" "$RPC" 2>&1 || true)
if echo "$resp" | grep -q '"result"'; then
  exit 0
fi

log "ALERT: signal-cli RPC unresponsive. Resp: ${resp:0:200}"

# 2. Try a plain restart first.
sudo systemctl restart openclaw.service || true
for _ in 1 2 3 4 5 6; do
  sleep 5
  if timeout 5 bash -c "</dev/tcp/127.0.0.1/8080" 2>/dev/null; then
    log "Recovered via restart"
    exit 0
  fi
done

log "Restart did not recover; attempting backup restore"

# 3. Last resort: restore from the latest backup.
latest_backup=$(ls -1dt "$BACKUP_ROOT"/* 2>/dev/null | head -1)
if [[ -n "${latest_backup:-}" ]]; then
  sudo systemctl stop openclaw.service || true
  rm -rf "$STATE_DIR"
  cp -R "$latest_backup" "$STATE_DIR"
  sudo systemctl start openclaw.service
  sleep 15
fi

log "Restored and restarted"
```

**Unit file — do NOT forget `TimeoutStartSec`**, otherwise a hung run can freeze the timer for days (it happened on this user's VPS: 5 days silent because `Active: activating (start)` never ended):

```ini
# /etc/systemd/system/openclaw-health.service  (or ~/.config/systemd/user/... if user-scoped)
[Unit]
Description=OpenClaw Signal Health Check
After=openclaw.service
# Do NOT add Requires=openclaw.service — that makes the health unit restart
# whenever the gateway restarts, killing the script mid-recovery.

[Service]
Type=oneshot
User=openclaw
ExecStart=/home/openclaw/signal-health-check.sh
TimeoutStartSec=90
TimeoutStopSec=15
KillMode=mixed
```

### Auto-Update (user timer, weekly — controls the system service via sudo)

The update script should be equally strict:

1. Back up `~/.openclaw/` and `~/.local/share/signal-cli/data/`.
2. Stop the gateway cleanly.
3. Update one component at a time.
4. Restart the gateway.
5. Verify `openclaw status`, the gateway health endpoint, and `signal-cli getUserStatus`.
6. Abort and alert if verification fails.

Example user-unit setup:

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/openclaw-health.service <<'EOF'
[Unit]
Description=OpenClaw Signal health check

[Service]
Type=oneshot
EnvironmentFile=%h/.config/openclaw-env
ExecStart=%h/bin/openclaw-signal-health-check.sh
EOF

cat > ~/.config/systemd/user/openclaw-health.timer <<'EOF'
[Unit]
Description=Run OpenClaw Signal health check every 30 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=30min

[Install]
WantedBy=timers.target
EOF

cat > ~/.config/systemd/user/openclaw-update.service <<'EOF'
[Unit]
Description=OpenClaw weekly update

[Service]
Type=oneshot
EnvironmentFile=%h/.config/openclaw-env
ExecStart=%h/bin/openclaw-update.sh
EOF

cat > ~/.config/systemd/user/openclaw-update.timer <<'EOF'
[Unit]
Description=Run OpenClaw weekly update

[Timer]
OnCalendar=Sun *-*-* 04:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

# openclaw-env — keeps secrets out of scripts
# Create and chmod 600 before enabling timers:
# echo 'OPENCLAW_SIGNAL_ACCOUNT=+<E.164 number>' > ~/.config/openclaw-env
# chmod 600 ~/.config/openclaw-env

systemctl --user daemon-reload
systemctl --user enable --now openclaw-health.timer openclaw-update.timer
loginctl enable-linger "$USER"
```

### Update script (`~/bin/openclaw-update.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

ACCOUNT="${OPENCLAW_SIGNAL_ACCOUNT:?set OPENCLAW_SIGNAL_ACCOUNT in ~/.config/openclaw-env}"
# Requires passwordless sudo — see /etc/sudoers.d/openclaw-systemctl setup above.
SERVICE_CTL="sudo systemctl"
SERVICE_NAME="openclaw"
BACKUP_ROOT="$HOME/backups/openclaw-$(date +%Y%m%d)"
LOG="$HOME/.local/log/openclaw-update.log"
mkdir -p "$BACKUP_ROOT" "$(dirname "$LOG")"

log() { echo "[$(date -Is)] $*" | tee -a "$LOG"; }

# 1. Backup current state
log "Backing up ~/.openclaw and signal-cli data..."
cp -a "$HOME/.openclaw" "$BACKUP_ROOT/openclaw"
cp -a "$HOME/.local/share/signal-cli/data" "$BACKUP_ROOT/signal-cli-data" 2>/dev/null || true

# 2. Stop gateway cleanly
log "Stopping gateway..."
$SERVICE_CTL stop "$SERVICE_NAME".service

# 3. Update OpenClaw
log "Updating openclaw..."
npm update -g openclaw 2>&1 | tee -a "$LOG"
NEW_VERSION=$(openclaw --version 2>/dev/null || echo "unknown")
log "New version: $NEW_VERSION"

# 4. Update signal-cli if SIGNAL_CLI_UPGRADE_VERSION is set
# Requires passwordless sudo for tar and ln — extend /etc/sudoers.d/openclaw-systemctl:
#   openclaw ALL=(root) NOPASSWD: /usr/bin/tar, /usr/bin/ln
# Without that, skip this block and upgrade signal-cli manually as root.
if [[ -n "${SIGNAL_CLI_UPGRADE_VERSION:-}" ]]; then
  log "Updating signal-cli to $SIGNAL_CLI_UPGRADE_VERSION..."
  curl -sL "https://github.com/AsamK/signal-cli/releases/download/v${SIGNAL_CLI_UPGRADE_VERSION}/signal-cli-${SIGNAL_CLI_UPGRADE_VERSION}.tar.gz" \
    -o "/tmp/signal-cli-${SIGNAL_CLI_UPGRADE_VERSION}.tar.gz"
  sudo tar xf "/tmp/signal-cli-${SIGNAL_CLI_UPGRADE_VERSION}.tar.gz" -C /opt/
  sudo ln -sf "/opt/signal-cli-${SIGNAL_CLI_UPGRADE_VERSION}/bin/signal-cli" /usr/local/bin/signal-cli
  log "signal-cli updated. Rebuild libsignal if on ARM64 — see channel-setup.md."
fi

# 5. Restart and verify
log "Restarting gateway..."
$SERVICE_CTL start "$SERVICE_NAME".service
sleep 5

if ! $SERVICE_CTL is-active --quiet "$SERVICE_NAME".service; then
  log "ERROR: gateway failed to start after update. Restore from $BACKUP_ROOT"
  exit 1
fi

if ! signal-cli -a "$ACCOUNT" getUserStatus "$ACCOUNT" 2>/dev/null | grep -q ": true"; then
  log "ERROR: Signal account not registered after update. Restore from $BACKUP_ROOT"
  exit 1
fi

log "Update complete. All checks passed."
```

### Graceful Shutdown

The OpenClaw service should include `TimeoutStopSec=30` so signal-cli can flush its state before the process is killed:

```ini
[Service]
TimeoutStopSec=30
KillSignal=SIGTERM
```

---

## When Using This Skill

### If online (web search available)

Before starting, refresh cached data AND fetch OpenClaw docs. This is non-negotiable — the skill caches configs and commands but OpenClaw releases daily and configs change.

**Fetch official docs (do this BEFORE Phase 5, not during debugging):**

1. Fetch `https://docs.openclaw.ai/install` — installation steps, post-install config
2. Fetch `https://docs.openclaw.ai/gateway/security` — auth modes, allowedOrigins, token setup, Control UI pairing
3. Fetch `https://docs.openclaw.ai/gateway/tailscale` — Tailscale Serve config (if user chose Tailscale)
4. Fetch `https://docs.openclaw.ai/channels/<channel>` — channel-specific setup (for Phase 8)

**Refresh version data via web search:**

1. `openclaw latest version release notes` — check for breaking changes vs cached v2026.3.13
2. `signal-cli latest release ARM64` — check if native aarch64 build is now available
3. `<provider> VPS pricing` — verify current prices for the user's chosen provider
4. `tailscale pricing free plan serve` — confirm Serve is still free
5. `openclaw cron job best practices 2026` — new scheduling features or patterns
6. `openclaw agent isolation security` — any new sandbox or per-agent auth features
7. Update the `references/` files if any data changed. Note the new `last_updated` date.

> **Evolutive principle:** OpenClaw releases daily. This skill MUST web-search before any significant decision — don't rely solely on cached configs. If the user's setup uses a feature that has changed, flag it before proceeding.

### If offline (no web search)

This skill is designed to work offline using cached data in `references/`. All commands, configs, and version numbers are embedded. The main risk is that:

- OpenClaw version may have changed (releases daily)
- Pricing may have shifted
- signal-cli may have added ARM64 native builds

Proceed with cached data but **warn the user** that some info may be stale.

### Always

- **Adapt to the agent** — use the agent's native question/answer mechanism
- **After completion** — suggest `/t3-retro` (teatree) or equivalent retrospective to improve this skill

---

## Sources & References

All information gathered and verified on **2026-03-14**. Dates indicate when source was last known accurate.

| Source | URL | Accessed |
|--------|-----|----------|
| OpenClaw GitHub (v2026.3.13) | [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) | 2026-03-14 |
| OpenClaw Docs — Install | [docs.openclaw.ai/install](https://docs.openclaw.ai/install) | 2026-03-14 |
| OpenClaw Docs — Security | [docs.openclaw.ai/gateway/security](https://docs.openclaw.ai/gateway/security) | 2026-03-14 |
| OpenClaw Docs — Tailscale | [docs.openclaw.ai/gateway/tailscale](https://docs.openclaw.ai/gateway/tailscale) | 2026-03-14 |
| OpenClaw Docs — Channels | [docs.openclaw.ai/channels](https://docs.openclaw.ai/channels) | 2026-03-14 |
| OpenClaw Docs — Signal | [docs.openclaw.ai/channels/signal](https://docs.openclaw.ai/channels/signal) | 2026-03-14 |
| OpenClaw Docs — Model Providers | [docs.openclaw.ai/concepts/model-providers](https://docs.openclaw.ai/concepts/model-providers) | 2026-03-14 |
| OpenClaw Docs — Multi-Agent | [docs.openclaw.ai/concepts/multi-agent](https://docs.openclaw.ai/concepts/multi-agent) | 2026-03-16 |
| OpenClaw Agents CLI | [github.com/openclaw/openclaw/.../agents.md](https://github.com/openclaw/openclaw/blob/main/docs/cli/agents.md) | 2026-03-16 |
| Multi-Agent Orchestration Guide | [zenvanriel.com](https://zenvanriel.com/ai-engineer-blog/openclaw-multi-agent-orchestration-guide/) | 2026-03-16 |
| Hetzner Cloud Pricing | [hetzner.com/cloud](https://www.hetzner.com/cloud) | 2026-03-14 |
| Hetzner Ubuntu Security Guide | [community.hetzner.com](https://community.hetzner.com/tutorials/security-ubuntu-settings-firewall-tools/) | 2026 |
| Tailscale Pricing | [tailscale.com/pricing](https://tailscale.com/pricing) | 2026-03-14 |
| Tailscale Serve Docs | [tailscale.com/docs/features/tailscale-serve](https://tailscale.com/docs/features/tailscale-serve) | 2026-03-14 |
| signal-cli (v0.14.1) | [github.com/AsamK/signal-cli](https://github.com/AsamK/signal-cli) | 2026-03-14 |
| Baileys (WhatsApp Web) | [github.com/WhiskeySockets/Baileys](https://github.com/WhiskeySockets/Baileys) | 2026-03 |
| Ollama | [ollama.ai](https://ollama.ai/) | 2026-03 |
| Node.js 24 LTS (24.14.0) | [nodejs.org](https://nodejs.org/en/about/previous-releases) | 2026-03-14 |
| OpenClaw Wikipedia | [en.wikipedia.org/wiki/OpenClaw](https://en.wikipedia.org/wiki/OpenClaw) | 2026-03 |
| OpenClaw Security Risks — Bitsight | [bitsight.com](https://www.bitsight.com/blog/openclaw-ai-security-risks-exposed-instances) | 2026-03 |
| OpenClaw Privacy — TechXplore | [techxplore.com](https://techxplore.com/news/2026-02-openclaw-ai-agent-privacy-nightmare.html) | 2026-02 |
| Cloudflare Tunnel Docs | [developers.cloudflare.com](https://developers.cloudflare.com/cloudflare-one/) | 2026-03 |
| Cloudflare Zero Trust (free) | [cloudflare.com/zero-trust](https://www.cloudflare.com/zero-trust/products/access/) | 2026-03 |
| OpenClaw + Cloudflare Tunnel Guide | [blog.canadianwebhosting.com](https://blog.canadianwebhosting.com/openclaw-cloudflare-tunnel-tailscale-no-public-ports/) | 2026-02 |
| Post Bridge | [post-bridge.com/openclaw](https://www.post-bridge.com/openclaw) | 2026-02 |
| Publora | [publora.com](https://publora.com/blog/connect-openclaw-ai-agent-social-media-publora) | 2026-02 |
