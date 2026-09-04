# OpenClaw Security Hardening Reference

> **Sources:**
>
> - [docs.openclaw.ai/gateway/security](https://docs.openclaw.ai/gateway/security)
> - [Hetzner Community — Ubuntu Security](https://community.hetzner.com/tutorials/security-ubuntu-settings-firewall-tools/)

## OpenClaw Security Model

OpenClaw assumes a **personal assistant model**: one trusted operator per gateway. It is NOT designed for multi-tenant use. Key principles:

- Gateway bound to **loopback by default** — only local clients connect
- **Auth required** for any non-loopback binding
- Tailscale Serve preferred over exposing ports
- Prompt injection is **not solved** — hard enforcement via tool policy, sandboxing, channel allowlists

### What Tailscale Does and Doesn't Protect

**Tailscale covers:**

- Network-level access to the gateway and dashboard (only devices on your tailnet can reach it)
- Removes the need to expose any port to the internet
- Encrypted transit between your devices and the server

**Tailscale does NOT cover:**

- Content of agent conversations — session transcripts are stored in plaintext at `~/.openclaw/agents/<id>/sessions/*.jsonl`
- Admin can always read all agents' conversations via the dashboard or directly on disk
- Cross-agent isolation — different agents share the same filesystem and gateway process

**Consequence:** If you route different people (e.g., personal vs. work contacts) to different agents, their conversations are isolated at the session level but an admin with server access or dashboard access can read all of them. **There is no E2E encryption between an agent's chat and the admin dashboard.** If strict agent privacy is a requirement, run separate gateway instances on separate servers.

### Per-Agent Sandbox Isolation

Agents on the same gateway share a filesystem. Sandbox mode controls what tool calls each agent can execute:

```python
# In openclaw.json — use Python to edit complex structures (see § 9.4)
# Full trust for a personal automation agent (no sandbox):
agent["sandbox"] = {"mode": "off"}

# Isolated execution for untrusted/external-facing agents:
agent["sandbox"] = {"mode": "all", "scope": "agent", "workspaceAccess": "rw"}
# workspaceAccess: "rw" is required or the agent can't write SOUL.md/memory
```

Auto-approve all tool calls for a trusted agent:

```json
// exec-approvals.json
{
  "agents": {
    "<trusted-agent-id>": { "default": "approve" }
  }
}
```

Restart the gateway after any `openclaw.json` or `exec-approvals.json` change.

## Secure Baseline Configuration

```json
{
  "gateway": {
    "mode": "local",
    "bind": "loopback",
    "port": 18789,
    "auth": { "mode": "token", "token": "<openssl rand -base64 32>" }
  },
  "session": { "dmScope": "per-channel-peer" },
  "channels": {
    "whatsapp": {
      "dmPolicy": "pairing",
      "groups": { "*": { "requireMention": true } }
    }
  },
  "tools": {
    "profile": "messaging",
    "deny": ["group:automation", "group:runtime", "group:fs"],
    "exec": { "security": "deny", "ask": "always" },
    "elevated": { "enabled": false }
  },
  "discovery": { "mdns": { "mode": "minimal" } },
  "logging": { "redactSensitive": "tools" }
}
```

## File Permissions

```bash
chmod 700 ~/.openclaw
chmod 600 ~/.openclaw/openclaw.json
chmod 700 ~/.openclaw/credentials
```

## DM Access Control Policies

| Policy | Behavior |
| -------- | ---------- |
| `pairing` (default) | Unknown senders get expiring codes; require approval |
| `allowlist` | Block unknown senders entirely |
| `open` | Allow anyone (requires explicit `"*"` in channel allowlist) |
| `disabled` | Ignore all DMs |

## Gateway Authentication Modes

| Mode | Use case |
| ------ | ---------- |
| `token` | Default. Set via `OPENCLAW_GATEWAY_TOKEN` or config |
| `password` | Required for Tailscale Funnel (public access) |
| `trusted-proxy` | Identity-aware reverse proxies |

## Docker + Firewall (Critical)

Docker **bypasses UFW/iptables** by manipulating chains directly. If you publish a container port, it's accessible from the internet regardless of UFW rules.

**Fix:** Always bind containers to `127.0.0.1` and add DOCKER-USER rules:

```bash
# Block all new inbound connections to Docker containers
sudo iptables -I DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
sudo iptables -I DOCKER-USER -s 127.0.0.0/8 -j RETURN
sudo iptables -I DOCKER-USER -s 100.64.0.0/10 -j RETURN  # Tailscale
sudo iptables -I DOCKER-USER -m conntrack --ctstate NEW -j DROP

# Same for IPv6
sudo ip6tables -I DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
sudo ip6tables -I DOCKER-USER -s ::1/128 -j RETURN
sudo ip6tables -I DOCKER-USER -m conntrack --ctstate NEW -j DROP

# Persist
sudo apt install iptables-persistent
sudo netfilter-persistent save
```

## Tool Access Control

**Default (messaging-only agents, safest):**

```json
{
  "tools": {
    "profile": "messaging",
    "deny": ["group:automation", "group:runtime", "group:fs"],
    "exec": { "security": "deny", "ask": "always" },
    "elevated": { "enabled": false }
  }
}
```

**Full machine access (personal operator agent, no sandbox):**

```json
{
  "tools": {
    "elevated": {
      "enabled": true,
      "allowFrom": {
        "<channel>": ["<uuid-or-identifier>"]
      }
    }
  }
}
```

Set `sandbox: {mode: "off"}` at the agent level and `exec-approvals.agents.<id>.default = "approve"` for fully autonomous operation. Do this only for an agent bound to a channel and contact you fully trust.

Control-plane tools to deny for untrusted senders: `gateway`, `cron`, `sessions_spawn`, `sessions_send`.

### Monitoring Cost

- Review `openclaw usage` monthly to catch runaway cron jobs or unexpected high-volume sessions

## Browser Control Security

- Use a **dedicated browser profile**, never your daily-driver
- Disable sync/password managers in the agent profile
- Browser control = operator access to logged-in accounts
- Disable when not needed: `gateway.nodes.browser.mode="off"`

## Security Audit

Run regularly:

```bash
openclaw security audit              # Standard checks
openclaw security audit --deep       # Live Gateway probe
openclaw security audit --fix        # Auto-fix permissions
```

### Critical Findings to Watch For

| Finding | Fix |
| --------- | ----- |
| `gateway.bind_no_auth` | Add `gateway.auth.*` |
| `fs.state_dir.perms_world_writable` | `chmod 700 ~/.openclaw` |
| `gateway.tailscale_funnel` | Disable or restrict; require password auth |
| `sandbox.dangerous_network_mode` | Fix Docker network settings |

## Credential Locations (Backup These)

| What | Path |
| ------ | ------ |
| Main config | `~/.openclaw/openclaw.json` |
| WhatsApp creds | `~/.openclaw/credentials/whatsapp/<id>/creds.json` |
| Telegram token | config or `TELEGRAM_BOT_TOKEN` env |
| Discord token | config or `DISCORD_BOT_TOKEN` env |
| Signal keys | `~/.local/share/signal-cli/data/` |
| Pairing allowlists | `~/.openclaw/credentials/<channel>-allowFrom.json` |
| Session transcripts | `~/.openclaw/agents/<id>/sessions/*.jsonl` |

## Incident Response Checklist

1. **Contain:** Stop gateway, bind to loopback, disable Funnel/Serve
2. **Rotate:** Gateway token/password, channel tokens, API keys
3. **Audit:** Check logs at `/tmp/openclaw/`, review transcripts, re-run `openclaw security audit --deep`

## LUKS Disk Encryption (Optional)

Full disk encryption on Hetzner Cloud VPS is complex. It requires:

1. Rescue boot and manual partitioning
2. `cryptsetup` with LUKS
3. `dropbear-initramfs` for remote unlock via SSH after reboot

**Simpler alternative:** Use Hetzner encrypted block storage volumes for sensitive data only:

- [Hetzner encrypted volumes guide](https://stanislas.blog/2018/12/how-to-use-encrypted-block-storage-volumes-hetzner-cloud/)

For most personal AI assistant use cases, full disk encryption is overkill. The API keys and credentials can be protected with file permissions + `pass`.

## Ubuntu 24.04 Hardening Checklist

- [x] System updates (`apt update && apt upgrade -y`)
- [x] Non-root user with SSH key
- [x] SSH hardened (no root login, no password auth, max 3 tries)
- [x] UFW enabled (only 22, 80, 443)
- [x] Fail2Ban for SSH
- [x] Unattended security updates
- [x] OpenClaw file permissions locked down
- [x] Docker DOCKER-USER chain rules (if Docker installed)
- [x] Tailscale for remote access (no direct port exposure)
- [ ] Optional: custom SSH port
- [ ] Optional: LUKS disk encryption
- [ ] Optional: Docker sandboxing for OpenClaw tools
