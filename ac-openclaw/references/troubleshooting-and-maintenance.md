# OpenClaw Reference — read when troubleshooting or verifying installation

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
| Running `curl \| bash` without verifying the script | Remote scripts can change between visits — supply chain risk | Download first (`curl -fsSL url -o install.sh`), inspect, then run. Reference files use vendor install commands for convenience but the agent should prefer download-then-inspect when practical |
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
| Installing BOTH a user-level `~/.config/systemd/user/openclaw-gateway.service` AND a system-level `/etc/systemd/system/openclaw.service` | They race for port 18789 on every restart, each one killing the other ("killing N stale gateway process(es) before restart"). Looks like the gateway "breaks constantly." | Pick ONE install method from the start. If both are already present, disable the one you don't want (`systemctl --user disable --now openclaw-gateway.service` + rename the unit file), then `systemctl daemon-reload`. |
| Putting API keys in `Environment=` lines of a systemd unit file | Unit files are mode 664 by default — every logged-in user on the host can read them | Use `EnvironmentFile=` pointing at a `chmod 600` env file, OR a startup wrapper that reads from `pass` (the user's existing `~/.openclaw/start-gateway.sh` pattern). Rotate any key that was ever in a world/group-readable unit file. |
| Running `openclaw` CLI commands on the same host as a running `openclaw.service` | In v2026.4.x, `openclaw cron list`/`doctor`/etc. detect the running gateway PID and SIGTERM it before trying to start their own in-process gateway, which then fails to resolve `OPENCLAW_GATEWAY_TOKEN` (not in interactive shells) and exits. Systemd restarts the real service, signal-cli dies for 20-30 s. Every CLI call causes a messaging outage. | Edit `~/.openclaw/cron/jobs.json` directly for cron tweaks, call signal-cli JSON-RPC at `http://127.0.0.1:8080/api/v1/rpc` (no trailing slash) for sends/probes, and use the Tailscale-served dashboard for everything else. If you must use the CLI, do it from a different machine against a remote gateway. |
| Auto-update landed new code but gateway still errors `ERR_MODULE_NOT_FOUND` | OpenClaw's npm auto-update replaces files on disk but the running Node.js process still references old content-hashed chunk filenames that aren't in the new tarball. Every outbound send throws. | Restart the service: `sudo systemctl restart openclaw.service`. Disk and package.json will show the newer version; `start-gateway.sh` loads the new `dist/index.js` on startup. Consider enabling an auto-restart-after-update hook if OpenClaw doesn't ship one. |
| **Cron jobs (press-review, heartbeat) silently stop firing for a day or more after an auto-update — no error, no delivery, no run-log row for the missed day(s)** | **Same root CLASS as the `ERR_MODULE_NOT_FOUND` row above: auto-update applied new code to disk but did NOT restart the running process.** A version bump that *migrates the cron store* makes this silent instead of loud. Observed on the 2026-06-04 → 2026.6.1 bump: the new code consolidated the per-feature JSON stores into a single `~/.openclaw/state/openclaw.sqlite` and renamed the old files to `*.migrated` (`cron/jobs.json.migrated`, `cron/jobs-state.json.migrated`, `cron/runs/<id>.jsonl.migrated`, `flows/registry.sqlite.migrated`, `tasks/runs.sqlite.migrated`). But the *still-running* old process kept its in-memory scheduler pointed at the now-renamed `jobs.json` — so the next morning's cron never fired at all (no run-log row), while `systemctl status` showed the service "active (running)" and `NRestarts` low. The journal is the tell: `[gateway] auto-update applied` repeating **every hour** with no `full process restart` / `[gateway] ready` between them means the new code is on disk but never loaded. A manual `sudo systemctl restart openclaw.service` (or any gateway-tool restart) loads the new code, which reads the sqlite store, and cron resumes. | **Restart the gateway after any auto-update that you did not see followed by a `[gateway] ready` line:** `sudo systemctl restart openclaw.service`. Confirm the running PID's start time is **newer** than the mtime of `~/.npm-global/lib/node_modules/openclaw/package.json` (stale = on-disk code is newer than the process). v2026.6.1+ ships an `respawnGatewayProcessForUpdate` / `restartGatewayProcessWithFreshPid` path (in `dist/run-wssker-*.js`) that restarts after update, with an in-process-restart fallback — so the class is largely self-healing forward, but the fallback may not pick up a store migration. **Do not rely on it: install the press-review delivery watchdog (below) as the same-day safety net.** Verify a missed day via the cron store: `sqlite3 -readonly ~/.openclaw/state/openclaw.sqlite "SELECT date(run_at_ms/1000,'unixepoch','localtime') d, count(*), group_concat(status) FROM cron_run_logs WHERE job_id=(SELECT job_id FROM cron_jobs WHERE name='press-review') GROUP BY d ORDER BY d DESC LIMIT 7;"` — a date with **zero rows** is a silent skip. |

## Troubleshooting Quick Reference

| Problem | Check |
|---------|-------|
| OpenClaw won't start | `openclaw doctor`, check Node version (`node -v` >= 22) |
| Gateway unreachable | `openclaw status`, check the configured service (`systemctl --user status openclaw` or `sudo systemctl status openclaw`) |
| Channel not receiving messages | `openclaw channels status --probe` |
| Signal: daemon not reachable | `pgrep -af signal-cli`, check signal-cli HTTP port |
| Signal: "User is not registered" | Verify `getUserStatus` first, then restart gateway and restore the latest signal-cli backup before attempting destructive re-registration. See [`channel-setup.md`](channel-setup.md) § "Troubleshooting: Signal Registration Lost" |
| Signal: "This person is not on Signal" (after re-registration) | Identity key changed. Contact must delete old conversation and start a new one |
| WhatsApp: QR expired | Re-run `openclaw channels login --channel whatsapp` |
| Tailscale: can't reach dashboard | `tailscale status`, verify both devices on same tailnet |
| Docker bypasses firewall | Add DOCKER-USER iptables rules (see [`security-hardening.md`](./security-hardening.md) § Docker + Firewall) |
| API key rate limited | OpenClaw auto-rotates keys; add backup keys with `_1`, `_2` suffixes |
| High memory usage (Ollama) | Check model size vs RAM; use smaller quantization or smaller model |
| SSH custom port not working (Ubuntu 24.04) | Ubuntu 24.04 uses systemd socket activation. Do NOT put `Port` directives in `sshd_config` — use a systemd socket override at `/etc/systemd/system/ssh.socket.d/override.conf` with explicit `0.0.0.0:PORT` and `[::]:PORT` format. Bare port numbers (e.g., `ListenStream=2222`) don't bind IPv4. Always keep the old port open in UFW until the new port is confirmed working from outside. |
| Locked out of SSH | Use `hcloud server enable-rescue <name> --ssh-key <key>` then `hcloud server reset <name>` to boot into rescue mode. Mount disk at `/mnt` via `mount /dev/sda1 /mnt`, fix configs, unmount, disable rescue, reset. |
| Gateway constantly cycling / "breaks every few minutes" | Check for a DUPLICATE unit. Run `systemctl --user list-units --type=service --no-pager` AND `sudo systemctl list-units --type=service --no-pager \| grep openclaw`. If you see **both** a user-level `openclaw-gateway.service` and a system-level `openclaw.service`, they race for port 18789 — each tries to kill the other on startup ("killing N stale gateway process(es) before restart"). Disable whichever you don't want with `systemctl --user disable --now openclaw-gateway.service` (then rename the unit file to stop systemd still seeing it) or equivalent sudo-level commands. Pick ONE install method and delete the other. |
| `ERR_MODULE_NOT_FOUND: Cannot find module '.../dist/*.runtime-*.js'` in gateway logs | An `npm update -g openclaw` landed new code on disk but the running process still references old code-split chunk filenames (content-hashed — new tarball ships new hashes). Fix: `sudo systemctl restart openclaw.service`. This is visible via `/home/openclaw/.npm-global/lib/node_modules/openclaw/package.json` showing a version newer than what the gateway logs report at startup. |
| Health check `signal-cli getUserStatus` hangs indefinitely | Classic data-dir lock contention. `signal-cli daemon` holds the exclusive lock on `~/.local/share/signal-cli/data/`; a second `signal-cli` subprocess waits forever on the lock without printing the "in use by another instance" error immediately. **Fix the script**: probe `http://127.0.0.1:8080/api/v1/rpc` (**no trailing slash**) instead of spawning a second `signal-cli` subprocess, and wrap with `timeout 10 curl`. Also add `TimeoutStartSec=90` to the health service unit so systemd kills any residual hang after 90 s. |
| signal-cli JSON-RPC `send` returns `UNREGISTERED_FAILURE` | Check the `recipient` format. signal-cli's JSON-RPC `send` takes E.164 phone numbers (`+33612345678`) in `recipient`, NOT `uuid:...` strings. If you pass `"recipient": ["uuid:..."]`, signal-cli strips non-digits and treats it as a phone number — always fails. OpenClaw's internal `delivery.to: "uuid:..."` is fine because OpenClaw translates before calling signal-cli; only raw JSON-RPC calls need the phone-number format. |
| `openclaw` CLI kills the running gateway every time I invoke it | Do NOT run `openclaw cron list` / `openclaw doctor` / any CLI command on the same host as a running `openclaw.service`. The CLI in v2026.4.x detects the running gateway PID and SIGTERMs it ("service-mode: cleared N stale gateway pid(s) before bind on port 18789") before trying to start its own in-process gateway — which usually fails because `OPENCLAW_GATEWAY_TOKEN` env var isn't set in the interactive shell. Use direct file edits for cron changes, signal-cli JSON-RPC for sends, or the Tailscale dashboard for everything else. |
| Plaintext API keys visible in `~/.config/systemd/user/*.service` | Never put `Environment=OPENAI_API_KEY=sk-...` or similar in unit files — they end up mode 664 (group+world readable by default). Use `EnvironmentFile=%h/.openclaw/gateway.env` with `chmod 600`, OR a startup wrapper script that reads from `pass`. Rotate any key that was ever committed as plaintext in a user-readable file. |
| Cron job fails with `cron: job execution timed out` (e.g. press-review) | The `payload.timeoutSeconds` budget includes the WHOLE agent turn: script exec + tool calls + model synthesis + delivery. Reasoning-heavy models (`gpt-oss-120b`, `deepseek-r1`) can drift well over 60 s for synthesis alone. Read `~/.openclaw/cron/runs/<jobId>.jsonl` to see the duration trend — durations creeping toward the budget cap mean a timeout is imminent. Bump `payload.timeoutSeconds` in `~/.openclaw/cron/jobs.json` (live-reloaded by the gateway, no service restart). Keep budget at ≥ 2× the recent p95 successful duration, not just the average. |
| Cron job fails with `⚠️ Agent couldn't generate a response` | OpenRouter / model-side empty completion, NOT a budget issue. Adding more time doesn't help. Likely causes: provider rate-limit, transient model error, or a model recently moved to "reasoning mandatory" without `"reasoning": true` in the agent's `models.json` (see `press-review.md` § "Model reasoning flag"). Add a fallback model under the agent's `models.fallback` chain. |
| Press review (or any digest) arrives **empty / near-empty** — only the `## Press Review — <date>` header, ~150 output tokens, even though the *first* run of the day was full | The aggregator script's dedup + conditional-GET cache **starves repeat runs**: once any run (the cron, or a manual test) marks the day's items seen and stores feed ETags, the next run the same day returns "0 fresh" for every source and a 304 skips each feed entirely — so an on-demand pull *after* the cron gets nothing. **Fix lives in `press-review.py`:** dedup suppresses a URL only on a *later* day (same-day re-runs re-show today's items) and a 304 re-serves the last parsed items cached in `press-review-feeds.json` instead of returning nothing. Verify by running the script twice back-to-back — both runs must report the same non-empty `N fresh` counts. |
| OpenRouter credits can drain unexpectedly — `402 Insufficient credits` after what should be free/BYOK usage; `https://openrouter.ai/activity` shows requests served by an **unexpected provider** (e.g. Azure) | **OpenRouter routes a model across many providers at very different prices, and falls back across them by default.** Two traps: (1) the BYOK *"Always use for this provider"* toggle only forces *your* key for *that* provider — it does NOT stop OpenRouter falling back to a *different* provider serving the same model, which bills your OpenRouter credits; (2) a normally-routed model (e.g. `openai/gpt-oss-120b` spans roughly $0.039–$0.95 per-M-token across providers) can silently land on an expensive one. **Fix: pin provider routing so OpenRouter only ever uses providers you chose and *fails* rather than falling back.** In OpenClaw set it under `models.providers.openrouter.params.provider`, e.g. `{"only": ["deepinfra","dekallm","novita"], "sort": "price"}` (use provider *slugs* from `GET /api/v1/models/<model>/endpoints` — the part before the `/` in each `tag` — not display names). A failed request then drops to the agent's free-model fallback instead of a pricey provider. Belt-and-braces: set a per-key spend cap at `https://openrouter.ai/settings/keys` (keys have **no limit** by default) and audit spend at `https://openrouter.ai/activity`. |
| A hosted model gives noticeably worse answers than expected — weaker reasoning/code, or garbled multi-byte (CJK) text — even though you picked a frontier model slug | Providers hosting the same open-weight model can serve it at different quantization levels (int4/fp4 are the aggressive ones, and can corrupt multi-byte decoding). OpenRouter may route to a low-bit-quant provider by default, so the model is technically right but the weights are degraded. **Fix: require higher-precision providers in the same `params.provider` block you already use for cost/reliability pinning — add a `quantizations` allow-list**, e.g. `{"only": ["<provider-slug>"], "quantizations": ["fp8","bf16","fp16"]}`. A request that can't be served at the allowed precision then fails over instead of silently degrading. Allowed values: `int4`, `int8`, `fp4`, `fp6`, `fp8`, `fp16`, `bf16`, `fp32`, `unknown`. This is the hosted-provider analogue of the local quantization table in [`local-models.md`](local-models.md) (§ "Quantization Quick Reference"). |
| Tool/agent setup: tools misfire intermittently (bad JSON, wrong tool name, tool not called) on one model even though the same slug works elsewhere | The same weights give different tool-calling accuracy across providers. Two levers: (1) on OpenRouter, append the `:exacto` suffix to a supported model slug (e.g. `<vendor>/<model>:exacto`) to route only to providers with measurably better tool-use success; (2) detect a degraded provider before trusting it — run a tiny fixed eval canary (a handful of prompts with known-good answers plus one tool-call prompt) against the configured route and compare output, rather than trusting a perplexity or latency number. A cheap provider that fails the canary is the one to drop from `only`. |
| Cron (press-review/heartbeat) **recurring `status=error`, `error="LLM request failed."`** after a long run (often 100–240 s), `error-then-ok` across days, gateway otherwise healthy (`[gateway] ready`, restart-after-update worked) | NOT the auto-update silent-miss — the agent's OpenRouter route is hitting **unreliable providers**. Either the agent's `params.provider` is **empty** (no pin → OpenRouter default routing) or pinned to the **cheapest** tier (`sort: price` → deepinfra/dekallm/novita = the flakiest). A daily-digest turn is long, so one bad provider fails the whole run. **Fix: pin to reliable, still-cheap *paid* providers and sort by throughput, not price** — `params.provider = {"only": ["groq","together","baseten"], "sort": "throughput"}` (Groq is fast + reliable, also cuts the 100 s+ latency). ~30k tokens/day ≈ **$0.20/mo** — reliability dwarfs the price gap. **Free models are a poor cron fallback** (low rate-limit / daily-quota → fails exactly when relied on). **Per-agent gotcha:** the cron agent (e.g. `souliane`) has its OWN `~/.openclaw/agents/<agent>/agent/plugins/openrouter/catalog.json` — `main`'s pin does NOT cover it; fix every cron-running agent. This is the reliability counter-weight to the cost-pin row above: for a *must-deliver* cron, favour throughput over price. |
| Gateway crash-loops on restart: `Gateway failed to start: Invalid config at .../openclaw.json` → `agents.defaults.model: Invalid input` | You hand-edited `agents.defaults.model` (e.g. appended to `fallbacks` + `models`) and the shape failed schema validation; systemd then restart-loops the dead gateway. **Don't hand-edit `agents.defaults.model` for routing/reliability — set provider routing in the openrouter plugin catalog `params.provider` instead** (rows above). The config is validated only at gateway **startup**, so a bad edit isn't caught until the failed restart. Always `cp openclaw.json openclaw.json.bak-<ts>` before editing; recover with `cp` back + `sudo systemctl reset-failed openclaw.service && sudo systemctl restart openclaw.service`. Reuse a *proven* shape (copy another working agent's block) rather than authoring `model` config blind. |
| Running a cron on demand fails: `unknown cron job id: <name>` or `GatewaySecretRefUnavailableError: gateway.auth.token ... unavailable` | v2026.6.1 cron CLI is **gateway-routed** — it does NOT kill the running service (the v2026.4.x kill-the-gateway behaviour in the earlier row is fixed for cron commands). Two gotchas: (1) `cron run` takes the **job ID, not the name** (get it from `openclaw cron list` or the journal `[cron:<id>]`); (2) it needs the gateway token in your shell: `export OPENCLAW_GATEWAY_TOKEN="$(pass show openclaw/gateway-token)"` (the systemd unit injects it at boot; an interactive shell doesn't). Then `node ~/.npm-global/lib/node_modules/openclaw/openclaw.mjs cron run <jobId>` → `{"ok":true,"enqueued":true}` and runs **async** — read the outcome from `cron_run_logs` in `~/.openclaw/state/openclaw.sqlite`, not the CLI's return. |
| Proactive cron delivery (e.g. press-review `announce` mode) fails `Delivering to Signal requires target <…uuid:ID…>` even though `delivery.to` is a valid `uuid:` and chat **replies** to the same recipient succeed | Seen when OpenClaw talks to an **external/containerised** signal-cli daemon (`autoStart:false` + `httpUrl`, or a docker shim). The reply path resolves its target from the incoming message's session and works; the cron's *explicit* `uuid:` target resolution does not, across single/multi-account and autoStart on/off. Generation itself succeeds (the run record shows a full `summary` + token usage). **Workaround:** message the bot to get an on-demand briefing (chat path works). Root cause correlates with the external-daemon connection (native-spawned signal-cli resolves the same explicit target) rather than the target string. |
| Where's the actual run history for a cron job? | The `state` block inside `~/.openclaw/cron/jobs.json` is a stale schema slot — recent OpenClaw versions write runtime state to `~/.openclaw/cron/jobs-state.json` (latest only) and per-run records to `~/.openclaw/cron/runs/<jobId>.jsonl`. The jsonl is append-only; tail it for the duration trend. The `lastErrorReason: "timeout"` field in `jobs-state.json` distinguishes a hard budget hit from a model-side failure. |
| Gateway crash-loops every ~30-60 s; logs show `[plugins] bonjour: ... re-advertise ... state=probing` then `Unhandled promise rejection: CIAO PROBING CANCELLED` / `CIAO ANNOUNCEMENT CANCELLED`, `Main process exited, code=exited, status=1/FAILURE`, `Scheduled restart job` (rising `NRestarts`) | The `bonjour` (mDNS/CIAO) plugin's re-advertise watchdog throws an **unhandled** promise rejection that kills the Node process; systemd `Restart=always` loops it forever, so signal-cli never stays up and no cron/heartbeat runs. A cloud VPS has no LAN to advertise to, so the plugin is useless. **Fix: disable it** - add `"bonjour": { "enabled": false }` under `plugins.entries` in `~/.openclaw/openclaw.json`, then `sudo systemctl reset-failed openclaw.service && sudo systemctl restart openclaw.service`. Confirm via the startup log: `bonjour` no longer appears in `ready (N plugins: ...)`. NOTE: the repeated SIGKILLs from this loop frequently corrupt signal-cli's SQLite store - see the next row. |
| signal-cli won't start: `[signal] signal-cli: Error loading state file for user <E.164>: Failed read from kyber_pre_key store (RuntimeException)`; RPC port 8080 refused; a read-only `PRAGMA integrity_check` on `~/.local/share/signal-cli/data/<accountId>.d/account.db` reports `database disk image is malformed` | The account SQLite DB is **corrupt** - usually a crash-looping gateway SIGKILLing signal-cli mid-write (see bonjour row). `account.db` mtime freezes on the day it broke (matches "silent since ..."); the account id is in `data/accounts.json` (state dirs are named by internal id, not phone number). **Fix: restore the newest non-corrupt `account.db` from backup.** Daily `~/backups/openclaw-YYYY-MM-DD.tar.gz` contain `home/<user>/.local/share/signal-cli/`. Scan newest->oldest, extract `.../<accountId>.d/account.db`, run `PRAGMA integrity_check` on each until one returns `ok` - every snapshot *after* corruption carries the same bad DB, so the clean one is the last backup *before* the break. Restore from **inside** the openclaw-owned `signal-cli/` dir (the parent `~/.local/share/` is often root-owned, so you cannot rename `signal-cli` itself): `mv data data.corrupt-<ts>`, then extract `.../signal-cli/data` from the good tarball into place; verify with a one-off read-only `signal-cli -a <E.164> listIdentities` (no daemon running -> no data-dir lock contention). The identity key is unchanged across snapshots -> **no Signal safety-number change**; you lose only messages since that backup. Never run `deleteLocalAccountData`/re-register without explicit approval. |
| **ARM64 only:** signal-cli daemon crashes (`SIGABRT`) on every **send** while receive/`version` work fine; gateway logs `[signal] daemon exited (source=process code=null signal=SIGABRT)` + `OutboundDeliveryError: socket hang up`; `/tmp/hs_err_pid*.log` shows `SIGSEGV ... oopDesc::klass() ... jni_IsInstanceOf ... libsignal_jni.so ... Java_..._SessionCipher_1EncryptMessage` on a `ForkJoinPool-*-worker` (virtual-thread carrier). Model synthesis succeeds but **delivery always fails**; the heartbeat respawns the daemon so it recurs every ~30 min ("silent morning routine"). | **ARM64/aarch64 libsignal native-lib mismatch — the known signal-cli ARM64 gap.** signal-cli's `libsignal-client-*.jar` bundles native libs only for Linux-x86 (`libsignal_jni_amd64.so`) and macOS-ARM (`libsignal_jni_aarch64.dylib`), **never Linux-aarch64** — so it falls back to a hand-placed `/usr/java/packages/lib/libsignal_jni.so`, and any version drift between that `.so` and the jar's Java bindings corrupts JNI handles → `SIGSEGV` on encrypt. **No JVM flag fixes it** (verified: `-Xint`, `-XX:+UseSerialGC`, `-XX:-UseCompressedOops` all still crash — it is native, not JIT/GC). OpenClaw's own `install-signal-cli` also bails on `linux + non-x64`. **Fix (what the community does on ARM64): run signal-cli from the `bbernhard/signal-cli-rest-api` Docker image — it ships correctly-built ARM64 libsignal — as the native daemon, and connect OpenClaw to it instead of spawning the broken local binary.** (1) snapshot `~/.local/share/signal-cli/data` (a newer signal-cli may migrate the DB). (2) stop the gateway (frees `:8080`, releases the DB lock). (3) `docker run -d --name signal-daemon --restart unless-stopped --no-healthcheck -p 127.0.0.1:8080:8080 -e XDG_DATA_HOME=/data -e HOME=/tmp -v ~/.local/share:/data --user <uid:gid> --entrypoint signal-cli bbernhard/signal-cli-rest-api:latest -a <E.164> daemon --http 0.0.0.0:8080 --no-receive-stdout` (mounts the existing account → **no re-pairing**; `--user` matches the data owner uid; `--no-healthcheck` because the bbernhard healthcheck targets its REST wrapper, not the raw daemon). (4) in `~/.openclaw/openclaw.json` set `channels.signal.autoStart=false` and `channels.signal.httpUrl="http://127.0.0.1:8080"`; `openclaw config validate` then restart the gateway. (5) verify: `curl -s -X POST http://127.0.0.1:8080/api/v1/rpc -d '{"jsonrpc":"2.0","method":"send","id":1,"params":{"recipient":["<recipient-uuid>"],"message":"test"}}'` returns `"type":"SUCCESS"` (no crash), and the gateway shows a `signal:direct` lane on an incoming reply. `sudo systemctl enable docker` so the container survives reboot. Future signal-cli updates = `docker pull` a new image, no native-lib juggling. |

---

## Automated Maintenance (Post-Install)

Use `systemd --user` for ongoing OpenClaw automation unless you deliberately standardized on a root-managed system service. That keeps the gateway, health checks, and update timers in the same supervision model.

### Signal Health Check (user timer, every 30 min)

The health-check script should be conservative:

1. Probe the running `signal-cli` daemon via its HTTP JSON-RPC endpoint — **never** spawn a second `signal-cli` subprocess. The daemon holds an exclusive lock on the data directory; a subprocess will block indefinitely waiting for it.
2. If the RPC answers `version`, exit 0.
3. If it doesn't, restart the gateway once and poll again for up to 30 s.
4. Only if the daemon still doesn't answer, restore the latest backup of `~/.local/share/signal-cli/data/`, start the gateway, and notify via the same RPC.
5. Do not auto-run `deleteLocalAccountData` or re-register without human approval.

Example script skeleton (updated 2026-04-22 after a wedge-incident. The previous example spawned a second `signal-cli` subprocess to call `getUserStatus` — that contends for the data-dir lock and hangs forever. Use the HTTP JSON-RPC path instead; mind the exact URL `http://127.0.0.1:8080/api/v1/rpc` **with no trailing slash** — the trailing-slash variant silently 404s):

```bash
#!/usr/bin/env bash
set -uo pipefail  # NOT -e: we manage exits manually

ACCOUNT="${OPENCLAW_SIGNAL_ACCOUNT:?set OPENCLAW_SIGNAL_ACCOUNT in the service environment}"
BACKUP_ROOT="$HOME/backups/signal-cli"
STATE_DIR="$HOME/.local/share/signal-cli/data"
RPC="http://127.0.0.1:8080/api/v1/rpc"   # NO trailing slash
LOGFILE="${OPENCLAW_HEALTH_LOG:-/var/log/openclaw-health.log}"
# Grant sudo with: echo "openclaw ALL=(root) NOPASSWD: /usr/bin/systemctl start openclaw.service, /usr/bin/systemctl stop openclaw.service, /usr/bin/systemctl restart openclaw.service" | sudo tee /etc/sudoers.d/openclaw-systemctl

log() { echo "$(date -Iseconds) $1" >> "$LOGFILE"; }

# 0. Gateway must be alive before we bother probing.
if ! systemctl is-active --quiet openclaw.service; then
  log "WARN: gateway not running, skipping check"
  exit 0
fi

# 1. Probe signal-cli daemon via HTTP with a hard timeout. timeout 10 guarantees we NEVER wedge.
payload='{"jsonrpc":"2.0","method":"version","id":1}'
resp=$(timeout 10 curl -sS -m 8 -H 'Content-Type: application/json' -X POST -d "$payload" "$RPC" 2>&1 || true)
if echo "$resp" | grep -q '"result"'; then
  exit 0
fi

log "ALERT: signal-cli RPC unresponsive. Resp: ${resp:0:200}"

# 2. Try a plain restart first.
sudo systemctl restart openclaw.service || true
for _ in 1 2 3 4 5 6; do
  sleep 5
  if timeout 5 bash -c "</dev/tcp/127.0.0.1/8080" 2>/dev/null; then
    log "Recovered via restart"
    exit 0
  fi
done

log "Restart did not recover; attempting backup restore"

# 3. Last resort: restore from the latest backup.
latest_backup=$(ls -1dt "$BACKUP_ROOT"/* 2>/dev/null | head -1)
if [[ -n "${latest_backup:-}" ]]; then
  sudo systemctl stop openclaw.service || true
  rm -rf "$STATE_DIR"
  cp -R "$latest_backup" "$STATE_DIR"
  sudo systemctl start openclaw.service
  sleep 15
fi

log "Restored and restarted"
```

**Unit file — do NOT forget `TimeoutStartSec`**, otherwise a hung run can freeze the timer for days (it happened on this user's VPS: 5 days silent because `Active: activating (start)` never ended):

```ini
# /etc/systemd/system/openclaw-health.service  (or ~/.config/systemd/user/... if user-scoped)
[Unit]
Description=OpenClaw Signal Health Check
After=openclaw.service
# Do NOT add Requires=openclaw.service — that makes the health unit restart
# whenever the gateway restarts, killing the script mid-recovery.

[Service]
Type=oneshot
User=openclaw
ExecStart=/home/openclaw/signal-health-check.sh
TimeoutStartSec=90
TimeoutStopSec=15
KillMode=mixed
```

### Press-Review Delivery Watchdog (timer, daily — surfaces a silent miss SAME-day)

The Signal health check above proves the *daemon* is alive; it says nothing about
whether the daily press review (or any cron-delivered digest) actually went out.
The failure class in the troubleshooting row "Cron jobs silently stop firing after
an auto-update" produces a healthy-looking gateway and a silent non-delivery — the
user only notices days later when they realise no brief arrived. Close that gap
with a small, dependency-free watchdog that runs once daily *after* the brief is
due, verifies it delivered today, and alerts the user over the SAME channel
(signal-cli JSON-RPC) on a miss.

What it checks (all read-only, no `openclaw` CLI — that would cycle the gateway):

1. **Did it deliver today?** Read the press-review job from `~/.openclaw/state/openclaw.sqlite`
   (`cron_jobs.last_run_at_ms` is *today* AND `last_run_status='ok'` AND
   `last_delivery_status='delivered'`). Falls back to the legacy `~/.openclaw/cron/jobs.json`
   if the sqlite store isn't present (version-portable).
2. **Is the job still there + enabled?** A migration that drops the job is itself an alert.
3. **Stale-process detector (the root cause):** the on-disk code mtime
   (`~/.npm-global/lib/node_modules/openclaw/dist/index.js` + `package.json`) is
   NEWER than the running gateway process's start time (`/proc/<MainPID>` ctime).
   That is exactly "auto-update landed but no restart". Deterministic — no log
   scraping. (An early version scraped `current vX.Y` from the journal and
   false-positived on a stale `update available` line; use the mtime-vs-start-time
   signal instead.)

On any miss it sends ONE Signal message per day (date-keyed marker under
`~/.openclaw/state/`) to the press-review recipient, naming the problem and the fix
(`sudo systemctl restart openclaw.service`). A healthy run sends nothing.

The deployed script lives at `~/bin/press-review-watchdog.py` (Python stdlib only)
and the canonical copy is [`scripts/press-review-watchdog.py`](scripts/press-review-watchdog.py).
Gotchas baked in: signal-cli raw JSON-RPC `send` wants a **bare** UUID/E.164 in
`recipient` (strip OpenClaw's `uuid:` prefix); RPC URL is `http://127.0.0.1:8080/api/v1/rpc`
with **no trailing slash**; `~/.local` is often root-owned so logs go under the
openclaw-owned `~/.openclaw/logs/` (file logging degrades gracefully — journald
captures stderr regardless).

System-level timer + service (mirrors the existing `openclaw-health` units), 09:00
local = 1 h after the 08:00 brief so the cron's full timeout budget + retries have
elapsed:

```ini
# /etc/systemd/system/press-review-watchdog.service
[Unit]
Description=OpenClaw press-review delivery watchdog (alerts the user same-day on a silent miss)
After=openclaw.service

[Service]
Type=oneshot
User=openclaw
Environment=HOME=/home/openclaw
ExecStart=/usr/bin/python3 /home/openclaw/bin/press-review-watchdog.py
TimeoutStartSec=90
TimeoutStopSec=15
KillMode=mixed
```

```ini
# /etc/systemd/system/press-review-watchdog.timer
[Unit]
Description=Run the OpenClaw press-review watchdog daily at 09:00 (1h after the 08:00 brief)

[Timer]
OnCalendar=*-*-* 09:00:00
Persistent=true
OnBootSec=10min

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now press-review-watchdog.timer
# Verify both verdict paths before declaring done:
python3 ~/bin/press-review-watchdog.py            # healthy day -> "OK ... delivered today", no Signal msg
# negative test: copy the script, point JOB_NAME at a non-existent name, run -> sends an alert
```

Tune `OnCalendar` to the brief's schedule + budget. Adapt for a `systemd --user`
setup by dropping the units in `~/.config/systemd/user/` and using
`systemctl --user enable --now` (linger must be on).

### Auto-Update (user timer, weekly — controls the system service via sudo)

The update script should be equally strict:

1. Back up `~/.openclaw/` and `~/.local/share/signal-cli/data/`.
2. Stop the gateway cleanly.
3. Update one component at a time.
4. Restart the gateway.
5. Verify `openclaw status`, the gateway health endpoint, and `signal-cli getUserStatus`.
6. Abort and alert if verification fails.

Example user-unit setup:

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/openclaw-health.service <<'EOF'
[Unit]
Description=OpenClaw Signal health check

[Service]
Type=oneshot
EnvironmentFile=%h/.config/openclaw-env
ExecStart=%h/bin/openclaw-signal-health-check.sh
EOF

cat > ~/.config/systemd/user/openclaw-health.timer <<'EOF'
[Unit]
Description=Run OpenClaw Signal health check every 30 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=30min

[Install]
WantedBy=timers.target
EOF

cat > ~/.config/systemd/user/openclaw-update.service <<'EOF'
[Unit]
Description=OpenClaw weekly update

[Service]
Type=oneshot
EnvironmentFile=%h/.config/openclaw-env
ExecStart=%h/bin/openclaw-update.sh
EOF

cat > ~/.config/systemd/user/openclaw-update.timer <<'EOF'
[Unit]
Description=Run OpenClaw weekly update

[Timer]
OnCalendar=Sun *-*-* 04:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

# openclaw-env — keeps secrets out of scripts
# Create and chmod 600 before enabling timers:
# echo 'OPENCLAW_SIGNAL_ACCOUNT=+<E.164 number>' > ~/.config/openclaw-env
# chmod 600 ~/.config/openclaw-env

systemctl --user daemon-reload
systemctl --user enable --now openclaw-health.timer openclaw-update.timer
loginctl enable-linger "$USER"
```

### Update script (`~/bin/openclaw-update.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

ACCOUNT="${OPENCLAW_SIGNAL_ACCOUNT:?set OPENCLAW_SIGNAL_ACCOUNT in ~/.config/openclaw-env}"
# Requires passwordless sudo — see /etc/sudoers.d/openclaw-systemctl setup above.
SERVICE_CTL="sudo systemctl"
SERVICE_NAME="openclaw"
BACKUP_ROOT="$HOME/backups/openclaw-$(date +%Y%m%d)"
LOG="$HOME/.local/log/openclaw-update.log"
mkdir -p "$BACKUP_ROOT" "$(dirname "$LOG")"

log() { echo "[$(date -Is)] $*" | tee -a "$LOG"; }

# 1. Backup current state
log "Backing up ~/.openclaw and signal-cli data..."
cp -a "$HOME/.openclaw" "$BACKUP_ROOT/openclaw"
cp -a "$HOME/.local/share/signal-cli/data" "$BACKUP_ROOT/signal-cli-data" 2>/dev/null || true

# 2. Stop gateway cleanly
log "Stopping gateway..."
$SERVICE_CTL stop "$SERVICE_NAME".service

# 3. Update OpenClaw
log "Updating openclaw..."
npm update -g openclaw 2>&1 | tee -a "$LOG"
NEW_VERSION=$(openclaw --version 2>/dev/null || echo "unknown")
log "New version: $NEW_VERSION"

# 4. Update signal-cli if SIGNAL_CLI_UPGRADE_VERSION is set
# Requires passwordless sudo for tar and ln — extend /etc/sudoers.d/openclaw-systemctl:
#   openclaw ALL=(root) NOPASSWD: /usr/bin/tar, /usr/bin/ln
# Without that, skip this block and upgrade signal-cli manually as root.
if [[ -n "${SIGNAL_CLI_UPGRADE_VERSION:-}" ]]; then
  log "Updating signal-cli to $SIGNAL_CLI_UPGRADE_VERSION..."
  curl -sL "https://github.com/AsamK/signal-cli/releases/download/v${SIGNAL_CLI_UPGRADE_VERSION}/signal-cli-${SIGNAL_CLI_UPGRADE_VERSION}.tar.gz" \
    -o "/tmp/signal-cli-${SIGNAL_CLI_UPGRADE_VERSION}.tar.gz"
  sudo tar xf "/tmp/signal-cli-${SIGNAL_CLI_UPGRADE_VERSION}.tar.gz" -C /opt/
  sudo ln -sf "/opt/signal-cli-${SIGNAL_CLI_UPGRADE_VERSION}/bin/signal-cli" /usr/local/bin/signal-cli
  log "signal-cli updated. Rebuild libsignal if on ARM64 — see channel-setup.md."
fi

# 5. Restart and verify
log "Restarting gateway..."
$SERVICE_CTL start "$SERVICE_NAME".service
sleep 5

if ! $SERVICE_CTL is-active --quiet "$SERVICE_NAME".service; then
  log "ERROR: gateway failed to start after update. Restore from $BACKUP_ROOT"
  exit 1
fi

if ! signal-cli -a "$ACCOUNT" getUserStatus "$ACCOUNT" 2>/dev/null | grep -q ": true"; then
  log "ERROR: Signal account not registered after update. Restore from $BACKUP_ROOT"
  exit 1
fi

log "Update complete. All checks passed."
```

### Graceful Shutdown

The OpenClaw service should include `TimeoutStopSec=30` so signal-cli can flush its state before the process is killed:

```ini
[Service]
TimeoutStopSec=30
KillSignal=SIGTERM
```

---

## When Using This Skill

### If online (web search available)

Before starting, refresh cached data AND fetch OpenClaw docs. This is non-negotiable — the skill caches configs and commands but OpenClaw releases daily and configs change.

**Fetch official docs (do this BEFORE Phase 5, not during debugging):**

1. Fetch `https://docs.openclaw.ai/install` — installation steps, post-install config
2. Fetch `https://docs.openclaw.ai/gateway/security` — auth modes, allowedOrigins, token setup, Control UI pairing
3. Fetch `https://docs.openclaw.ai/gateway/tailscale` — Tailscale Serve config (if user chose Tailscale)
4. Fetch `https://docs.openclaw.ai/channels/<channel>` — channel-specific setup (for Phase 8)

**Refresh version data via web search:**

1. `openclaw latest version release notes` — check for breaking changes vs cached v2026.3.13
2. `signal-cli latest release ARM64` — check if native aarch64 build is now available
3. `<provider> VPS pricing` — verify current prices for the user's chosen provider
4. `tailscale pricing free plan serve` — confirm Serve is still free
5. `openclaw cron job best practices 2026` — new scheduling features or patterns
6. `openclaw agent isolation security` — any new sandbox or per-agent auth features
7. Update the `references/` files if any data changed. Note the new `last_updated` date.

> **Evolutive principle:** OpenClaw releases daily. This skill MUST web-search before any significant decision — don't rely solely on cached configs. If the user's setup uses a feature that has changed, flag it before proceeding.

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
