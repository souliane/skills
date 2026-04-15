# OpenClaw Channel Setup Reference

**Last updated:** 2026-03-14
**Source:** [docs.openclaw.ai/channels](https://docs.openclaw.ai/channels)

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
SIGNAL_CLI_VERSION="0.14.2"
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

**Build failures:** If cargo fails, check: (1) `libclang-dev` installed? (2) `protobuf-compiler` installed? (3) Enough RAM? (4 GB minimum during build). These are the three dependencies that cause failures.

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

### Troubleshooting: Signal Registration Lost

**Symptom:** Gateway logs show `signal-cli: User +<NUMBER> is not registered.` in a crash loop. Contacts see "This person is not on Signal."

**Observed failure mode:** After an unclean shutdown, reboot, or partial upgrade, signal-cli's local state can diverge from the account state the gateway expects. Do not assume the account is truly deregistered until you verify it. Inactivity alone is not enough evidence.

**Diagnosis:**

```bash
# 1. Check whether the account is still registered on Signal's servers
signal-cli -a +<NUMBER> getUserStatus +<NUMBER>
# If output shows true, do NOT wipe local state yet

# 2. Check for recent reboots / unclean shutdowns
last reboot | head -10

# 3. Inspect gateway logs before changing anything
journalctl --user -u openclaw.service -n 50 --no-pager
# or: sudo journalctl -u openclaw.service -n 50 --no-pager
```

**Recovery order (least destructive first):**

```bash
# If you run OpenClaw as a user service
systemctl --user restart openclaw.service

# If you run OpenClaw as a system service
sudo systemctl restart openclaw.service
```

If `getUserStatus` still returns `true`, restore the latest backup of `~/.local/share/signal-cli/data/` first, then restart the gateway again. Only move to re-registration after both of these are true:

- `signal-cli -a +<NUMBER> getUserStatus +<NUMBER>` returns `false`
- restarting the gateway and restoring the latest backup did not recover the account

**Fix — full re-registration (destructive, last resort):**

```bash
# 1. Stop the gateway
systemctl --user stop openclaw.service
# or: sudo systemctl stop openclaw.service

# 2. Clear stale local data (REQUIRED — otherwise "AlreadyVerifiedException")
signal-cli -a +<NUMBER> deleteLocalAccountData

# 3. Get fresh captcha from https://signalcaptchas.org/registration/generate.html
# 4. Register (strip the "signalcaptcha://" prefix)
signal-cli -a +<NUMBER> register --captcha 'signal-hcaptcha.TOKEN...'

# 5. Verify with SMS code IMMEDIATELY (codes expire fast)
signal-cli -a +<NUMBER> verify <CODE>

# 6. Confirm registration succeeded
signal-cli -a +<NUMBER> getUserStatus +<NUMBER>
# Must show: +<NUMBER>: true

# 7. Restart gateway
systemctl --user start openclaw.service
# or: sudo systemctl start openclaw.service
```

**Gotchas during re-registration:**

| Problem | Cause | Fix |
|---------|-------|-----|
| `AlreadyVerifiedException` on register | Stale local data thinks it's registered | Only after confirming `getUserStatus` is `false`, run `deleteLocalAccountData` and re-register |
| `StatusCode: 499` on verify | Code expired or too many attempts | Re-register with a new captcha + verify immediately |
| "This person is not on Signal" after fix | Identity key changed; contact's app cached old key | Contact must delete the old conversation and start a new one |

**Prevention:** Back up `~/.local/share/signal-cli/data/` regularly, use graceful service shutdown with `TimeoutStopSec=30`, and avoid ad-hoc force kills during upgrades.

### Updating signal-cli

```bash
# 1. Check current and latest version
signal-cli --version
curl -sL "https://api.github.com/repos/AsamK/signal-cli/releases/latest" | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])"

# 2. Stop gateway
systemctl --user stop openclaw.service
# or: sudo systemctl stop openclaw.service

# 3. Download and install (JVM variant — use the plain .tar.gz, not -Linux-native or -Linux-client)
VERSION="0.14.2"
curl -sL "https://github.com/AsamK/signal-cli/releases/download/v${VERSION}/signal-cli-${VERSION}.tar.gz" -o /tmp/signal-cli-${VERSION}.tar.gz
sudo tar xf /tmp/signal-cli-${VERSION}.tar.gz -C /opt/
sudo ln -sf /opt/signal-cli-${VERSION}/bin/signal-cli /usr/local/bin/signal-cli
signal-cli --version

# 4. Restart gateway
systemctl --user start openclaw.service
# or: sudo systemctl start openclaw.service
```

**Release asset naming:** The GitHub release has multiple tarballs. For JVM variant (ARM64/aarch64), use `signal-cli-<VERSION>.tar.gz` (plain). The `-Linux-native` variant is x86_64 only. The `-Linux-client` variant is for linked devices, not standalone registration.

**CRITICAL (ARM64): Rebuild libsignal after updating signal-cli.** The `libsignal_jni.so` native library must match the `libsignal-client-*.jar` version bundled with signal-cli. If you update signal-cli without rebuilding, you get `AssertionError: bad parameter type` in `SealedSessionCipher_DecryptToUsmc` and messages silently fail to decrypt. Check the jar version with `ls /opt/signal-cli-<VERSION>/lib/ | grep libsignal-client`, then rebuild from the matching tag:

```bash
# Find the required version
LIBSIGNAL_VER=$(ls /opt/signal-cli-*/lib/libsignal-client-*.jar | grep -oP '\d+\.\d+\.\d+' | tail -1)
# Rebuild
git clone --depth 1 --branch "v${LIBSIGNAL_VER}" https://github.com/signalapp/libsignal.git /tmp/libsignal
cd /tmp/libsignal/java && cargo build --release -p libsignal-jni
sudo cp /tmp/libsignal/target/release/libsignal_jni.so /usr/java/packages/lib/
rm -rf /tmp/libsignal
```

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
