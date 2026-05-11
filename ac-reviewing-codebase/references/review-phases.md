# Review Phases 2-4 — read during the corresponding review phase

Detailed checklists for content review, technical review, and quality review. Load this file when entering Phase 2 of the review workflow.

## Phase 2 — Content Review

### 2.1 Duplication & Diverged Copies

- Search for **semantic** duplication across all reviewed skills' markdown files. Two paragraphs saying the same thing in different words count as duplication — not just identical text.
- **Prefer inter-skill dependency over duplication.** When two skills share knowledge, put it in one skill and make the other declare a dependency.
- **Guard agnosticism.** A generic/framework skill must not absorb project-specific details. **Ask the user if in doubt.**
- **Diverged copies** are the most dangerous form: grep for distinctive phrases and compare versions across files. If they differ, one is stale.
- **Cross-cutting rules** (rules that apply to ALL skills) need a dedicated shared reference file rather than being duplicated in each skill.

### 2.2 Conciseness & Length Reduction

- Every sentence must earn its place. Remove filler, redundant explanations, over-qualification.
- **Actively reduce skill length.** Shorter skills get read and followed; long skills get skimmed.
- Never sacrifice completeness for brevity — the goal is concise AND complete.
- **Resolve conflicts.** When two instructions contradict each other, determine which is correct and delete the other.

### 2.3 Self-Sufficiency & Knowledge Placement

- Check the user's **personal config files** for content that **belongs in the skill itself**.
- Common misplacements: guardrails → skill's `SKILL.md`; troubleshooting → `references/troubleshooting.md`; patterns → playbooks.
- **Skills must ask for what they need.** If a skill requires user-specific info, it must check memory/config and ask if not found.

**Active promotion from personal config (Non-Negotiable):**

During every review, **read the user's personal config and memory files end-to-end**. Classify each entry:

| Category | Action |
|---|---|
| Guardrail / "do this, not that" | Promote to skill |
| Troubleshooting entry | Promote to `references/troubleshooting.md` |
| Workflow pattern | Promote to playbook or skill workflow |
| User preference (formatting, tone) | Keep in personal config |
| Environment-specific fact (paths, credentials) | Keep in personal config |
| "Safety net" duplicate | Keep — verify skill source is up to date |

### 2.3b Cross-Repo Memory Scan (Non-Negotiable)

Skills reference code repos. Each code repo may have agent memory files containing guardrails and patterns that belong in skills.

1. Discover referenced repos from Phase 1 § 1.4 (Managed Assets Inventory, defined in SKILL.md).
2. Find memory directories for each repo.
3. Read and classify each memory file using the table from § 2.3.
4. **Privacy gate before promotion.** Check if target skill is public — generalize internal details.
5. Promote and clean up.
6. Report: files scanned, promoted, kept, deleted as stale.

### 2.4 Skill ↔ Repo Config Boundary (Non-Negotiable)

- **Do not copy rules from a repo's agent instruction files into skill files.** Reference them instead.
- **When a skill adds extra detail**, reference the repo file for the base rule.
- **Duplication is tolerated ONLY when fully acknowledged** with source attribution.

### 2.5 Information Boundaries

- Generic/framework skills must not contain project-specific or proprietary details.
- **Active scan (non-negotiable).** Grep all reviewed skill files for project names, product names, customer names, internal hostnames. Any hit in a generic skill is a blocker.

### 2.6 Knowledge Consolidation (Buried Playbook Problem)

Critical knowledge frequently gets buried in project-specific troubleshooting sections. The agent violates a rule not because it disagrees, but because it never sees it.

**Remediation:** Promote within the skill, move up the abstraction layer, pair prohibitions with positive procedures, cross-reference both directions.

### 2.7 Cross-References

- Verify all cross-references are accurate.
- **Programmatic verification:** extract relative paths from markdown links and verify targets exist on disk.

### 2.8 No Personal or Hardcoded Paths

- Grep all skill files for: hardcoded home directories, personal repo names, hardcoded usernames.
- Replace with env vars or placeholders.

### 2.9 Guardrail Classification

Classify each Non-Negotiable rule:

- **Domain guardrail** — encodes knowledge the model will never learn from training data. **Never relax.**
- **Model-limitation guardrail** — compensates for current model weaknesses. **Review periodically.**

### 2.10 Multi-Layer Skill Overlap & Promotion (Non-Negotiable)

When a skill ecosystem spans multiple layers (open-source → shared overlay → personal config), **actively promote knowledge upward**:

1. **Personal → Shared overlay.** Knowledge in personal config files that would benefit colleagues belongs in the team/project overlay. Promote guardrails, patterns, and troubleshooting entries that are not user-specific.
2. **Shared overlay → Open-source core.** Knowledge in a private overlay that is not project-specific belongs in the open-source skill or tool. Strip proprietary details (customer names, internal URLs, team-specific processes) and generalize.
3. **Detection:** For every entry in personal config or overlay-specific files, ask: "Is this portable? Would someone outside my team benefit from this?" If yes, promote it.
4. **Clean up after promotion.** Remove the personal/overlay copy once the content lives in the right layer. Keep cross-references if the personal copy added project-specific detail on top of the promoted generic rule.

---

## Phase 3 — Technical Review

### 3.1 Script Language & Conventions

- **Shell → Python assessment.** Shell scripts with non-trivial logic are candidates for Python conversion.
- **Python script standards.** Use: uv shebang, uv inline metadata, Typer for CLI.
- **Ask before converting** existing scripts.

### 3.2 Pre-Commit Hooks

- Audit existing hooks. Are there enforceable patterns that lack hooks?
- Verify hook file patterns correctly match intended files.
- **Co-location:** When a skill moves, its hooks move with it.

### 3.2b Cross-Repo Infrastructure Harmonization

Compare `.pre-commit-config.yaml`, `pyproject.toml`, `.editorconfig`, and utility scripts across repos. See `references/repo-management.md` § Infrastructure Audit for the full workflow.

### 3.3 Script Verification

- Python: `python3 -m py_compile <file>`, verify imports resolve.
- Shell: `bash -n <file>`.
- Do NOT run scripts with side effects.

### 3.4 Hook Scripts (Agent Platform Hooks)

Verify agent platform hook scripts are correct and functional. Check event types match intended trigger points.

### 3.5 Code Quality & Simplification

- **Dead code.** Grep for unused functions, unreachable branches, commented-out blocks.
- **Complexity.** Flag functions >50 lines or with 3+ nesting levels.
- **Duplication across scripts.** Extract shared logic when 3+ copies exist.
- **Test quality.** Verify tests cover important paths, not just happy path.
- **Readability.** Meaningful names, consistent conventions, self-explanatory code.
- **Factorization (Non-Negotiable).** Duplicated logic across scripts, repos, or skills is a finding. Extract to shared module or tool. When unsure if duplication is intentional — ask the user.
- **Fallbacks are code smells (Non-Negotiable).** Code that tries multiple approaches ("if this fails, try that") hides real issues. Stick to one way of doing things. Fallbacks are especially common in agent-generated code — agents workaround for hours with dirty hacks instead of fixing the root cause. Flag every fallback and ask: "Why does the primary path fail? Fix that instead."
- **Legacy compatibility shims are code smells.** Code that preserves old behavior (deprecated aliases, backward-compat wrappers, unused re-exports) accumulates silently. When found, ask the user: "Is this still needed, or can we remove it?" If removal requires deprecation, propose a timeline. Default stance: remove unless the user explicitly says to keep.

### 3.5b Promote Plugin/Overlay Wrappers to Core Backends (Non-Negotiable)

When the codebase has a plugin or overlay architecture with **typed core backend protocols** (e.g., teatree's `CodeHost`, `CIService`, `IssueTracker`, `ChatNotifier`, `ErrorTracker` in `backends/protocols.py`), every plugin/overlay method that performs platform-API work belongs on a core backend, not on the plugin.

**A plugin method is a promotion candidate when its body contains any of:**

- HTTP calls (`urllib.request`, `requests`, `httpx`, `aiohttp`, raw `socket`).
- Platform CLI shellouts (`gh`, `glab`, `slack-cli`, `notion-cli`, `sentry-cli`, `aws`, `gcloud`).
- Platform SDK clients (`Github(...)`, `gitlab.Gitlab(...)`, `WebClient(...)` for Slack, `boto3.client(...)`).
- File parsing of well-known platform formats (GitLab MR JSON, GitHub PR API responses, Slack event payloads).

**Promotion rule.** A plugin method that wraps a platform API is duplication waiting to drift — a second plugin will reimplement it differently, the API behavior will silently diverge, and pagination/auth/error handling will be missing in at least one copy. The fix:

1. **Identify the matching core protocol.** If one already exists (e.g., `IssueTracker.get_issue` for "fetch issue title"), the plugin method should delegate to it.
2. **If no matching protocol exists**, propose adding one — and gate the proposal on at least 2 plugins needing the same wrapper, or 1 plugin + a clear reuse case.
3. **Move the implementation** behind the backend, then delete the plugin override (or shrink it to a thin delegator).

**Detection grep (run during the audit):**

```bash
# Inside the plugin/overlay source root:
rg -nP '\b(urllib|requests|httpx)\.(request|get|post|put|delete|urlopen)\b|subprocess\.run.*\b(gh|glab|slack|notion|sentry-cli|aws|gcloud)\b' \
   src/<plugin_pkg>/
```

Any hit inside a method that the core extension API names (e.g., overlay base classes, plugin interfaces) is a finding.

**Worked example.** A plugin's `get_issue_title(url)` calls `urllib.request.Request(api_url)` with a `PRIVATE-TOKEN` header for GitLab and `subprocess.run(["gh", "issue", "view", ...])` for GitHub. The core protocol already exposes `IssueTracker.get_issue(url)` with the same intent. Recommendation: change the default `OverlayMetadata.get_issue_title()` to delegate to `IssueTracker.get_issue(url).get("title", "")` and delete the plugin override.

**Why this is not just "factorization" (3.5).** Factorization catches duplicate code within one repo. This check catches duplication across the **plugin boundary**, where the core has already provided a typed extension API but the plugin author either didn't know about it or grew the wrapper organically before the protocol existed. The first instance looks legitimate; the second instance is the pattern.

### 3.6 Security Review

- No hardcoded secrets. Grep all files for tokens, passwords, API keys.
- No unsafe shell patterns (unquoted variables, `eval` on user input).
- No destructive operations without confirmation.
- No instructions that bypass safety (`--no-verify`, disable SSL).
- **Supply chain license compatibility.** Check every dependency's license.

### 3.7 CLI vs MCP Tool Preference

Prefer native CLI tools over MCP when available. Grep for `mcp__` references and check for CLI equivalents.

### 3.8 Single CLI Entrypoint per Skill (Non-Negotiable)

Each skill with scripts must have exactly one `scripts/cli.py` using Typer.

### 3.9 Sub-Agent Safety Classification

Check each skill's `subagent_safe` metadata field. A skill is safe for sub-agents only if it is pure methodology with no dependency on shell functions, MCP tools, env vars, or running services.

### 3.10 Test Coverage & Quality

- Flag scripts without tests.
- Verify existing tests pass.
- **Integration-first check.** Happy paths = integration tests; unit tests = edge cases and error branches.
- **Test conciseness.** Flag: copy-pasted tests (use parametrize), repeated setup (use fixtures), over-mocking.

### 3.11 Upstream First

Look for opportunities to contribute upstream instead of maintaining custom workarounds.

### 3.12 CLI Structure, Entrypoints & Naming Coherence (Non-Negotiable)

Every codebase has entrypoints — CLI commands, API endpoints, module paths, file hierarchies. These are the public interface of the project. Incoherence here creates confusion and maintenance debt.

**CLI commands:**

- **Naming convention.** Are commands consistently named? Pick one style (verb, noun, verb-noun) and stick with it across all commands. Inconsistent naming (e.g., `check` vs `show-config` vs `run_tests`) is a finding.
- **Argument naming.** Are flags consistent across subcommands? If one command uses `--root` for a directory path and another uses `--path`, that's a finding. Same concept = same flag name.
- **Help text.** Does every command and flag have a help string? Is the help discoverable (`--help` at every level)?
- **Exit codes.** Consistent exit mechanism. Don't mix `raise SystemExit()` with `raise typer.Exit()` or `sys.exit()`. Pick one pattern.
- **Subcommand organization.** Are related commands grouped? Is the command tree shallow enough to discover? Deep nesting (3+ levels) without good reason is a finding.

**Module paths and file hierarchy:**

- **Directory structure.** Does the file hierarchy mirror the logical structure? Are files where you'd expect them?
- **Naming coherence.** Are modules, directories, and files named consistently? Same naming convention (kebab-case dirs, snake_case modules, etc.) throughout.
- **Single entrypoint per skill/package.** One CLI entrypoint (`cli.py`), one main module, one `__init__.py` that exports the public API. Multiple competing entrypoints = confusion.
- **Private vs public.** Functions/classes not intended for external use should be prefixed with `_`. Public functions that are only called internally are a finding.

**Cross-repo coherence:**

- When multiple repos in the portfolio have CLIs, verify they follow the same conventions: same argument names for the same concepts, same output formats, same exit code semantics.
- Flag gratuitous differences between sibling CLIs.

### 3.13 Documentation Freshness (Non-Negotiable)

- **Check that docs match code.** README, BLUEPRINT, generated API docs, architecture diagrams — verify they reflect current state. Stale docs that describe removed features or outdated CLI commands are findings.
- **Auto-generation hooks.** For documentation that should be auto-generated (API docs, CLI help, diagram renders), verify the generation hook exists in pre-commit or CI. Missing auto-generation = finding.
- **Detect manual maintenance debt.** If docs are manually maintained and frequently drift from code, recommend adding auto-generation. Propose specific hooks (e.g., `typer-cli generate` for CLI docs, mermaid pre-commit for diagrams).

### 3.14 Silenced Quality Signals (Non-Negotiable)

Hunt for manually suppressed code quality signals — these represent deliberate decisions to hide problems.

- **Lowered coverage thresholds.** Check `fail_under` values, `--no-cov` usage.
- **Suppressed lint rules.** Grep for `# noqa`, `# type: ignore`, `# pragma: no cover`. Each must be justified.
- **Excluded files from pre-commit.** Check `exclude:` patterns — justified or deferred?
- **Relaxed per-file-ignores.** Check broad patterns in ruff config. To test whether a rule is stale, remove it from the config block and run the full `ruff check <glob>` — not `ruff check --select <rule>`, which ignores the project's `preview` and `select = ["ALL"]` config and produces false "stale" results. A rule is stale only if zero violations surface when the full project config runs with that rule removed.
- **Missing hooks.** Compare against the infrastructure baseline.
- **Stale type-checker allowlists.** `ty`/`mypy`/`pyright` allowlists for unresolved imports accumulate — third-party libs get proper stubs over time. Test each entry by removing it and re-running the type checker; zero new errors = stale.
- **Companion skill violations.** When `ac-python` or `ac-django` are loaded, verify the codebase follows their conventions (integration-first testing, fat models, proper typing, correct manager usage).

### 3.15 Override Contract Verification (Non-Negotiable)

For overlay/plugin architectures with composed classes (e.g., `OverlayMetadata`, `OverlayConfig`), verify that every method the overlay defines actually overrides a base class method with the same name. Concrete check:

```bash
# List overlay methods (excluding private):
grep -n 'def ' <overlay>/overlay/*.py | grep -v '__'
# For each, verify the name exists on the base class:
grep -n 'def <method_name>' <core>/overlay.py
```

A method on the subclass with no match on the base class is either a broken override (silently dead code — the caller invokes the base class no-op) or a new extension (should be declared abstract/default on the base). Bulk renames (MR→PR, sync→fetch) are the #1 cause: one side gets renamed, the other doesn't, and tests pass because they test each side in isolation.

### 3.16 Routing Completeness After Skill Extraction (Non-Negotiable)

When a skill is extracted from another (e.g., `e2e` from `test`), verify the routing infrastructure was updated:

1. **Keyword maps.** Check `_AGENT_TASK_KEYWORDS` — the extracted skill's keywords must move to their own entry, not stay on the parent.
2. **Phase maps.** Check `_PHASE_TO_SKILL` — the extracted skill needs its own phase entry.
3. **Agent definitions.** Check `agents/*.md` — there must be an agent that lists the extracted skill in its `skills:` frontmatter.
4. **Orchestrator routing.** Check the orchestrator's keyword→agent table — extracted skill keywords must route to the correct agent.
5. **Keyword overlap.** Both parent and child should not trigger on the same keywords — the parent should drop the extracted keywords.
6. **`subagent_safe` consistency.** If the skill is `subagent_safe: false`, it must NOT appear only on agents that are sub-agents with no main-conversation path.

---

## Phase 4 — Quality Review

### 4.1 Production-Grade Standard

Every skill should be production-grade: clear writing, consistent formatting, no TODO/FIXME/HACK unaddressed.

### 4.2 Attribution

Proper credit for external sources as a `## References` section.

### 4.3 Agent Agnosticism Check

Grep for platform-specific terms (agent brand names, paths, tool names). Classify each hit and generalize where needed.

### 4.4 Attention to Detail

Typos, grammar, inconsistent capitalization, broken/outdated links, stale references.

### 4.5 Formatting Consistency

Consistent heading hierarchy, list style, code block annotations, YAML frontmatter.

### 4.6 Skill Authoring Best Practices

Evaluate against [`references/skill-authoring-best-practices.md`](skill-authoring-best-practices.md). Key checks: frontmatter spec, conciseness, progressive disclosure, degrees of freedom, consistent terminology, scripts over prose, evaluation-driven development.

---

## Phase 6 — Regression Review

### 6.1 Commit

Always commit after implementation. Suggest squashing fixup commits. **Never rewrite settled commits.**

### 6.2 Second Pass

Full second review pass. Changes can introduce regressions: broken cross-references, new duplication, formatting inconsistencies.

### 6.3 Pre-Commit Verification

Run `prek run --all-files`. Fix failures.

### 6.4 Final Commit

If the second pass produced fixes, create a follow-up commit. Run pre-commit again.

### 6.5 Definition of Done

**"Done" means re-running this review on the same scope produces zero new findings.** Before claiming complete:

1. Re-run Phases 2-4 mentally on every file changed.
2. If any check would produce a new finding, fix it now.

### 6.6 Retro & Iteration

Run retro skill if available. If user requests iteration, loop back to Phase 1 with narrower focus. Stop when a pass produces zero findings.
