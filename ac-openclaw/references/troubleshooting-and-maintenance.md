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

---

## Automated Maintenance (Post-Install)

Use `systemd --user` for ongoing OpenClaw automation unless you deliberately standardized on a root-managed system service. That keeps the gateway, health checks, and update timers in the same supervision model.

### Signal Health Check (user timer, every 30 min)

The health-check script should be conservative:

1. Verify the account with `signal-cli -a "$ACCOUNT" getUserStatus "$ACCOUNT"`.
2. If the account is still registered, exit without changes.
3. If the account is not registered, restore the most recent backup of `~/.local/share/signal-cli/data/` and restart the gateway once.
4. Only alert the operator after that retry still fails.
5. Do not auto-run `deleteLocalAccountData` or re-register without human approval.

Example script skeleton:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Read from env or config — never hardcode the number
ACCOUNT="${OPENCLAW_SIGNAL_ACCOUNT:?set OPENCLAW_SIGNAL_ACCOUNT in the service environment}"
BACKUP_ROOT="$HOME/backups/signal-cli"
STATE_DIR="$HOME/.local/share/signal-cli/data"
# Adjust if running as a system service: sudo systemctl restart openclaw.service
SERVICE_CTL="systemctl --user"
SERVICE_NAME="openclaw-gateway"

if signal-cli -a "$ACCOUNT" getUserStatus "$ACCOUNT" 2>/dev/null | grep -q ": true"; then
  exit 0
fi

latest_backup=$(ls -1dt "$BACKUP_ROOT"/* 2>/dev/null | head -1)
if [[ -n "${latest_backup:-}" ]]; then
  rm -rf "$STATE_DIR"
  cp -R "$latest_backup" "$STATE_DIR"
fi

$SERVICE_CTL restart "$SERVICE_NAME".service

# Poll until registered (max 30s) instead of sleeping blindly
for i in $(seq 1 6); do
  sleep 5
  if signal-cli -a "$ACCOUNT" getUserStatus "$ACCOUNT" 2>/dev/null | grep -q ": true"; then
    exit 0
  fi
done

echo "ERROR: Signal account still not registered after restart+restore" >&2
exit 1
```

### Auto-Update (user timer, weekly)

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
SERVICE_CTL="systemctl --user"
SERVICE_NAME="openclaw-gateway"
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
