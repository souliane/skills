# OpenClaw Server Configuration — Template

> Save a copy of this with real values in your personal agent memory/config after installation.
> Do NOT put real IPs, phone numbers, or secrets in this template.

## Connection

| Key | Value |
|-----|-------|
| Provider | `<provider> (<instance type>)` |
| Location | `<datacenter>` |
| IP | `<server IP>` |
| SSH port | `<port>` |
| SSH key | `<path to key>` |
| SSH user | `openclaw` |

## Services

| Service | Unit | Notes |
|---------|------|-------|
| OpenClaw gateway | `openclaw.service` | Wrapper reads keys from `pass` |
| Ollama | `ollama.service` | Local model fallback |
| Tailscale Serve | active | If chosen as remote access method |
| Docker | `docker.service` | If sandboxing enabled |
| Fail2Ban | `fail2ban.service` | SSH brute-force protection |

## Models

| Priority | Model | Provider |
|----------|-------|----------|
| Primary | `<model>` | `<provider>` |
| Fallback | `<model>` | Ollama (local) |

## Secrets in `pass`

- `openclaw/<provider>-key` — API key
- `openclaw/gateway-token` — dashboard auth

## Backups

| Method | Schedule | Notes |
|--------|----------|-------|
| Local tar.gz | Daily cron | `~/backups/` on server |
| GitHub push | Daily cron | Deploy key to private repo |
| Provider snapshot | Weekly | Full server image |

## Signal (if configured)

| Key | Value |
|-----|-------|
| Bot number | `<dedicated number>` |
| signal-cli version | Check `/opt/signal-cli-*/` |
| libsignal version | Must match: `ls /opt/signal-cli-*/lib/libsignal-client-*.jar` |
