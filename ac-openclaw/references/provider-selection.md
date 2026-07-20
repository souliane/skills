# Choosing a VPS provider

> **The method below is the durable part. The snapshot table is a worked example that will rot.**
> Every price in it was fetched from the vendor's own live page on **2026-07-17** and is net /
> ex-VAT. Prices in this market move *monthly* — re-verify before buying, never quote these
> numbers to a user as current.

This skill is **not** tied to one provider. [`hetzner-servers.md`](hetzner-servers.md) is one
cached provider among several — useful if the user picks Hetzner, not a default.

Companion skill: `ac-migrating-servers` owns *moving an existing box* (capture, cutover,
decommission). This file is for **fresh installs** — picking the box you are about to install
onto.

## The method

### 1. Fetch every number from the vendor

Treat a pricing blog post, a comparison site, or an LLM research report as a **list of
candidates to verify**, never as prices. The failure mode is not "wrong provider" — it is a
correct provider decorated with stale or invented specifics (a plan that no longer exists at
that price, a CPU attributed from a different vendor, an urgency claim like a stock counter or
promo expiry that has no source). Urgency claims are exactly the ones that push a fast purchase
without checking, so check those hardest.

### 2. Normalize VAT before comparing

Vendors quote inconsistently, and this alone can invert a ranking. Two real examples from the
same afternoon:

- One page said **€45.80**, footnoted "incl. 19% VAT" → **€38.49 net**.
- Another said **€13.99**, labelled `Preis inkl. MwSt.` → **~€11.76 net**, not €13.99 net.

Find the page's VAT footnote before putting a number in a comparison table. An EU-registered
business buying cross-border B2B pays the **net** price under reverse charge — but only if a
valid VAT ID is supplied at checkout. **Confirm the checkout total actually drops.** If it
doesn't, the ID wasn't accepted and reverse charge is not applying.

### 3. Existence ≠ availability

A provider will publish current prices for a plan it cannot sell you. If the provider has an
API, read the **availability** set, not the catalogue:

```bash
# distinguish "supported here" from "actually orderable here"
<provider-cli> server-type list -o json
<provider-cli> datacenter describe <dc>   # compare `supported` vs `available`
```

A plan listed under `supported` but absent from `available` prices out fine, keeps existing
servers running — and cannot be ordered or rescaled to.

Observed: an entire ARM line, listed and priced, **unavailable in every datacenter**, with a
stock-watcher polling every 30 minutes for four months and never once firing.

**If a stock watcher has never fired, that is a "no", not "waiting".** Do not plan an install
around capacity that has never appeared.

### 4. Read the CPU from the vendor's own announcement

Plan names lie by omission. A "heavy" or "performance" tier tells you nothing about silicon —
vendors publish the actual part in blog posts and news announcements, not in the pricing table.

One vendor's `vm.v3-*` line is **EPYC 9354 @3.25 GHz**, while its Ryzen boxes are a separately
named product line at 1.5–2.5× the price. Assuming "heavy tier = Ryzen" gets both the
performance model and the budget wrong.

Also check the *age*: one budget host's own store warned deployment could be **either** a 2017
Skylake part **or** a 2013 Ivy Bridge part, with no buyer's choice offered.

### 5. Latency is almost never the axis

For a messaging assistant — plus any CI-shaped agent work on the same box — the difference
between a 12 ms and a 20 ms datacenter is invisible. Signal's own round trip dwarfs it, and
pytest, Node builds, and headless Chromium are RAM- and CPU-bound, not network-bound. A vendor
selling "sub-5 ms from our local DC" is selling a non-benefit.

**Pick on RAM, cores, price, and jurisdiction.**

### 6. Jurisdiction, if you process someone else's data

If the box will run under a data-processing agreement, its country is a contractual matter, not
a preference:

- **EU/EEA** — clean.
- **Adequacy-decision countries** (UK, Switzerland) — legal, but add a third-country question to
  answer for no benefit.
- **No adequacy decision** — a real problem.

Decide this *before* comparing prices; it removes options and shortens the comparison.

### 7. Why the numbers keep moving (2026)

Memory foundries reallocated cleanroom capacity from commodity DDR4/DDR5 to HBM for AI
accelerators, and conventional DRAM contract prices rose steeply through early 2026. The effect
is structural rather than logistical: several hosts raised prices more than once in a single
year, including on existing contracts, and free ARM tiers were quietly halved. Relief is not
expected soon.

Practical consequence for a fresh install: **a cached price is a lead, not a quote**, and
"wait for a restock / for prices to fall" is not a plan.

## Snapshot — verified 2026-07-17 (WILL BE STALE)

All net / ex-VAT. EU locations only. Sized for a box that runs OpenClaw *and* agent
orchestration (see [`SKILL.md`](../SKILL.md) § 1.4) — for a chat-only assistant, much smaller
tiers apply.

| Provider | Plan | vCPU | RAM | Disk | Location | €/mo net |
|---|---|---|---|---|---|---|
| Hostkey | `vm.v2-medium` | 8 | 16 GB | 160 GB NVMe | Amsterdam | 14.00 |
| Hostkey | **`vm.v2-heavy`** | 8 | **32 GB** | 240 GB NVMe | Amsterdam | **28.00** |
| Hostkey | **`vm.v3-heavy`** | 8 | **32 GB** | 240 GB NVMe | Amsterdam | **36.40** |
| Alwyzon | `E16+` | 6 | 16 GB DDR5 ECC | NVMe RAID 10 | Vienna | 38.49 |
| Luxvps | `Lux Deal #2` | 6 | 26 GB | NVMe | Frankfurt | 11.95 |
| Prepaid-Hoster | `Essential 16` | 6 | 16 GB | NVMe | Offenbach | ~11.76 |

Notes that matter more than the numbers:

- **The `v2` vs `v3` trap.** Identical vCPU / RAM / disk, **€8.40/mo apart**. `v3` is the newer
  generation (EPYC 9354, DDR5). If the bottleneck is RAM, `v2` is the better buy; if the
  workload is CPU-bound agent fan-out, `v3` earns the delta. A recommendation naming `v3`
  without mentioning `v2` costs ~€100/yr for nothing.
- **Luxvps** is by a wide margin the cheapest RAM per euro — but the silicon is 2013–2017 Xeon
  and the store would not commit to which.
- **Alwyzon** is the newest silicon here and the only Austrian option, but its larger tiers rise
  steeply.
- Hetzner's ARM (CAX) line stays in [`hetzner-servers.md`](hetzner-servers.md); check
  availability per §3 before recommending it, and see the arm64 signal-cli caveat in
  [`channel-setup.md`](channel-setup.md) before choosing ARM at all.
