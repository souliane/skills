# Choosing a VPS provider

> **This file carries a method, not prices.** Every number you quote to a user comes from the
> vendor's own live page, fetched in the session you quote it in. Prices in this market move
> *monthly*, so a cached figure is a lead to verify, never a quote.

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
Assuming a top tier means the vendor's fastest silicon gets both the performance model and the
budget wrong, because the fast line is usually a separately named product at 1.5–2.5× the price.

Also check the *age*. The cheapest RAM-per-euro tier is routinely decade-old Xeon, and a budget
host will happily tell you it may deploy on either of two generations with no buyer's choice
offered. If the store will not name the part, treat the tier as the oldest one it could be.

### 4b. Compare adjacent generations before buying the newer one

Vendors keep two generations of the same tier on sale at identical vCPU / RAM / disk and a real
price gap — a double-digit percentage, for silicon and memory generation alone. Look up the older
sibling of whatever plan you are about to recommend:

- **RAM-bound** (the usual case for an assistant plus a couple of concurrent jobs) → the older
  generation is the better buy, and the delta is pure waste.
- **CPU-bound** (agent fan-out, parallel test workers) → the newer generation earns it.

Naming the newer plan without checking the older one is the easiest recurring overspend here.

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

### 7. Why the numbers keep moving

Memory foundries have reallocated cleanroom capacity from commodity DDR4/DDR5 to HBM for AI
accelerators, so conventional DRAM contract prices are rising. The effect is structural rather
than logistical: hosts raise prices more than once a year, sometimes on existing contracts, and
free or cheap ARM tiers get quietly cut.

Practical consequence for a fresh install: **a cached price is a lead, not a quote**, and
"wait for a restock / for prices to fall" is not a plan.

## Candidates

Do not carry a shortlist in this file — it rots faster than anything else here. Search for current
EU options, then run each candidate through §§ 1–7 above.

Size for a box that runs OpenClaw *and* whatever else the user answered in
[`SKILL.md`](../SKILL.md) § 1.4a — for a chat-only assistant, much smaller tiers apply.

Hetzner's ARM (CAX) line has a cached spec table in [`hetzner-servers.md`](hetzner-servers.md);
check availability per §3 before recommending it, and read the arm64 signal-cli caveat in
[`channel-setup.md`](channel-setup.md) before choosing ARM at all.
