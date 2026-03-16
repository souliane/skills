# OpenClaw Social Media Integrations — Reference

> **Last updated:** 2026-03-14
> **Sources:**
>
> - [openclaw-plugin-social](https://github.com/pepicrft/openclaw-plugin-social) (open source, 2026-02)
> - [Post Bridge + OpenClaw](https://www.post-bridge.com/openclaw) (2026-02)
> - [Publora + OpenClaw](https://publora.com/blog/connect-openclaw-ai-agent-social-media-publora) (2026-02)
> - [Genviral OpenClaw Skill](https://finance.yahoo.com/news/genviral-releases-openclaw-skill-automate-051000525.html) (2026-02)
> - [Composio Twitter MCP](https://composio.dev/toolkits/twitter/framework/openclaw) (2026)
> - [OpenClaw Security Risks — Bitsight](https://www.bitsight.com/blog/openclaw-ai-security-risks-exposed-instances) (2026-03)
> - [OpenClaw Privacy Concerns — TechXplore](https://techxplore.com/news/2026-02-openclaw-ai-agent-privacy-nightmare.html) (2026-02)

## Messaging Channels vs Social Media Posting

These are **two different things** in OpenClaw:

| Feature | Messaging channels | Social media posting |
|---------|-------------------|---------------------|
| **What** | Two-way chat: you DM the bot, it replies | One-way publishing: bot posts content to your profiles |
| **How** | Built-in channels (Signal, WhatsApp, etc.) | Plugins, skills, or third-party APIs |
| **Auth** | Bot tokens, QR pairing, phone numbers | OAuth apps, API keys, third-party schedulers |
| **Use case** | Interact with your AI assistant via messaging | Automate social media content creation & posting |
| **Risk** | Low (private conversations) | Higher (public posts under your identity) |

**Messaging channels** (Signal, WhatsApp, Telegram, Discord, Slack) let you **talk to** your OpenClaw assistant. They're built-in, well-tested, and secure by default. Signal is a **messaging channel**, not a social media platform — you use it to chat privately with your bot, not to post publicly.

**Social media integrations** let OpenClaw **post on your behalf** to platforms like X/Twitter, LinkedIn, Instagram, etc. These are community plugins or third-party services, not built-in. They carry additional risks because they can publish content publicly under your name.

**Some platforms are both messaging AND social media:**

- **Mastodon** — OpenClaw connects via the Matrix plugin (Mastodon supports ActivityPub). You can **both chat with the bot** (DMs) and have it **post to your timeline**. It's the most versatile recommended option.
- **Telegram** — Built-in messaging channel, but can also post to public Telegram channels (broadcast).
- **Discord** — Built-in messaging, but can also post to public server channels.

## Available Social Media Integration Methods

### 1. Third-Party Schedulers (Recommended)

Post to a scheduler API that fans out to multiple networks. Best approach for cross-posting without maintaining many auth setups.

| Service | Platforms | How it works | Cost |
|---------|-----------|-------------|------|
| [Post Bridge](https://www.post-bridge.com/openclaw) | Instagram, TikTok, YouTube, X, LinkedIn, Facebook, Threads, Bluesky, Pinterest | API-first, MCP server for OpenClaw | Freemium |
| [Publora](https://publora.com) | LinkedIn, X, Instagram, Threads, TikTok, YouTube, Facebook, Bluesky, Mastodon, Telegram | MCP server | Freemium |
| [Genviral](https://www.genviral.io) | TikTok, Instagram, YouTube, Facebook, Pinterest, LinkedIn | OpenClaw skill (42 API commands), video content focus | Freemium |

### 2. Direct API Plugins (Open Source)

| Plugin | Platforms | Notes |
|--------|-----------|-------|
| [openclaw-plugin-social](https://github.com/pepicrft/openclaw-plugin-social) | X/Twitter, LinkedIn, Mastodon, Bluesky | Open source, flexible scheduling, browser automation fallback |
| [Composio Twitter MCP](https://composio.dev/toolkits/twitter/framework/openclaw) | X/Twitter only | Managed auth, MCP integration |

### 3. Browser Automation (Last Resort)

OpenClaw can use its browser control to directly interact with social media websites. Not recommended — fragile, can trigger account bans, and is slow.

## Platform-by-Platform Assessment

### Recommended

| Platform | Why | Auth method | Dedicated account needed? |
|----------|-----|-------------|--------------------------|
| **Bluesky** | Open protocol (AT Protocol), API-friendly, no rate-limit hell, privacy-respecting | App password (no OAuth needed) | Recommended but not critical |
| **Mastodon** | Open source, federated, API-friendly, no algorithmic manipulation | OAuth app | Recommended |
| **LinkedIn** | Professional networking, good API | OAuth via scheduler | **Yes** — don't risk your main profile |
| **Telegram** | Already a built-in channel, can also post to public channels | Bot token | Already handled in channel setup |

### Use With Caution

| Platform | Why cautious | Auth method | Risks |
|----------|-------------|-------------|-------|
| **X / Twitter** | Aggressive rate limits, frequent API changes, costly API tiers, bot detection | OAuth 2.0 or API key ($100+/mo for posting access) | Account suspension, API cost, privacy (X collects data for AI training) |
| **Instagram** | No public posting API for personal accounts; requires Facebook Business account | Meta Business Suite OAuth | Account flagged as bot, ToS violation risk |
| **Facebook** | Complex API, Meta's aggressive data collection, frequent breaking changes | Meta Business Suite OAuth | Privacy nightmare, account lockouts |
| **TikTok** | API limited to business accounts, content review delays | TikTok for Business API | Limited personal-account support |

### Not Recommended

| Platform | Why avoid |
|----------|-----------|
| **Instagram (personal)** | No legitimate API for personal posting. All workarounds violate ToS and risk permanent ban |
| **Facebook (personal)** | Same as Instagram — no personal posting API. Business pages only |
| **Snapchat** | No public API for content posting |

## Security & Privacy Warnings

> **"OpenClaw is a huge security and privacy risk for the naive user"** — [Bitsight, 2026-03](https://www.bitsight.com/blog/openclaw-ai-security-risks-exposed-instances)

1. **Use dedicated accounts for social media.** Never connect your primary personal accounts. If OpenClaw is compromised, an attacker could post under your identity, read your DMs, or exfiltrate data.

2. **Prompt injection risk with social media.** Researchers at PromptArmor found that link previews in messaging apps can be used for indirect prompt injection against OpenClaw. Social media comments and replies are even more dangerous — they're untrusted input that could steer your agent.

3. **X/Twitter collects data for AI training.** Anything posted via their API may be used to train their models. Consider this before connecting.

4. **Meta platforms (Facebook, Instagram) have aggressive data collection.** Connecting OpenClaw gives Meta access to your agent's posting patterns and content.

5. **OAuth tokens are powerful.** A leaked social media OAuth token gives full account access. Store them securely (env vars or `pass`, never in config files).

## Setup Checklist (for any social media integration)

1. **Create a dedicated account** for the platform (don't use your personal one)
2. **Use a third-party scheduler** (Post Bridge, Publora) rather than direct API access
3. **Store all tokens/keys in `pass`** or environment variables
4. **Enable OpenClaw tool sandboxing** to limit what the agent can do
5. **Review posts before publishing** — set up approval workflows if the scheduler supports it
6. **Monitor for unauthorized posts** — check your social accounts regularly
7. **Use the most restrictive API scopes** possible (read-only where you just need monitoring)

## Quick Start: Bluesky (Simplest)

Bluesky is the easiest and safest social media to connect:

```bash
# Install the social plugin
openclaw plugins enable social

# Configure in openclaw.json:
# "social": {
#   "bluesky": {
#     "handle": "youraccount.bsky.social",
#     "appPassword": "<generate at bsky.app/settings/app-passwords>"
#   }
# }

# Or use a scheduler like Post Bridge for multi-platform
```

## Quick Start: X/Twitter via Composio MCP

```bash
# Enable Composio MCP server
openclaw plugins enable composio-twitter

# Follow Composio's auth flow to connect your X account
# Composio handles OAuth token management
```

> **Cost warning:** X/Twitter API Basic plan is $100/mo for write access (posting). Free tier is read-only. Consider if this cost is worth it for automated posting.
