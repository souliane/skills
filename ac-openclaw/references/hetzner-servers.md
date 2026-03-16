# Hetzner Cloud — CAX (ARM64/Ampere) Server Reference

> **Last updated:** 2026-03-14
> **Source:** [hetzner.com/cloud](https://www.hetzner.com/cloud), [costgoat.com/pricing/hetzner](https://costgoat.com/pricing/hetzner)

## CAX Series (Ampere Altra ARM64)

| Model | vCPUs | RAM | SSD | Traffic | Price/mo (excl. VAT) |
|-------|-------|-----|-----|---------|---------------------|
| CAX11 | 2 | 4 GB | 40 GB | 20 TB | ~4.49 EUR |
| CAX21 | 4 | 8 GB | 80 GB | 20 TB | ~7-8 EUR |
| CAX31 | 8 | 16 GB | 160 GB | 20 TB | ~14-15 EUR |
| CAX41 | 16 | 32 GB | 320 GB | 20 TB | ~28-30 EUR |

> **Pricing date:** Effective April 1, 2026. Prices are estimates for CAX21-41 based on the confirmed CAX11 increase (3.29→4.49). Verify at [hetzner.com/cloud](https://www.hetzner.com/cloud) before provisioning.

## Availability by Location

| Location | Code | CAX available |
|----------|------|--------------|
| Nuremberg, Germany | nbg1 | Yes |
| Falkenstein, Germany | fsn1 | Yes |
| Helsinki, Finland | hel1 | Yes |
| Singapore | sin | **No** (AMD only) |
| US (Ashburn, Hillsboro) | ash, hil | **No** (AMD only) |

## Recommendations for OpenClaw

| Use case | Recommended | Monthly cost |
|----------|-------------|-------------|
| BYOK only (no local model) | CAX11 | ~4-5 EUR |
| Local model 3-4B (basic) | CAX11 | ~4-5 EUR |
| Local model 7-8B (good) | CAX21 | ~7-8 EUR |
| Local model 14B (very good) | CAX31 | ~13-15 EUR |
| Local model 20B+ | CAX41 | ~25-30 EUR |
| Local model 70B+ | Not feasible on CAX | Dedicated server |

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
