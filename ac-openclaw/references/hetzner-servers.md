# Hetzner Cloud — CAX (ARM64/Ampere) Server Reference

> **One cached provider among several — not the default.** Start from
> [`provider-selection.md`](provider-selection.md), which holds the provider-agnostic method and
> a dated snapshot of other EU options. Use this file only once the user has chosen Hetzner.
>
> **Two caveats before recommending CAX:** (1) an ARM line can be listed and priced while being
> unavailable in every datacenter — check availability, not the catalogue; (2) arm64 has no
> usable native libsignal, so Signal must run from a container
> ([`channel-setup.md`](channel-setup.md) § ARM64). x86-64 avoids both.
>
> **Source:** [hetzner.com/cloud](https://www.hetzner.com/cloud)

## CAX Series (Ampere Altra ARM64)

| Model | vCPUs | RAM | SSD | Traffic |
| ------- | ------- | ----- | ----- | --------- |
| CAX11 | 2 | 4 GB | 40 GB | 20 TB |
| CAX21 | 4 | 8 GB | 80 GB | 20 TB |
| CAX31 | 8 | 16 GB | 160 GB | 20 TB |
| CAX41 | 16 | 32 GB | 320 GB | 20 TB |

> **No prices here on purpose.** Fetch the current per-model price from
> [hetzner.com/cloud](https://www.hetzner.com/cloud) before quoting one to the user, and mind the
> VAT footnote — see [`provider-selection.md`](provider-selection.md) § 2.

## Availability by Location

| Location | Code | CAX available |
| ---------- | ------ | -------------- |
| Nuremberg, Germany | nbg1 | Yes |
| Falkenstein, Germany | fsn1 | Yes |
| Helsinki, Finland | hel1 | Yes |
| Singapore | sin | **No** (AMD only) |
| US (Ashburn, Hillsboro) | ash, hil | **No** (AMD only) |

## Recommendations for OpenClaw

> These size **OpenClaw and a local model only**. If the host will also run agent orchestration
> (parallel pytest workers, Node builds, headless Chromium), budget **3–6 GB per concurrent job**
> on top and size for peak concurrency — see [`../SKILL.md`](../SKILL.md) § 1.4a. Sizing a shared
> host from this table undersizes it badly.

| Use case | Recommended |
| ---------- | ------------- |
| BYOK only (no local model) | CAX11 |
| Local model 3-4B (basic) | CAX11 |
| Local model 7-8B (good) | CAX21 |
| Local model 14B (very good) | CAX31 |
| Local model 20B+ | CAX41 |
| Local model 70B+ | Not feasible on CAX — dedicated server |

## hcloud CLI Quick Reference

```bash
# Install
brew install hcloud          # macOS
# or: apt install hcloud-cli   # Ubuntu (snap)

# Authenticate
hcloud context create openclaw
# Paste API token from https://console.hetzner.cloud

# List available server types
hcloud server-type list

# Create server
hcloud server create \
  --name openclaw \
  --type cax11 \
  --image ubuntu-24.04 \
  --location nbg1 \
  --ssh-key <key-name>

# List servers
hcloud server list

# Delete server (destructive!)
hcloud server delete openclaw
```
