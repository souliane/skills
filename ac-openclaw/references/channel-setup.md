# OpenClaw Channel Setup Reference

> **Last updated:** 2026-03-14
> **Source:** [docs.openclaw.ai/channels](https://docs.openclaw.ai/channels)

## All Supported Channels (24+)

### Built-in Channels

| Channel | Library | Auth method | Phone needed | Difficulty |
|---------|---------|-------------|-------------|------------|
| Signal | signal-cli | Phone number + SMS/QR | Yes (dedicated recommended) | Medium |
| WhatsApp | Baileys | QR code from phone | Yes (real mobile, no VoIP) | Easy |
| Telegram | grammY | Bot token from @BotFather | No | Easiest |
| Discord | discord.js | Bot token + gateway intents | No | Easy |
| Slack | Bolt | App token + bot token | No | Medium |
| Google Chat | — | Service account | No | Medium |
| IRC | built-in | Server + nick | No | Easy |
| BlueBubbles/iMessage | REST API | macOS server required | Apple ID | Hard |

### Plugin Channels (install separately)

Feishu, LINE, Matrix, Mattermost, Microsoft Teams, Nextcloud Talk, Nostr, Synology Chat, Tlon, Twitch, Zalo, Zalo Personal.

Install plugins with:

```bash
openclaw plugins enable <channel-name>
```

---

## Signal — Detailed Setup

### Prerequisites

- Phone number (can receive SMS once, for verification)
- **Dedicated number recommended** — registering with signal-cli can de-auth your main Signal app
- signal-cli binary: native Linux build or JVM variant (needs Java 25+)
- Gateway talks to signal-cli over HTTP JSON-RPC + SSE

### ARM64/aarch64 — Build libsignal from source (REQUIRED)

There is **no pre-built ARM64 `libsignal_jni.so`** as of 2026-03. The JVM variant of signal-cli WILL NOT WORK without this native library. You MUST build it from source.

**Do NOT use `signal-cli-rest-api` Docker container** — it exposes a REST API, but OpenClaw expects JSON-RPC + SSE. They are incompatible.

```bash
# Prerequisites
sudo apt-get install -y openjdk-25-jre-headless build-essential cmake libclang-dev protobuf-compiler
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"

# Download signal-cli JVM variant
SIGNAL_CLI_VERSION="0.14.0"
curl -fsSL "https://github.com/AsamK/signal-cli/releases/download/v${SIGNAL_CLI_VERSION}/signal-cli-${SIGNAL_CLI_VERSION}.tar.gz" -o /tmp/signal-cli.tar.gz
sudo tar xf /tmp/signal-cli.tar.gz -C /opt
sudo ln -sf /opt/signal-cli-${SIGNAL_CLI_VERSION}/bin/signal-cli /usr/local/bin/signal-cli
rm /tmp/signal-cli.tar.gz

# Build libsignal native JNI library (~3 min on CAX21)
git clone --depth 1 https://github.com/signalapp/libsignal.git /tmp/libsignal
cd /tmp/libsignal/java
cargo build --release -p libsignal-jni

# Install the .so where Java can find it
sudo mkdir -p /usr/java/packages/lib
sudo cp /tmp/libsignal/target/release/libsignal_jni.so /usr/java/packages/lib/

# Clean up build artifacts (saves ~2 GB)
rm -rf /tmp/libsignal
# Optionally remove Rust if not needed: rustup self uninstall

# Verify
signal-cli --version
```

> **Build failures:** If cargo fails, check: (1) `libclang-dev` installed? (2) `protobuf-compiler` installed? (3) Enough RAM? (4 GB minimum during build). These are the three dependencies that cause failures.

### Registration Paths

**Path A — QR Link (recommended if you have Signal on another device):**

```bash
signal-cli link -n "OpenClaw"
# Scan QR with Signal: Settings > Linked Devices > Link a Device
```

**Path B — SMS registration (dedicated bot number):**

1. Get captcha: open `https://signalcaptchas.org/registration/generate.html`
2. Complete captcha, extract `signalcaptcha://...` URL
3. Register immediately (tokens expire fast):

   ```bash
   signal-cli -a +<NUMBER> register --captcha 'signalcaptcha://...'
   ```

4. Enter SMS code:

   ```bash
   signal-cli -a +<NUMBER> verify <CODE>
   ```

### Key Storage

- Account keys: `~/.local/share/signal-cli/data/` — **back these up**
- OpenClaw config: `~/.openclaw/openclaw.json`

### DM Pairing

Default: unknown senders get a pairing code (expires in 1 hour):

```bash
openclaw pairing list signal
openclaw pairing approve signal <CODE>
```

### Common Issues

- Captcha token expires quickly (~60 seconds) — solve and register immediately
- ARM64: MUST build libsignal from source (see ARM64 section above). No pre-built binary exists. Do NOT use signal-cli-rest-api Docker container (wrong API protocol)
- `channels.signal.account` must be a JSON string (`"+33..."`) not a number — `openclaw config set` may parse `+33...` as a number. Fix with Python: `cfg['channels']['signal']['account'] = '+33...'`
- After multiple registration attempts, Signal may rate-limit. Wait 24h or try voice verification
- Signal identity keys in `~/.local/share/signal-cli/data/` — back these up. Losing them means re-registering the number
- Daemon check: `pgrep -af signal-cli`
- Logs: `grep -i "signal" "/tmp/openclaw/openclaw-$(date +%Y-%m-%d).log" | tail -20`

---

## WhatsApp — Detailed Setup

### Prerequisites

- Real mobile phone number (VoIP/virtual numbers get blocked)
- WhatsApp installed on a phone with that number
- QR code scanning capability

### Setup

```bash
openclaw channels login --channel whatsapp
# QR code appears (60-second window)
# Phone: WhatsApp > Settings > Linked Devices > Link a Device > Scan
```

### Credentials

- Stored at: `~/.openclaw/credentials/whatsapp/<accountId>/creds.json`
- Session may need re-pairing after ~14 days of disconnection

### Phone Number Format

Include country code with `+` prefix: `+1` (US), `+44` (UK), `+33` (FR), `+32` (BE), `+31` (NL), `+49` (DE), `+40` (RO).

---

## Telegram — Detailed Setup

### Prerequisites

- Telegram account
- That's it. Simplest channel.

### Create Bot

1. Open Telegram, message `@BotFather`
2. `/newbot` → choose name → choose username (must end in `bot`)
3. Copy the HTTP API token

### Optional BotFather Settings

- `/setjoingroups` → Enable (for group use)
- `/setprivacy` → Disable (to read all group messages)
- `/setdescription` → Set bot description
- `/setuserpic` → Set bot avatar

### Security

- Token = full bot control. If leaked: `/revoke` in BotFather
- Prefer `TELEGRAM_BOT_TOKEN` env var over config file

---

## Discord — Detailed Setup

### Prerequisites

- Discord account
- A server where you have admin permissions

### Create Bot

1. [Discord Developer Portal](https://discord.com/developers/applications) → New Application
2. Bot tab → Reset Token → copy
3. Privileged Gateway Intents:
   - **Message Content Intent** (required)
   - **Server Members Intent** (recommended)
   - Presence Intent (optional)
4. OAuth2 > URL Generator:
   - Scopes: `bot`
   - Permissions: View Channels, Send Messages, Read Message History, Embed Links, Attach Files
   - Open generated URL to invite bot

### Security

- Token = full bot control. Use `DISCORD_BOT_TOKEN` env var
- Only grant minimum permissions needed

---

## Slack — Detailed Setup

### Prerequisites

- Slack workspace admin access
- Socket Mode (recommended) or public URL for Events API

### Create App

1. [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From Scratch
2. OAuth & Permissions → Bot Token Scopes: `chat:write`, `channels:history`, `groups:history`, `im:history`, `mpim:history`, `app_mentions:read`
3. Install to Workspace → copy Bot User OAuth Token (`xoxb-...`)
4. Socket Mode → Enable → Generate App-Level Token (`xapp-...`) with `connections:write`
5. Event Subscriptions → Enable → Subscribe to: `message.channels`, `message.groups`, `message.im`, `app_mention`

### Config

```jsonc
{
  "channels": {
    "slack": {
      "enabled": true,
      "botToken": "xoxb-...",
      "appToken": "xapp-...",
      "dmPolicy": "pairing"
    }
  }
}
```
