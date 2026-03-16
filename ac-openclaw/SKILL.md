---
name: ac-openclaw
description: >
  Install, configure, and maintain OpenClaw (personal AI assistant) on a VPS or local machine.
  Triggers: "install openclaw", "setup openclaw", "bootstrap openclaw", "deploy openclaw",
  "self-hosted AI assistant", "personal AI on server", "openclaw maintenance", "update openclaw",
  "openclaw backup". Covers server provisioning, OS hardening, model configuration, messaging
  channel integration, secure remote access, backups, and ongoing maintenance.
compatibility: macOS/Linux, any AI coding agent (Claude Code, Codex, Copilot, Gemini CLI, Cursor, etc.)
metadata:
  version: 0.0.1
  subagent_safe: false
  last_research_date: "2026-03-14"
---

# Bootstrap OpenClaw

Interactive, step-by-step guide to install [OpenClaw](https://github.com/openclaw/openclaw) — a self-hosted personal AI assistant that connects to your messaging apps (Signal, WhatsApp, Telegram, Discord, Slack, and 20+ more).

> **OpenClaw** was originally published in November 2025 by Peter Steinberger as "Clawdbot", renamed "Moltbot" on 2026-01-27 (Anthropic trademark), then "OpenClaw" on 2026-01-30. MIT-licensed. 247k+ GitHub stars as of 2026-03.

## Versions (as of 2026-03-14)

| Component | Version | Notes |
|-----------|---------|-------|
| OpenClaw | v2026.3.13 (stable, 2026-03-14) | Releases use `vYYYY.M.D` scheme |
| Node.js | 24.14.0 LTS "Krypton" (2026-03-05) | Minimum: >=22.16; recommended: 24 LTS |
| signal-cli | v0.14.1 (2025-03-08) | Requires Java 25+; **no official ARM64 native binary** — use JVM variant on aarch64 |
| Tailscale | Latest stable | Free Personal plan (3 users, 100 devices). Serve = free. Funnel = Premium only ($18/user/mo) |
| Ollama | Latest stable | Native ARM64 support. CPU-only unless the server has a GPU |
| Caddy | Latest stable | Alternative to Tailscale for HTTPS reverse proxy |
| Ubuntu | 24.04 LTS | Recommended OS (works on any provider or local machine) |

> **When running this skill:** Web-search for latest versions first. OpenClaw releases daily. signal-cli and Node.js update less frequently.

## Dependencies

Standalone. No dependencies on other skills.

## Why OpenClaw (vs. ChatGPT / Gemini directly)

Talking to OpenClaw on Signal feels the same as messaging ChatGPT — until you configure what makes it different:

| Capability | ChatGPT / Gemini | OpenClaw |
|---|---|---|
| **Proactive behavior** | Waits for you | Heartbeat wakes every ~30 min: checks email, calendar, alerts you |
| **Cron jobs** | None | Scheduled tasks: daily news brief at 7am, weekly report, etc. |
| **System integration** | Limited plugins | Direct access: Gmail, Calendar, GitHub, Obsidian, smart home, Spotify |
| **Multi-agent** | One assistant | Different agents per contact/channel, each with own personality and memory |
| **Data privacy** | Cloud-only | Runs on your machine — data never leaves your infra |
| **Model choice** | Locked to vendor | Any model (Claude, GPT, Gemini, local Ollama) — rotate or fallback |
| **Custom skills** | GPTs (limited) | 13,000+ community skills + write your own in markdown |
| **Always-on** | Session-based | Daemon with persistent memory across conversations |

**To get value beyond "just another chatbot"**, configure at least one of:

- **Heartbeat** — proactive monitoring (email triage, calendar reminders)
- **Cron jobs** — scheduled automation (morning briefing, daily backup reports)
- **Multi-agent routing** — different personalities for different contacts ([`references/multi-agent-routing.md`](references/multi-agent-routing.md))
- **Tool integrations** — Gmail, Calendar, GitHub, Obsidian, Home Assistant

Without these, OpenClaw is indeed just a passthrough to an LLM API. The value is in the integrations and automation.

## When NOT to Use

- User wants to install a **different** AI assistant (not OpenClaw)
- User already has OpenClaw running and needs help with **configuration changes only** (point them to [docs.openclaw.ai](https://docs.openclaw.ai/) instead)
- User wants a managed/hosted OpenClaw (point them to [ClawHost](https://github.com/bfzli/clawhost) or similar)

## Compatibility

This skill is designed to work with **any AI coding agent**:

- **Claude Code** — use `AskUserQuestion` tool for interactive Q&A
- **Codex** — present questions inline, wait for user input
- **GitHub Copilot** — present questions inline, wait for user input
- **Gemini CLI** — present questions inline, wait for user input
- **Cursor / Windsurf / other** — present questions inline, wait for user input

Adapt question delivery to whatever interaction model the agent supports. The key rule is: **ask one question at a time, wait for the answer, then proceed.**

## Workflow Overview

```
 1. Gather requirements (server, model, channels, security)
 2. Plan (present full plan, get approval)
 3. Provision server (or confirm local machine)
 4. Harden OS
 5. Install OpenClaw
 6. Configure model provider
 7. Set up secure remote access (Tailscale or Caddy)
 8. Connect messaging channels
 9. Post-install hardening & verification
10. Social media integrations (optional)
11. Additional integrations & next steps
12. Wrap up + suggest retrospective to self-improve this skill
```

**Cardinal rule:** Ask ONE question at a time. Never dump a wall of questions. Wait for the user's answer before proceeding.

---

## Phase 1: Gather Requirements

Ask these questions **one at a time**, in order. Use the agent's questionnaire tool if available (e.g., `AskUserQuestion` in Claude Code). Provide sensible defaults based on cached data in [`references/`](references/).

### 1.1 Where will OpenClaw run?

```
Where will OpenClaw be installed?

a) Remote VPS (I'll provision a new server)          [DEFAULT]
b) Remote VPS (I already have a server — I'll give SSH access)
c) This machine (the one running the AI agent)
```

- If **(a)**: proceed to 1.2 (server provider).
- If **(b)**: ask for SSH connection details. **Password MUST be stored in `pass`** (the standard Unix password manager). Never accept copy-pasted passwords in chat. Guide:

  ```bash
  # User stores the password:
  pass insert servers/openclaw-vps
  # Agent retrieves it when needed:
  pass show servers/openclaw-vps
  ```

  Then ask for: hostname/IP, SSH port (default 22), username (default root).
- If **(c)**: confirm OS (`uname -a`), skip server provisioning, go to Phase 3.

### 1.2 Server provider

```
Which VPS provider? (or will you use a local machine?)

a) Hetzner Cloud
b) DigitalOcean
c) Linode / Akamai
d) Vultr
e) OVH / Scaleway
f) Other (I'll tell you which)
```

**Provider-specific guidance:**

- If the provider is **Hetzner**, this skill has cached specs and pricing — see [`references/hetzner-servers.md`](references/hetzner-servers.md). Use that to recommend a server type and datacenter.
- For **any other provider**: do a **web search** for `"<provider> VPS ARM64 pricing"` (or x86 if ARM64 is not available) to find current instance types and prices. Adapt the sizing recommendations in 1.4 to the provider's lineup.
- If **local machine**: skip to 1.4.

### 1.3 Server location

```
Where do you live? (determines closest datacenter for low latency)
```

**Do NOT present a hardcoded list of datacenters.** Instead:

- If the provider was already determined (1.2), **web-search** for their available regions and present the closest options to the user's location.
- If the provider has cached data in `references/` (e.g., Hetzner), use that.
- For any other provider, research dynamically.

### 1.4 Model strategy

This is critical — it determines server sizing. **Present the cost comparison FIRST, then ask.**

**Key insight: for a personal messaging bot, paid API is almost always cheaper AND better than self-hosting a model.** Make this case clearly:

| Approach | Server | Model cost | Total/mo | Quality |
|----------|--------|-----------|----------|---------|
| **BYOK only** (recommended) | CAX11 4 GB (~4.49 EUR) | Free tier or ~1-5 EUR | **~5-10 EUR** | Frontier |
| **Local 4B model** | CAX11 4 GB (~4.49 EUR) | Free | **~4.49 EUR** | Basic (barely usable) |
| **Local 8B model** | CAX31 16 GB (~14 EUR) | Free | **~14 EUR** | Good |
| **BYOK + local fallback** | CAX21 8 GB (~7 EUR) | Free tier or ~1-5 EUR | **~8-12 EUR** | Frontier + basic fallback |

> **WARNING: The "Server RAM" column for local models is the MINIMUM for the model to load.** In practice, Ollama needs significantly more RAM for the KV cache during inference — an 8B model with OpenClaw's full context window (system prompt + SOUL.md + conversation history) can require **~20 GB**, not the ~5-6 GB that model weights alone suggest. Always budget 2-3x the model weight size for actual inference.
>
> **Bottom line:** A CAX11 (~4.49 EUR/mo) + Gemini 2.5 Flash (free, 250 req/day) or a paid API (~$1-5/mo) gives you frontier-quality models for less than running a mediocre local model on an expensive server. Self-hosting only makes sense for privacy absolutists or offline use.
>
> **Reference:** See [OpenClaw Deploy Cost Guide](https://yu-wenhao.com/en/blog/2026-02-01-openclaw-deploy-cost-guide) for detailed cost breakdowns.

**Free tier API comparison (as of 2026-03):**

| Provider | Model | Free tier limits | Quality |
|----------|-------|-----------------|---------|
| **Gemini 2.5 Flash** | Best free option | 10 RPM / 250 RPD | Good |
| **Gemini 2.5 Pro** | Paid only | — | Very good |
| **Gemini 3 Flash** | Preview/limited | Stricter limits | Good |
| **OpenAI GPT-3.5** | Only free model | 3 RPM (unusable) | Outdated |
| **Anthropic Haiku** | Paid only | — | Good ($0.25/1M tokens) |

Then ask:

```
For a personal messaging bot, a paid API on a small cheap server gives
better quality for less money than self-hosting a model on a big server.

How will you provide the AI model?

a) BYOK — API Key only (cheapest server, best models)          [DEFAULT]
   → Gemini 2.5 Flash free (250 msg/day) or paid (~$1-5/mo)
b) BYOK + local Ollama fallback (needs more RAM for fallback)
   → Best of both but server costs more
c) Local model only (needs expensive server, lower quality)
   → Only recommended for privacy/offline requirements
```

**If local model chosen:** The sizing table above shows minimum RAM for weights only. For actual inference with OpenClaw's context, multiply by 2-3x. Web-search for current Ollama memory requirements before recommending a server size.

**Provider resize note:** When recommending a server size, inform the user whether the provider supports upgrade/downgrade without reinstalling. This reduces decision anxiety — the user isn't locked in. For Hetzner: "Hetzner supports both upgrades and downgrades from the console or CLI. It requires a brief restart (~1 minute) but no data loss or reinstallation. You can start with CAX21 and downgrade to CAX11 later if you don't need the RAM." For other providers: web-search for their resize policy.

**Instance availability note:** ARM instances (CAX series on Hetzner) can be temporarily sold out in specific datacenters. When recommending a server type + location, warn the user this can happen and suggest alternatives:

1. Try another datacenter in the same country (e.g., `fsn1` instead of `nbg1` — both in Germany, negligible latency difference)
2. Use the next closest region (e.g., Helsinki for a European user — adds ~20-30ms, imperceptible for a messaging bot)
3. Wait a few days — providers restock ARM capacity regularly

For Hetzner specifically: web-search or run `hcloud server-type describe cax21` to check current availability per location before recommending one.

**Confirmation step (when local model + small server):** If the user chose option (b) or (c) and the server has ≤ 8 GB RAM, explicitly confirm the specific model before moving on. Example for 4 GB:

```
On CAX11 (4 GB RAM), the only local model that fits is Qwen 3 4B (~3 GB).
It handles basic Q&A but has limited reasoning — serviceable as a fallback
when your BYOK provider is down or rate-limited.

Install Ollama with Qwen 3 4B as your local fallback? (yes/no)
If no: we can skip Ollama or upgrade the server (CAX21 = 8 GB, ~7-8 EUR/mo → 8B models).
```

Do NOT silently move on after the user picks a model strategy. The user must confirm what will actually be installed.

### 1.5 OpenClaw capabilities — tool use

This question affects server sizing (Docker overhead) and security (sandboxing). Ask it **before** channels and security.

```
What will you use OpenClaw for?

a) Chat only — text conversations via messaging apps              [DEFAULT]
   → No special requirements.

b) Chat + tools — shell commands, code execution, file operations
   → Docker sandboxing strongly recommended for safety.
   → Adds ~200-500 MB RAM overhead (tight on 4 GB with Ollama).

c) Chat + tools + agents — autonomous multi-step tasks
   → Docker sandboxing required. More RAM headroom recommended.
```

**If (b) or (c):** Flag the RAM constraint if using Ollama on a small server. Docker daemon + containers consume ~200-500 MB. On CAX11 (4 GB) already running Ollama (~3 GB), sandboxing may not fit — warn the user and suggest either dropping Ollama or upgrading the server.

**Carry the answer forward** to § 1.7 (security) — Docker sandboxing recommendation adapts based on tool-use intent.

### 1.6 Which messaging channels?

These are for **private two-way chat** with your assistant (like texting a friend). Not social media posting.

```
Which messaging channel do you want to connect?

Recommended (ranked by privacy):
a) Signal          — E2E encrypted, open source                          [DEFAULT]
   ⚠️ Requires a DEDICATED phone number (registering de-auths your main Signal app)
b) Telegram        — easiest setup (bot token from @BotFather), no phone needed
c) WhatsApp        — E2E encrypted, needs real mobile number, Meta-owned
d) Matrix          — E2E encrypted, self-hosted, decentralized (plugin)

Also available:
e) Discord         (bot token + gateway intents, no E2E)
f) Slack           (workspace app, no E2E)
g) iMessage        (BlueBubbles, macOS server required)
h) IRC, Microsoft Teams, Google Chat, LINE, Mattermost, and more (plugins)

Which one? (start with one, you can add more later)
```

**Suggest starting with ONE channel.** Get it working first, then add more if needed.

For each selected channel, the skill will guide setup in Phase 8. See [`references/channel-setup.md`](references/channel-setup.md) for cached setup details.

### 1.7 Security preferences

**Principle: default to maximum security.** Present the most secure setup as the default. If a security measure doesn't fit the user's situation (e.g., RAM constraints), explain clearly why you're suggesting to disable it, what the trade-offs are, and what risk the user accepts.

Present the full default security stack:

```
Here's what will be enabled by default:

- UFW firewall (only ports 22, 80, 443)
- Fail2Ban for SSH brute-force protection
- SSH key-only auth (password auth disabled)
- Unattended security updates
- OpenClaw bound to localhost + reverse proxy for remote access
- Non-root user for OpenClaw
- Docker sandboxing for tool execution (isolates shell/code in containers)
- Custom SSH port (2222) to reduce bot noise

Any of these you'd like to change? (or Enter to proceed with all defaults)
```

**Then adapt based on context — explain trade-offs honestly when suggesting a downgrade:**

- **If chat-only (§ 1.5a):** "Docker sandboxing is included by default, but since you chose chat-only (no tools/code execution), there's nothing to sandbox right now. Removing it saves ~200-500 MB RAM and reduces complexity. You can always add it later if you enable tools. Want to skip Docker sandboxing for now?"

- **If tools/agents (§ 1.5b/c) on a small server with Ollama:** "Docker sandboxing is critical for your setup — it prevents a misbehaving tool or prompt injection from damaging your server. However, on CAX11 (4 GB) with Ollama already using ~3 GB, Docker's ~200-500 MB overhead makes it very tight. Options: (a) keep sandboxing and drop Ollama, (b) keep both and risk OOM under load, (c) upgrade to CAX21 (8 GB, ~7-8 EUR/mo) to fit everything comfortably. Which do you prefer?"

- **If tools/agents on a server with enough RAM:** Keep Docker sandboxing enabled, no downgrade needed.

**Additional options (only if user asks):**

- Disk encryption (LUKS) — strongest data-at-rest protection, but adds complexity: requires `dropbear-initramfs` for remote unlock after every reboot. Recommend only for high-sensitivity data.

### 1.8 Remote access to the web dashboard

The user needs to know how they'll access the OpenClaw dashboard from their phone/laptop. This choice affects the plan (domain needed? Cloudflare account? Tailscale on all devices?). Ask it now, execute it in Phase 7.

**Set-and-forget guarantee:** Reassure the user that whichever method they choose, it runs as a systemd service. Once installed, the server just runs — no manual reverse proxy, no SSH tunnel each time, no port forwarding. Open a URL and you're in.

```
How do you want to access the OpenClaw web dashboard from your phone/laptop?
All options run as permanent background services — once set up, there's
nothing to do. Just open the URL.

a) Cloudflare Tunnel + Zero Trust (recommended)
   → Access from any browser/phone, no app install needed
   → Free. Requires a domain name + Cloudflare account
   → Auth via Google/GitHub/email OTP before reaching the dashboard

b) Tailscale Serve (most secure)
   → Private mesh network, zero public exposure
   → Free. BUT: requires Tailscale app on EVERY device (laptop, phone)
   → ⚠️ May conflict with existing VPNs (WireGuard, etc.) — ask the user first
   → Best if you're already a Tailscale user or have no other VPN

c) Caddy reverse proxy + password (simplest)
   → Direct HTTPS with Let's Encrypt, password-protected
   → Requires a domain name. No extra accounts needed
   → Less secure: password-only auth, exposed to internet
```

| Method | Install app on phone? | Domain needed? | Cost | Security |
|--------|----------------------|---------------|------|----------|
| **Cloudflare Tunnel** | No | Yes | Free | High (Zero Trust identity check) |
| **Tailscale Serve** | Yes (Tailscale app) | No | Free | Highest (not on internet at all) |
| **Caddy + password** | No | Yes | Free | Medium (password-only) |

**If the user chose Tailscale, immediately ask about existing VPNs:**

```
Do you have any other VPN running on your devices (WireGuard, OpenVPN,
corporate VPN, etc.)?

Tailscale can conflict with other VPNs — especially WireGuard-based ones.
They compete for the macOS/iOS network extension slot and may block each
other's traffic. On Linux/Android it's less problematic.

If yes: you'll need to avoid running both simultaneously. Toggle one off
before using the other. If that's a dealbreaker, consider Cloudflare
Tunnel (option a) instead — it doesn't require a VPN app on your devices.
```

**Carry the answer forward** to Phase 7 for execution.

---

## Phase 2: Present the Plan

After gathering all answers, present a **complete plan** for user approval:

```markdown
## Installation Plan

**Server:** <provider> <instance type> (<vCPU>, <RAM>, <SSD>) in <location>
**OS:** Ubuntu 24.04 LTS (<arch>)
**Model:** <BYOK provider or Ollama model>
**Capabilities:** <chat-only / tools / tools + agents>
**Channels:** <chosen channel(s)>
**Security:** UFW + Fail2Ban + SSH keys + unattended-upgrades <+ Docker sandboxing if tools>
**Remote access:** <chosen method from § 1.8> (runs as systemd service — set and forget)
**Estimated cost:** <server cost/mo> + <API usage if BYOK>

Steps:
1. Provision server (or connect to existing / confirm local)
2. Initial OS setup (user, SSH keys, firewall)
3. Install Node.js 24 + OpenClaw
4. Configure model provider
5. Set up secure remote access
6. Connect messaging channel(s)
7. Run security audit
8. Test end-to-end

Proceed? (yes/no)
```

Wait for approval. If the user wants changes, adjust and re-present.

---

## Phases 3–12: Installation & Configuration

Detailed step-by-step instructions for each phase live in reference files. Load them as you reach each phase — don't front-load everything into context.

| Phase | Reference | Summary |
|-------|-----------|---------|
| **3. Provision Server** | [`references/installation-phases.md`](references/installation-phases.md) § Phase 3 | Create VPS or configure existing server/local machine |
| **4. Harden the OS** | [`references/installation-phases.md`](references/installation-phases.md) § Phase 4 | UFW, fail2ban, SSH hardening, unattended upgrades |
| **5. Install OpenClaw** | [`references/installation-phases.md`](references/installation-phases.md) § Phase 5 | Node.js 24, OpenClaw, gateway config, dashboard pairing |
| **6. Configure Model** | [`references/installation-phases.md`](references/installation-phases.md) § Phase 6 | BYOK API keys, local Ollama, or hybrid setup |
| **7. Remote Access** | [`references/installation-phases.md`](references/installation-phases.md) § Phase 7 | Cloudflare Tunnel (recommended), Tailscale Serve, or Caddy |
| **8. Messaging Channels** | [`references/channel-setup.md`](references/channel-setup.md) | Signal, WhatsApp, Telegram, Discord — one at a time |
| **9. Post-Install** | [`references/installation-phases.md`](references/installation-phases.md) § Phase 9 | Security audit, systemd service, Docker sandboxing |
| **10. Social Media** | [`references/social-media.md`](references/social-media.md) | Optional — only if user explicitly wants posting |
| **11. Integrations** | [`references/installation-phases.md`](references/installation-phases.md) § Phase 11 | Backups, tool integrations, heartbeat, cron jobs |
| **12. Wrap Up** | [`references/installation-phases.md`](references/installation-phases.md) § Phase 12 | Final verification, suggest retrospective |

**Key rules for all phases:**

- **Fetch OpenClaw docs before Phase 5** (see § When Using This Skill below)
- **Store every generated secret in `pass` immediately** — gateway tokens, API keys, passwords
- **Set `gateway.mode` and `allowedOrigins` before starting the gateway** (Phase 5.3)
- **Warn about device pairing** before the user opens the dashboard (Phase 5.5)
- **Always recommend dedicated prepaid SIM for Signal** — never use a personal number

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
| Gateway unreachable | `openclaw status`, check `systemctl status openclaw` |
| Channel not receiving messages | `openclaw channels status --probe` |
| Signal: daemon not reachable | `pgrep -af signal-cli`, check signal-cli HTTP port |
| WhatsApp: QR expired | Re-run `openclaw channels login --channel whatsapp` |
| Tailscale: can't reach dashboard | `tailscale status`, verify both devices on same tailnet |
| Docker bypasses firewall | Add DOCKER-USER iptables rules (see [`references/security-hardening.md`](references/security-hardening.md) § Docker + Firewall) |
| API key rate limited | OpenClaw auto-rotates keys; add backup keys with `_1`, `_2` suffixes |
| High memory usage (Ollama) | Check model size vs RAM; use smaller quantization or smaller model |
| SSH custom port not working (Ubuntu 24.04) | Ubuntu 24.04 uses systemd socket activation. Do NOT put `Port` directives in `sshd_config` — use a systemd socket override at `/etc/systemd/system/ssh.socket.d/override.conf` with explicit `0.0.0.0:PORT` and `[::]:PORT` format. Bare port numbers (e.g., `ListenStream=2222`) don't bind IPv4. Always keep the old port open in UFW until the new port is confirmed working from outside. |
| Locked out of SSH | Use `hcloud server enable-rescue <name> --ssh-key <key>` then `hcloud server reset <name>` to boot into rescue mode. Mount disk at `/mnt` via `mount /dev/sda1 /mnt`, fix configs, unmount, disable rescue, reset. |

---

## When Using This Skill

### If online (web search available)

Before starting, refresh cached data AND fetch OpenClaw docs. This is non-negotiable — the skill caches configs and commands but OpenClaw releases daily and configs change.

**Fetch official docs (do this BEFORE Phase 5, not during debugging):**

1. `WebFetch https://docs.openclaw.ai/install` — installation steps, post-install config
2. `WebFetch https://docs.openclaw.ai/gateway/security` — auth modes, allowedOrigins, token setup, Control UI pairing
3. `WebFetch https://docs.openclaw.ai/gateway/tailscale` — Tailscale Serve config (if user chose Tailscale)
4. `WebFetch https://docs.openclaw.ai/channels/<channel>` — channel-specific setup (for Phase 8)

**Refresh version data via web search:**

1. `openclaw latest version release notes` — check for breaking changes vs cached v2026.3.13
2. `signal-cli latest release ARM64` — check if native aarch64 build is now available
3. `<provider> VPS pricing` — verify current prices for the user's chosen provider
4. `tailscale pricing free plan serve` — confirm Serve is still free
5. Update the `references/` files if any data changed. Note the new `last_updated` date.

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
