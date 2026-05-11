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
| Docker bypasses firewall | Add DOCKER-USER iptables rules (see [`security-hardening.md`](./security-hardening.md) § Docker + Firewall) |
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
| Cron job fails with `cron: job execution timed out` (e.g. press-review) | The `payload.timeoutSeconds` budget includes the WHOLE agent turn: script exec + tool calls + model synthesis + delivery. Reasoning-heavy models (`gpt-oss-120b`, `deepseek-r1`) can drift well over 60 s for synthesis alone. Read `~/.openclaw/cron/runs/<jobId>.jsonl` to see the duration trend — durations creeping toward the budget cap mean a timeout is imminent. Bump `payload.timeoutSeconds` in `~/.openclaw/cron/jobs.json` (live-reloaded by the gateway, no service restart). Keep budget at ≥ 2× the recent p95 successful duration, not just the average. |
| Cron job fails with `⚠️ Agent couldn't generate a response` | OpenRouter / model-side empty completion, NOT a budget issue. Adding more time doesn't help. Likely causes: provider rate-limit, transient model error, or a model recently moved to "reasoning mandatory" without `"reasoning": true` in the agent's `models.json` (see `press-review.md` § "Model reasoning flag"). Add a fallback model under the agent's `models.fallback` chain. |
| Where's the actual run history for a cron job? | The `state` block inside `~/.openclaw/cron/jobs.json` is a stale schema slot — recent OpenClaw versions write runtime state to `~/.openclaw/cron/jobs-state.json` (latest only) and per-run records to `~/.openclaw/cron/runs/<jobId>.jsonl`. The jsonl is append-only; tail it for the duration trend. The `lastErrorReason: "timeout"` field in `jobs-state.json` distinguishes a hard budget hit from a model-side failure. |

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
