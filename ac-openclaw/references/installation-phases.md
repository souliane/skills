# Installation Phases (3-12)

Detailed execution steps for server provisioning, OS hardening, OpenClaw installation, model configuration, remote access, channel setup, and post-install verification.

## Phase 3: Provision Server

### 3.1 New VPS (any provider)

**SSH key — check existing keys first, don't blindly generate a new one:**

1. List existing local keys: `ls ~/.ssh/*.pub`
2. If using a CLI tool (e.g., `hcloud`), list keys already registered with the provider: `hcloud ssh-key list`
3. Ask the user which key(s) to use — they may want their existing personal key for direct access
4. Only generate a new key if the user has none or explicitly wants a dedicated one:

```bash
ssh-keygen -t ed25519 -C "openclaw" -f ~/.ssh/openclaw_ed25519
```

**When creating the server, include ALL keys the user wants** — both for the agent to SSH in and for the user to SSH in directly.

**Provider-specific provisioning:**

- **Hetzner:** Use cached CLI commands from [`references/hetzner-servers.md`](./hetzner-servers.md).
- **Any other provider:** Web-search for `"<provider> CLI create server"` or guide the user through their web console. The key steps are:
  1. Upload SSH public key(s) if not already registered with the provider
  2. Create an instance with Ubuntu 24.04 LTS (ARM64 preferred, x86 also works)
  3. Select the instance type determined in Phase 1.4
  4. Select the datacenter determined in Phase 1.3
  5. **Include all chosen SSH keys** when creating the server
  6. Note the IP address

After creation, verify SSH access:

```bash
ssh -i ~/.ssh/<chosen_key> root@<SERVER_IP>
```

### 3.2 Existing server

If connecting to an existing server:

```bash
# Test SSH connection
ssh -p <PORT> <USER>@<HOST>
# If password auth: password must be in `pass`
ssh -p <PORT> <USER>@<HOST> # password from: pass show servers/openclaw-vps
```

### 3.3 Local machine

If installing locally, verify prerequisites:

```bash
uname -a          # Confirm OS
node --version    # Need Node >= 22 (24 recommended)
```

---

## Phase 4: Harden the OS

> **Skip if local machine** — only for remote VPS.

Run as root via SSH. Present each block to the user, wait for confirmation before proceeding.

**Also in Phase 4:** install GPG + `pass` on the server (MANDATORY — must be done before any secrets are generated in Phase 5+). See § 5.3 for the `pass` setup commands.

**Set timezone:** Ask the user what timezone they're in and set it:

```bash
# Ask: "What timezone are you in?" then set it
sudo timedatectl set-timezone <timezone>  # e.g., Europe/Brussels, America/New_York
```

```bash
# 4.1 System updates
apt update && apt upgrade -y
apt install -y curl wget git unzip software-properties-common

# 4.2 Create non-root user
adduser --disabled-password --gecos "OpenClaw" openclaw
usermod -aG sudo openclaw
echo "openclaw ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/openclaw
mkdir -p /home/openclaw/.ssh
cp ~/.ssh/authorized_keys /home/openclaw/.ssh/
chown -R openclaw:openclaw /home/openclaw/.ssh
chmod 700 /home/openclaw/.ssh && chmod 600 /home/openclaw/.ssh/authorized_keys

# 4.3 SSH hardening — IMPORTANT: verify openclaw user can SSH in BEFORE restarting
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
# NOTE: Do NOT put Port directives in sshd_config on Ubuntu 24.04.
# Ubuntu 24.04 uses systemd socket activation — the socket controls
# which ports SSH listens on. Port directives in sshd_config conflict.
cat > /etc/ssh/sshd_config.d/hardened.conf << 'SSHEOF'
PermitRootLogin no
PasswordAuthentication no
PermitEmptyPasswords no
MaxAuthTries 3
X11Forwarding no
AllowUsers openclaw
SSHEOF

# Custom SSH port via systemd socket override (Ubuntu 24.04+)
# MUST use explicit 0.0.0.0:PORT and [::]:PORT format, not bare ports.
# First clear defaults with ListenStream=, then add desired ports.
mkdir -p /etc/systemd/system/ssh.socket.d
cat > /etc/systemd/system/ssh.socket.d/override.conf << 'SOCKEOF'
[Socket]
ListenStream=
ListenStream=0.0.0.0:22
ListenStream=[::]:22
ListenStream=0.0.0.0:2222
ListenStream=[::]:2222
SOCKEOF
systemctl daemon-reload
systemctl restart ssh.socket ssh.service

# 4.4 Firewall (UFW) — keep BOTH SSH ports open initially
ufw default deny incoming && ufw default allow outgoing
ufw allow 22/tcp comment 'SSH-temp'
ufw allow 2222/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
# AFTER verifying port 2222 works from outside, remove port 22:
# ufw delete allow 22/tcp
# Then update socket override to remove port 22 lines

# 4.5 Fail2Ban
apt install -y fail2ban
cat > /etc/fail2ban/jail.local << 'F2BEOF'
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600
F2BEOF
systemctl enable fail2ban && systemctl start fail2ban

# 4.6 Automatic security updates
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

> **Docker bypass warning:** Docker bypasses UFW. See [`references/security-hardening.md`](./security-hardening.md) § Docker + Firewall.

**Disk encryption (only if user requested):** LUKS on cloud VPS requires rescue boot + `dropbear-initramfs` for remote unlock. For most users, encrypted block storage volumes are simpler. See [`references/security-hardening.md`](./security-hardening.md) § LUKS.

---

## Phase 5: Install OpenClaw

All commands as the `openclaw` user (`su - openclaw` on VPS).

### 5.1 Install Node.js 24

```bash
# Install Node.js 24 via NodeSource
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs

# Verify
node --version   # Should show v24.x
npm --version
```

### 5.2 Install OpenClaw

```bash
# Recommended: use the official installer
curl -fsSL https://openclaw.ai/install.sh | bash

# OR via npm directly:
# npm install -g openclaw@latest

# Run onboarding wizard
openclaw onboard --install-daemon
```

The onboarding wizard will ask about:

- Model provider (configure in Phase 6)
- Default agent name
- Initial channel (configure in Phase 7)

You can skip channels during onboarding and configure them manually later.

### 5.3 Configure gateway (MUST do before starting)

The gateway will refuse to start without `gateway.mode`. Configure it immediately after install:

```bash
# Set gateway mode (required — gateway won't start without this)
openclaw config set gateway.mode local

# Set auth to token mode (recommended)
openclaw config set gateway.auth.mode token

# Generate and store the gateway token
OPENCLAW_GATEWAY_TOKEN="$(openssl rand -base64 32)"
echo "export OPENCLAW_GATEWAY_TOKEN=\"$OPENCLAW_GATEWAY_TOKEN\"" >> ~/.bashrc
```

**If using Tailscale Serve (§ 1.8):** also configure:

```bash
openclaw config set gateway.tailscale.mode serve
openclaw config set gateway.auth.allowTailscale true
# Allow the Tailscale hostname as a Control UI origin
openclaw config set gateway.controlUi.allowedOrigins '["https://<server-name>.<tailnet>.ts.net"]'
```

> The `allowedOrigins` and `gateway.mode` MUST be set before the gateway starts, otherwise the user will hit errors ("gateway start blocked", "origin not allowed"). Do not defer this to a later phase.

**Store ALL generated secrets in `pass` immediately** — on the user's local machine, not the server:

```bash
pass insert openclaw/gateway-token
# Paste the OPENCLAW_GATEWAY_TOKEN value
```

### 5.4 Verify installation

```bash
openclaw doctor    # Check configuration
openclaw status    # Gateway status
openclaw --version # Confirm version
```

### 5.5 Dashboard device pairing

When the user first opens the Control UI from a new device (browser), OpenClaw requires a one-time device pairing approval — even on the same tailnet.

**The agent must handle this proactively:**

1. After the gateway is running and the user opens the dashboard, they will see "pairing required"
2. On the server, list pending requests: `openclaw devices list`
3. Approve the pending request: `openclaw devices approve <request-id>`
4. The dashboard will connect after approval

**Tell the user this will happen before they open the dashboard**, not after they see the error. Example: "When you open the dashboard for the first time, it will show 'pairing required'. That's expected — I'll approve your device from the server."

---

## Phase 6: Configure Model Provider

### 6.1 BYOK (Bring Your Own Key)

Ask the user which provider:

```
Which AI model provider will you use?

a) Anthropic (Claude Opus 4.6, Sonnet 4.6, Haiku 4.5)   [RECOMMENDED]
b) OpenAI (GPT-5.2, GPT-5, GPT-4.5)
c) Google Gemini (Gemini 3 Pro, Flash)
d) OpenRouter (access to all models, single API key)
e) Other (xAI, Groq, Mistral, etc.)
```

#### Account and key setup (all providers)

**Always recommend a dedicated account** — not the user's personal one. Explain why:

- **Billing isolation** — runaway usage or prompt injection only affects the dedicated account
- **Revocation** — revoking the key doesn't break the user's other projects
- **Audit** — clean usage tracking for OpenClaw specifically

**Always recommend a restricted/scoped API key** with minimal permissions. Each provider has different permission models — **web-search for the current UI** before advising, as these change frequently.

**Always recommend a budget/spending limit** as a safety net against runaway usage.

#### Provider-specific key setup

**OpenAI:**

1. Create a dedicated project: [platform.openai.com/settings/organization/projects](https://platform.openai.com/settings/organization/projects) → "Create project" (e.g., "openclaw")
2. Switch to that project (top-left switcher)
3. Create API key: [platform.openai.com/api-keys](https://platform.openai.com/api-keys) → "Create new secret key"
4. Owner: **Service account** (not personal) — name it `openclaw-bot`
5. Permissions: **Restricted** — set everything to **None**, then enable only what's needed:

   | Permission | Setting | Why |
   |-----------|---------|-----|
   | Responses (`/v1/responses`) | **Write** | Core — OpenClaw chat |
   | Chat completions (`/v1/chat/completions`) | **Request** | Core — legacy chat API |
   | All others (Text-to-speech, Realtime, Embeddings, Images, Moderations, Assistants, Threads, Evals, Fine-tuning, Files, Videos, Vector Stores, Prompts, Datasets) | **None** | Not needed |

   > **Note (2026-03-15):** Permission levels vary by endpoint — some offer Write, others offer Request. The UI changes over time. Web-search or ask the user for a screenshot to verify current endpoint names and available levels.

6. Set budget: [platform.openai.com/settings/organization/limits](https://platform.openai.com/settings/organization/limits) (e.g., $10-20/month)

**Anthropic:**

1. Create account at [console.anthropic.com](https://console.anthropic.com)
2. Create API key with a descriptive name (e.g., `openclaw-bot`)
3. Set spending limit in Settings → Plans & Billing

**Google Gemini:**

1. Create a dedicated Google account (e.g., `yourname.openclaw@gmail.com`)
2. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → Generate API key
3. Gemini has a generous free tier (60 req/min on Flash)

**OpenRouter:**

1. Create account at [openrouter.ai](https://openrouter.ai)
2. Create API key in Settings → Keys
3. Set a credit limit

#### Store the key securely

**Always use `pass`** (the standard Unix password manager). Never store API keys in plaintext config files or `.bashrc`.

```bash
# On the user's local machine
pass insert openclaw/<provider>-key

# On the server: export from pass into the environment
echo 'export OPENAI_API_KEY="$(pass show openclaw/openai-key)"' >> ~/.bashrc
```

> **If `pass` is not available on the server** (common for VPS), use OpenClaw's built-in config instead:
>
> ```bash
> openclaw configure --section model
> # Paste the API key when prompted — stored in ~/.openclaw/credentials/
> ```

#### Configure OpenClaw

```bash
# OpenAI
openclaw models set openai/gpt-5

# Anthropic
openclaw models set anthropic/claude-sonnet-4-6

# Gemini
openclaw models set google/gemini-3-pro-preview

# OpenRouter
openclaw models set openrouter/anthropic/claude-opus-4-6
```

### 6.2 Local Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model (based on server RAM)
# 4 GB RAM:
ollama pull qwen3:4b

# 8 GB RAM:
ollama pull llama3.1:8b
# or: ollama pull qwen3:8b

# 16 GB RAM:
ollama pull qwen3:14b

# Verify
ollama list
ollama run qwen3:8b "Hello, are you working?"

# Configure OpenClaw to use Ollama
# Ollama is auto-detected at http://127.0.0.1:11434/v1
openclaw models set ollama/qwen3:8b
```

### 6.3 Both (BYOK primary + Ollama fallback)

Configure BYOK as primary (6.1), then install Ollama (6.2). OpenClaw falls back through its provider priority chain automatically when the primary provider is rate-limited or unreachable.

---

## Phase 7: Secure Remote Access

The user already chose their remote access method in § 1.8. Execute the chosen option below.

### 7.1 Option A: Cloudflare Tunnel + Zero Trust (recommended)

**Best for most users.** Access from any browser or phone without installing anything. Cloudflare handles HTTPS, DDoS protection, and identity verification. The tunnel is outbound-only — no ports are opened on your server.

**Prerequisites:** A domain name (even a cheap one) + free [Cloudflare account](https://dash.cloudflare.com/sign-up)

**Step 1 — Add domain to Cloudflare:**

1. Sign up at [dash.cloudflare.com](https://dash.cloudflare.com)
2. Add your domain and follow the nameserver migration instructions
3. Wait for DNS propagation (can take up to 24h, usually minutes)

**Step 2 — Install `cloudflared` on the server:**

```bash
curl -fsSL https://pkg.cloudflare.com/install.sh | sudo bash
sudo apt install -y cloudflared
```

**Step 3 — Create and configure the tunnel:**

```bash
cloudflared tunnel login
# Opens browser — authorize with your Cloudflare account

cloudflared tunnel create openclaw
cloudflared tunnel route dns openclaw claw.yourdomain.com
```

**Step 4 — Configure the tunnel:**

```bash
sudo mkdir -p /etc/cloudflared
sudo cat > /etc/cloudflared/config.yml << 'CFEOF'
tunnel: openclaw
credentials-file: /home/openclaw/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: claw.yourdomain.com
    service: http://127.0.0.1:18789
  - service: http_status:404
CFEOF
```

**Step 5 — Enable as systemd service:**

```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

**Step 6 — Add Zero Trust Access policy (CRITICAL):**

Without this, anyone who knows the URL can access your dashboard. Go to [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com/):

1. Access > Applications > Add an Application > Self-hosted
2. Application domain: `claw.yourdomain.com`
3. Add a policy: Allow — Emails ending in `@yourdomain.com` (or specific emails)
4. Or: Allow — Login methods: Google, GitHub, One-time PIN (email)

Now when you open `https://claw.yourdomain.com` from your phone, you'll see a Cloudflare login page first. After authenticating (Google, GitHub, or email OTP), you reach the OpenClaw dashboard. No VPN, no app install.

**OpenClaw config for Cloudflare Tunnel:**

```jsonc
{
  "gateway": {
    "bind": "loopback",
    "port": 18789,
    "auth": { "mode": "token" },
    "trustedProxies": ["127.0.0.1"]
  }
}
```

```bash
export OPENCLAW_GATEWAY_TOKEN="$(openssl rand -base64 32)"
echo "export OPENCLAW_GATEWAY_TOKEN=\"$OPENCLAW_GATEWAY_TOKEN\"" >> ~/.bashrc
```

### 7.2 Option B: Tailscale Serve (most secure)

**Best if you already use Tailscale** or want zero internet exposure. The dashboard is only accessible from devices on your private Tailscale network.

**Tradeoff:** Every device (laptop, phone, tablet) must have the Tailscale app installed and be logged into the same account.

**How it works:**

- Tailscale creates an encrypted mesh network ("tailnet") between your devices
- Serve routes tailnet traffic to localhost:18789 (OpenClaw gateway)
- Dashboard accessible at `https://<server-name>.<tailnet>/`
- **Free:** Personal plan = 3 users, 100 devices, Serve included
- **Funnel** (public internet access) is Premium only ($18/user/mo)

```bash
# On the server
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Opens an auth URL — user must visit it in their browser
```

**Tailscale account creation:** Tailscale uses SSO only (no username/password). Recommend **personal Google account** — it's the most convenient because:

- Same login works on the Tailscale phone app (needed to access the dashboard from mobile)
- No extra account to manage
- Tailscale only gets your email for identity — no access to Google Drive, Gmail, or any data
- End-to-end encrypted between your devices; Tailscale can't read your traffic

**Ask the user which phone they have** — this determines the best SSO:

- **iPhone** → Apple SSO (native integration, seamless on iOS)
- **Android** → Google SSO (native integration, seamless on Android)
- **Either** → Google also works fine on iPhone; GitHub/Microsoft work but are less convenient on mobile

**VPN compatibility (CRITICAL — ask in § 1.8, act here):**

Tailscale can conflict with other VPNs on the user's devices:

- **On the server:** No conflict — the server typically has no other VPN
- **On macOS/iOS:** Tailscale and WireGuard/OpenVPN compete for the system network extension. **Do NOT run both simultaneously.** User must toggle one off before using the other
- **On Linux/Android:** Generally coexists, but CGNAT range (`100.64.0.0/10`) conflicts are possible

If the user has an existing VPN, explain: "You'll need to disconnect your VPN before opening the OpenClaw dashboard, then reconnect after. If toggling is too inconvenient, Cloudflare Tunnel (option a) avoids this entirely — no VPN app needed on your devices."

**After the server is authenticated, install Tailscale on every device that needs to access the OpenClaw dashboard:**

| Device | Install method | Notes |
|--------|---------------|-------|
| macOS | **Mac App Store** → "Tailscale" | **Do NOT use `brew install tailscale`** — the CLI-only version can't route HTTP traffic on macOS (missing network extension). App Store version handles routing, DNS, and the menu bar. **Install automation:** ask the user "I'll open the Tailscale page in the App Store — OK?" then run `open "macappstore://apps.apple.com/app/tailscale/id1475387142?mt=12"`. Always ask before opening GUI windows. |
| iPhone | App Store → "Tailscale" | Log in with same SSO account |
| Android | Play Store → "Tailscale" | Log in with same SSO account |
| Linux | `curl -fsSL https://tailscale.com/install.sh \| sh` then `sudo tailscale up` | CLI works fully on Linux |
| Windows | Download from [tailscale.com/download](https://tailscale.com/download) | |

All devices must use the **same SSO account** as the server. Once connected, the OpenClaw dashboard is accessible from any of them.

**Enabling Tailscale Serve on the tailnet:**

When you run `tailscale serve` for the first time, Tailscale may prompt you to enable Serve for your tailnet. It will show a URL like `https://login.tailscale.com/f/serve?node=...`.

**CRITICAL WARNING:** The page may also offer to enable **Funnel**. **Do NOT enable Funnel** — it exposes your server to the public internet, defeating the entire purpose of using Tailscale for private access. Only enable **Serve** (private, tailnet-only access).

**OpenClaw config:**

```jsonc
{
  "gateway": {
    "bind": "loopback",
    "port": 18789,
    "tailscale": { "mode": "serve" },
    "auth": { "mode": "token", "allowTailscale": true }
  }
}
```

```bash
export OPENCLAW_GATEWAY_TOKEN="$(openssl rand -base64 32)"
echo "export OPENCLAW_GATEWAY_TOKEN=\"$OPENCLAW_GATEWAY_TOKEN\"" >> ~/.bashrc
openclaw gateway restart
```

### 7.3 Option C: Caddy reverse proxy (simplest)

**Simplest setup** — just a domain + reverse proxy. No third-party accounts beyond your domain registrar.

**Tradeoff:** Password-only auth. The dashboard is on the public internet behind HTTPS + a password. Less secure than Cloudflare Zero Trust or Tailscale.

```bash
# Install Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy

# Configure Caddy (auto-HTTPS with Let's Encrypt)
sudo cat > /etc/caddy/Caddyfile << 'CADDYEOF'
claw.yourdomain.com {
    reverse_proxy 127.0.0.1:18789
}
CADDYEOF

sudo systemctl restart caddy
```

Point DNS A record to server IP. Caddy handles SSL automatically.

**OpenClaw config:**

```jsonc
{
  "gateway": {
    "bind": "loopback",
    "port": 18789,
    "auth": { "mode": "password" },
    "trustedProxies": ["127.0.0.1"]
  }
}
```

```bash
export OPENCLAW_GATEWAY_PASSWORD="$(openssl rand -base64 32)"
echo "export OPENCLAW_GATEWAY_PASSWORD=\"$OPENCLAW_GATEWAY_PASSWORD\"" >> ~/.bashrc
# Save this password — you'll need it to log into the dashboard
```

---

## Phase 8: Connect Messaging Channels

For each channel the user selected, follow [`references/channel-setup.md`](./channel-setup.md). Do them **one at a time** — verify each works before moving to the next.

**Quick summary per channel:**

| Channel | Key step | Verify with |
|---------|----------|-------------|
| Signal | Install signal-cli + register phone number | `openclaw pairing list signal` |
| Telegram | Get bot token from `@BotFather` | Send message to bot |
| WhatsApp | `openclaw channels login --channel whatsapp` + scan QR | Send message |
| Discord | Create bot in Developer Portal + enable intents | Send message in server |
| Slack | Create app, get bot + app tokens, enable Socket Mode | Send DM to bot |

After configuring each channel in `~/.openclaw/openclaw.json`:

```bash
openclaw gateway restart
openclaw channels status --probe
```

**Universal config pattern** (add per channel):

```jsonc
{
  "channels": {
    "<channel>": {
      "enabled": true,
      "dmPolicy": "pairing",
      "groups": { "*": { "requireMention": true } }
    }
  }
}
```

**Critical reminders:**

- Signal: use a **dedicated phone number** (registering can de-auth your main Signal app). ARM64: may need JVM variant (`openjdk-25-jre-headless`) if no native build
- WhatsApp: needs a **real mobile number** (no VoIP). QR code expires in 60 seconds
- All channels: approve new contacts via `openclaw pairing approve <channel> <code>`

Full step-by-step for each channel: [`references/channel-setup.md`](./channel-setup.md)

---

## Phase 9: Post-Install Hardening & Verification

### 9.1 Security audit + baseline config

```bash
openclaw security audit --deep
chmod 700 ~/.openclaw && chmod 600 ~/.openclaw/openclaw.json && chmod 700 ~/.openclaw/credentials
```

Apply the secure baseline config from [`references/security-hardening.md`](./security-hardening.md) — it includes: loopback binding, token auth, per-channel-peer DM scope, messaging-only tool profile, minimal mDNS, and sensitive log redaction.

### 9.2 Enable OpenClaw as a systemd service

```bash
sudo cat > /etc/systemd/system/openclaw.service << 'SVCEOF'
[Unit]
Description=OpenClaw Gateway
After=network.target

[Service]
Type=simple
User=openclaw
Environment=HOME=/home/openclaw
EnvironmentFile=/home/openclaw/.openclaw/env
ExecStart=/usr/bin/openclaw gateway
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable openclaw
sudo systemctl start openclaw
sudo systemctl status openclaw
```

### 9.3 Docker sandboxing (optional but recommended)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker openclaw
```

Config (use Python to edit JSON directly — see § 9.4 warning):

```json5
{
  agents: {
    defaults: {
      sandbox: {
        mode: "all",          // "off", "non-main", or "all"
        scope: "agent",       // "agent", "session", or "shared"
        workspaceAccess: "rw" // CRITICAL: without this, agent can't write USER.md, SOUL.md, memory
      }
    }
  }
}
```

> **`workspaceAccess: "rw"` is required** when `sandbox.mode` is `"all"`. Without it, the agent cannot write to its own workspace — USER.md updates, memory writes, and file operations all fail silently.
> **Docker + UFW warning:** Docker bypasses UFW. Add DOCKER-USER iptables rules — see [`references/security-hardening.md`](./security-hardening.md) § Docker + Firewall.

### 9.4 Config editing — use Python, not `openclaw config set` for complex changes

**CRITICAL WARNING:** `openclaw config set` and `openclaw models set` can **silently overwrite** manually-added config sections (`agents.list`, `bindings`, custom entries). This has caused data loss (e.g., multi-agent bindings disappearing).

**For simple scalar values:** `openclaw config set` is fine (e.g., `gateway.mode`, `channels.signal.enabled`).

**For complex structures** (agents.list, bindings, sandbox config): edit the JSON directly with Python:

```bash
python3 -c "
import json
with open('/home/openclaw/.openclaw/openclaw.json') as f:
    cfg = json.load(f)
# Make changes here
cfg['agents']['defaults']['sandbox'] = {'mode': 'all', 'scope': 'agent', 'workspaceAccess': 'rw'}
with open('/home/openclaw/.openclaw/openclaw.json', 'w') as f:
    json.dump(cfg, f, indent=2)
"
```

**After ANY `openclaw config set` or `openclaw models set` command:** verify that `agents.list` and `bindings` are still intact. If they were wiped, restore from the backup or re-add them.

### 9.5 Ollama fallback auth

If using Ollama as a fallback model, OpenClaw requires an auth entry even though Ollama has no real API key. Write to **each agent's** `auth-profiles.json`:

```bash
# For EACH agent (main, darwin, etc.)
python3 -c "
import json
auth = {
    'ollama:local': {
        'type': 'token',
        'provider': 'ollama',
        'token': 'ollama-local'
    },
    'lastGood': {
        'ollama': 'ollama:local'
    }
}
with open('/home/openclaw/.openclaw/agents/<AGENT_ID>/agent/auth-profiles.json', 'w') as f:
    json.dump(auth, f, indent=2)
"
```

Also add `OLLAMA_API_KEY="ollama-local"` to the gateway wrapper script.

### 9.6 Signal profile name

Set a display name for the Signal bot so contacts see a name, not just a number:

```bash
signal-cli -u +<BOT_NUMBER> updateProfile --given-name "OpenClaw"
```

---

## Phase 10: Social Media & Additional Channels (Optional)

**Explain the difference to the user first:**

> OpenClaw has two types of external connections:
>
> **Messaging channels** (Phase 8) = **private two-way chat with your bot.** You DM the bot, it replies. Like texting a friend. This is how you interact with your assistant day-to-day.
>
> **Social media posting** = **the bot publishes content publicly on your behalf.** It posts to your timeline or feed. Like having a social media manager.
>
> **Recommendation: stick to private messaging.** Most users only need to chat with their assistant privately. Social media posting adds complexity, security risk, and the danger of the bot posting something publicly you didn't intend. Only set up social media posting if you have a specific need (e.g., content marketing automation).

### Private messaging — which platform is best?

Present this table to help the user choose (or add more channels to what they set up in Phase 8):

| Platform | Privacy | Ease of setup | Phone needed? | Encryption | Best for |
|----------|---------|---------------|--------------|------------|----------|
| **Signal** | Excellent | Medium | Yes (dedicated recommended) | End-to-end | Privacy-first users. Gold standard for secure messaging |
| **Telegram** | Good | Easiest | No | Server-side (E2E optional) | Quick setup. Best first channel to test |
| **WhatsApp** | Good | Easy | Yes (real mobile) | End-to-end | Already-WhatsApp users. Most familiar UX |
| **Matrix** | Excellent | Medium | No | End-to-end (Megolm) | Self-hosters who want full control. E2E by default, decentralized, no single company owns it |
| **Discord** | Moderate | Easy | No | None (TLS only) | Gamers, communities. Not for sensitive data |
| **Slack** | Moderate | Medium | No | None (TLS only) | Work/team use |
| **Mastodon** | Low for DMs | Medium | No | **DMs NOT encrypted** | Fediverse users. Do NOT use for private bot conversations — server admins can read DMs |
| **IRC** | Low | Easy | No | None (TLS only) | Minimalists. No media support |

**Recommendation order for private messaging:**

1. **Signal** — privacy champion (E2E, open source, no metadata collection)
2. **Matrix** — self-hosted privacy (E2E via Megolm, decentralized, you own the server). More complex to set up but the most private option if you self-host
3. **Telegram** — easiest setup (5 minutes, no phone needed for the bot). Server-side encryption only — Telegram can read your messages, but convenient
4. **WhatsApp** — familiar UX, E2E encrypted, but Meta-owned (metadata collection)

> **Mastodon is NOT suitable for private messaging.** Despite appearing to have DMs, Mastodon "direct messages" are just posts with restricted visibility — they are stored in plaintext on the server. Any server admin can read them. For private conversations with your bot, use Signal, Matrix, or WhatsApp instead.

### Social media posting (only if user explicitly wants it)

Ask: "Do you also want OpenClaw to post content publicly on your behalf (social media automation)?"

**Default recommendation: No.** Only proceed if the user has a clear use case.

If yes, present the recommendation from [`references/social-media.md`](./social-media.md):

| Platform | Recommendation | Why |
|----------|---------------|-----|
| **Bluesky** | Recommended | Open protocol, API-friendly, privacy-respecting, free API |
| **Mastodon** | Recommended | Open source, federated, good API |
| **LinkedIn** | Use with caution | Good API but use a **dedicated account** |
| **X/Twitter** | Use with caution | $100+/mo API for posting, aggressive rate limits, data used for AI training |
| **Instagram/Facebook** | Not recommended | No personal posting API; Business account required; Meta data collection |

**Key warnings:**

- **Always use dedicated accounts** — never connect personal profiles
- Use a **third-party scheduler** (Post Bridge, Publora, Genviral) rather than direct API access
- **Prompt injection risk**: social media comments are untrusted input that could steer your agent
- Store all OAuth tokens in `pass`, never in config files

Full setup details: [`references/social-media.md`](./social-media.md)

---

## Phase 11: Additional Integrations

Ask what else the user wants. Present **one category at a time**:

**Core integrations:** Gmail & Calendar (OAuth), Browser automation (Chromium), Obsidian/Notes, GitHub/GitLab, Spotify/Hue

**Advanced:** Cron jobs & webhooks, Voice mode (ElevenLabs), Community skills from [ClawHub](https://openclaw.ai/) (13,000+), Canvas/A2UI workspace, Multi-agent routing

**Maintenance:** Automated backups, Log rotation, Monitoring/health checks

**Key recommendations:**

- **Use dedicated accounts** for connected services (separate Gmail, GitHub, etc.)
- **Start small** — one channel working perfectly before adding more
- For each integration, **do a web search** for the latest OpenClaw setup guide

### Automated backups (always recommend)

```bash
cat > /home/openclaw/backup-openclaw.sh << 'BKEOF'
#!/bin/bash
BACKUP_DIR="/home/openclaw/backups"
mkdir -p "$BACKUP_DIR"
tar czf "$BACKUP_DIR/openclaw-$(date +%Y-%m-%d).tar.gz" \
  ~/.openclaw/openclaw.json ~/.openclaw/credentials/ \
  ~/.openclaw/agents/ ~/.local/share/signal-cli/data/ 2>/dev/null
find "$BACKUP_DIR" -name "openclaw-*.tar.gz" -mtime +30 -delete
BKEOF
chmod +x /home/openclaw/backup-openclaw.sh
(crontab -l 2>/dev/null; echo "0 3 * * * /home/openclaw/backup-openclaw.sh") | crontab -
```

---

## Phase 12: Wrap Up

### 12.1 Final health check

```bash
openclaw doctor
openclaw security audit --deep
openclaw channels status --probe
```

### 12.2 Test end-to-end

**The agent must test everything itself — do not ask the user to test and report errors.** Run these checks programmatically:

```bash
# Test gateway is responding
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18789/

# Test model works (via Ollama directly if configured)
curl -s http://127.0.0.1:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<model>","messages":[{"role":"user","content":"Say hello"}],"max_tokens":10}'

# Test Signal channel
openclaw channels status --probe

# Test dashboard is accessible via Tailscale (from user's machine)
curl -sk -o /dev/null -w "%{http_code}" https://<tailscale-hostname>/

# Verify agent isolation (if multi-agent)
openclaw agents list --bindings

# Verify sandbox allows workspace writes
# (the agent should write a test file and verify)
```

Only ask the user to send a Signal message for the final human-in-the-loop test (pairing approval requires their interaction).

### 12.3 Post-install analysis and suggestions

**Analyze the current config and suggest improvements.** Ask the user about each one individually:

- **Backups:** "Your config is only on the server. Want to set up off-site backups?" Recommend GitHub (free, deploy key) + Hetzner snapshots (~0.21 EUR/mo for weekly). Set up automated daily backup script + weekly snapshot rotation.
- **Web search:** If not configured: "Want to enable web search for the agent? It can search the internet to answer questions."
- **Skills:** Check `openclaw skills check` — suggest installing dependencies for useful skills (ClawHub, summarize, GitHub, etc.)
- **Multi-user:** "Will anyone else use this bot (family, friends)? If yes, be aware that all users share the same agent memory and context — the bot may reference private conversations with other users."
- **Sandbox workspace:** If `sandbox.mode=all`, verify `sandbox.workspaceAccess=rw` is set. Without it, the agent can't write to its own workspace (SOUL.md, USER.md, memory files). This is a common issue.
- **Timezone:** Verify server timezone matches user's location: `timedatectl`
- **Signal profile:** If using Signal, set a profile name: `signal-cli -u +NUMBER updateProfile --given-name "OpenClaw"`

### 12.4 Recap for the user

Present a complete summary of what was installed, how to access it, and what secrets/bookmarks to save. The user should walk away knowing everything without re-reading the conversation.

```
Installation complete!

Summary:
- OpenClaw running on <server> as systemd service
- Dashboard: <URL> (via <access method>)
- Channels: <list>
- Model: <primary> + <fallback>
- Security: <list of measures>
- Backups: <local + off-site method>

Secrets stored in `pass` (local machine):
- openclaw/gateway-token
- openclaw/<provider>-key

Bookmarks to save:
- Dashboard: <URL>
- Server provider console: <URL>
- API key management: <URLs per provider>

SSH access:
- ssh -i <key> -p <port> <user>@<ip>

Key things to know:
- <VPN conflict warning if applicable>
- <Dedicated phone number for Signal>
- <Sandbox limitations>
- <Backup schedule>
- <How to add new users>

Maintenance (covered by this skill):
- Update OpenClaw: npm update -g openclaw
- Update models: ollama pull <model>
- Rotate API keys: pass insert -f openclaw/<key>, restart gateway
- Security audit: openclaw security audit --deep
- Backup restore: <method>
```

### 12.5 Multi-user setup (if requested)

When adding family members or friends:

**Privacy warning (MUST tell the user BEFORE adding anyone):** OpenClaw has a **single agent profile** by default. All paired users share the same SOUL.md, USER.md, and conversation memory. The bot may reference things said by other users. **Always recommend per-user agent isolation** (most secure).

#### Per-user agent isolation (recommended)

Each person gets their own isolated agent with separate memory, personality, and conversation history:

```bash
# Create agents
openclaw agents add <name>    # e.g., openclaw agents add alice

# Route by Signal UUID (not phone number — more private)
# The UUID appears in `openclaw pairing list signal` when someone messages the bot
```

Config for routing:

```json5
{
  agents: {
    list: [
      { id: "main", default: true },
      { id: "alice" },
    ],
  },
  bindings: [
    {
      agentId: "alice",
      match: { channel: "signal", peer: { kind: "direct", id: "uuid:<alice-uuid>" } },
    },
  ],
}
```

**Flow to add a new user:**

1. Create their agent: `openclaw agents add <name>`
2. They message the bot on Signal → receive a pairing code
3. Check `openclaw pairing list signal` → note their UUID
4. Add a binding routing their UUID to their agent
5. Approve pairing: `openclaw pairing approve signal <CODE>`
6. Optionally create a SOUL.md for their agent

**Why route by UUID instead of phone number:** The sender's phone number is not needed in the config. Signal identifies users by UUID internally. Routing by UUID avoids storing family members' phone numbers in config files.

#### Signal pairing approval

Currently **CLI only** — no dashboard UI for pairing approval:

```bash
openclaw pairing list signal
openclaw pairing approve signal <CODE>
```

#### Signal bot registration — phone number is mandatory

Signal requires a phone number to register. There is no way to create a Signal bot without one. This is a Signal design decision (phone number = identity).

**Approaches:**

| Method | Privacy | Cost | Notes |
|--------|---------|------|-------|
| **Dedicated prepaid SIM** (recommended) | Best | ~5-10 EUR one-time | Completely separate from personal number. Recommended. |
| **eSIM / virtual number** | Good | ~3-5 EUR/mo | No physical SIM needed. Services like Hushed, MySudo. Verify it can receive SMS. |
| **Google Voice / VoIP** | Moderate | Free | May not work — Signal blocks many VoIP numbers |
| **Personal number** | Bad | Free | Registering de-auths your personal Signal app. Do NOT use. |

**Always recommend dedicated prepaid SIM** — cheapest, most private, no risk to personal Signal.

---
