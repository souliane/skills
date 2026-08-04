# Review Manifest — the enforced completion contract

This file is the **single source of truth** for what a complete review covers. It is
not prose to be skimmed: `cli.py review-checklist` renders it into a working
checklist, and `cli.py review-verify` refuses to pass until every mandatory item is
both ticked **and** carries evidence.

The problem it exists to solve: the review is ~40 mandatory items spread across
1,500 lines of reference prose. An agent reliably runs Phase 0, finds real bugs,
ships them, and reports "review complete" having covered a fraction of the scope —
because nothing structurally distinguished a finished review from an abandoned one.
Coordination-heavy work does not survive in prose (`quality-principles.md`
§ "Paradigm Fitness"). So completion is executable here instead.

## Format

Each item is one line:

```
- [ ] `<id>` <description> <(non-negotiable))>
      evidence: <what you ran / what you found>
```

`review-verify` fails when a `(non-negotiable)` item is unticked, or when any ticked
item has an empty `evidence:`. Evidence must name what was actually run or read —
"done" is not evidence, and a reviewer who writes it is telling on themselves.

An item that genuinely does not apply is ticked with `evidence: n/a — <reason>`.
Declaring something inapplicable is a real judgment that leaves a record; silently
skipping it is what this file prevents.

---

## Phase 0 — Prerequisites

- [ ] `0.1` Verified every in-scope skill dir is a git-tracked source, not a symlink target (non-negotiable)
      evidence:
- [ ] `0.2` Symlink health: maintained skills are live clones, not managed installs
      evidence:
- [ ] `0.3` Uncommitted changes, stashes and stale branches triaged in every managed repo (non-negotiable)
      evidence:
- [ ] `0.4` Open-PR sweep run or explicitly declined by the user (non-negotiable)
      evidence:
- [ ] `0.5` Scope listed and confirmed: every repo named, none silently dropped (non-negotiable)
      evidence:
- [ ] `0.6` Agent memory dirs and repo-level agent config discovered and inventoried
      evidence:
- [ ] `0.7` Every selected SKILL.md, reference, script and hook config READ IN FULL (non-negotiable)
      evidence:
- [ ] `0.8` Companion skills loaded when the condition matches (Python -> ac-python, Django -> ac-django) (non-negotiable)
      evidence:
- [ ] `0.9` `references/quality-principles.md` read before any reviewing began (non-negotiable)
      evidence:

## Phase 1 — Discovery & Architecture

- [ ] `1.1` Dependency graph built; coupling direction checked (generic must not import project-specific)
      evidence:
- [ ] `1.2` Architecture assessment: merge/split/restructure candidates, toolification candidates
      evidence:
- [ ] `1.3` Every skill declares dependencies or states "Standalone"
      evidence:
- [ ] `1.4` Managed-assets inventory built (owned / referenced / instructed)
      evidence:
- [ ] `1.5` Cross-skill and cross-module naming consistency grepped
      evidence:
- [ ] `1.6a` Skill -> code: every referenced CLI command, path and convention verified against the code (non-negotiable)
      evidence:
- [ ] `1.6b` Code -> skill: skills accurately describe current code behaviour (non-negotiable)
      evidence:
- [ ] `1.6c` Cross-repo convention alignment (branch naming, commit format, test structure, CI) (non-negotiable)
      evidence:
- [ ] `1.6d` Shared dependency contracts verified producer-vs-consumer (non-negotiable)
      evidence:
- [ ] `1.6e` Boilerplate factorization: common config/scripts/CI extracted or flagged (non-negotiable)
      evidence:
- [ ] `1.6f` Existing boilerplate copies checked for drift against dependents (non-negotiable)
      evidence:
- [ ] `1.6g` Contract verification at every producer/consumer seam (non-negotiable)
      evidence:
- [ ] `1.6h` Override-contract verification: every overlay method matches a base-class name (non-negotiable)
      evidence:
- [ ] `1.6i` Routing completeness: every skill has a load path (keyword map, agent frontmatter, or slash command) (non-negotiable)
      evidence:
- [ ] `1.7` Silenced quality signals hunted: coverage floors, noqa, excludes, per-file-ignores, missing hooks (non-negotiable)
      evidence:

## Phase 2 — Content Review

- [ ] `2.1` Semantic duplication and diverged copies searched across all skill markdown
      evidence:
- [ ] `2.2` Conciseness pass: filler removed, contradictions resolved
      evidence:
- [ ] `2.3` Personal config and memory files READ END-TO-END and every entry classified (non-negotiable)
      evidence:
- [ ] `2.3b` Cross-repo memory scan: discover, read, classify, privacy-gate, promote, report (non-negotiable)
      evidence:
- [ ] `2.4` Skill vs repo-config boundary respected (reference, don't copy) (non-negotiable)
      evidence:
- [ ] `2.5` Information boundaries: generic skills grepped for project/product/customer names (non-negotiable)
      evidence:
- [ ] `2.6` Buried-knowledge hunt: critical rules surfaced out of project-specific playbooks
      evidence:
- [ ] `2.7` Cross-references programmatically verified to resolve on disk
      evidence:
- [ ] `2.8` No hardcoded home dirs, personal repo names or usernames
      evidence:
- [ ] `2.9` Every Non-Negotiable classified as domain guardrail vs model-limitation guardrail
      evidence:
- [ ] `2.10` Multi-layer promotion: personal -> shared overlay -> open-source core (non-negotiable)
      evidence:

## Phase 3 — Technical Review

- [ ] `3.1` Script language and conventions assessed (shell->Python candidates, uv shebang, Typer)
      evidence:
- [ ] `3.2` Pre-commit hooks audited; enforceable patterns lacking hooks flagged
      evidence:
- [ ] `3.2b` Cross-repo infrastructure harmonized (.pre-commit-config, pyproject, .editorconfig)
      evidence:
- [ ] `3.3` Scripts verified to compile / parse
      evidence:
- [ ] `3.4` Agent-platform hook scripts verified against their trigger events
      evidence:
- [ ] `3.5` Code quality: dead code, complexity, duplication, fallbacks, legacy shims (non-negotiable)
      evidence:
- [ ] `3.5b` Plugin/overlay platform wrappers promoted to core backends; detection grep run (non-negotiable)
      evidence:
- [ ] `3.5c` Comment proportionality: added comments are one line each; multi-line narration flagged as a finding, never gated (Rule 16)
      evidence:
- [ ] `3.6` Security review: secrets, unsafe shell, destructive ops, safety bypasses, licences (non-negotiable)
      evidence:
- [ ] `3.7` CLI-over-MCP preference checked
      evidence:
- [ ] `3.8` Single `scripts/cli.py` entrypoint per skill (non-negotiable)
      evidence:
- [ ] `3.9` `subagent_safe` metadata classified per skill
      evidence:
- [ ] `3.10` Test coverage and quality; regression tests proven to fail against un-fixed code (non-negotiable)
      evidence:
- [ ] `3.10b` Behavioral-eval coverage SUGGESTED for load-bearing skill rules / non-deterministic behaviour
      evidence:
- [ ] `3.11` Upstream-first opportunities considered
      evidence:
- [ ] `3.12` CLI structure, entrypoints and naming coherence across all repos (non-negotiable)
      evidence:
- [ ] `3.13` Documentation freshness; auto-generation hooks present where docs should be generated (non-negotiable)
      evidence:
- [ ] `3.14` Silenced quality signals: each suppression justified or filed (non-negotiable)
      evidence:
- [ ] `3.17` Every setting and extension point the change ADDS is the narrowest shape expressing the variation; refactor triggers acted on (non-negotiable)
      evidence:

## Phase 4 — Quality Review

- [ ] `4.1` Production-grade standard: writing, formatting, no unaddressed TODO/FIXME/HACK
      evidence:
- [ ] `4.2` Attribution present for external sources
      evidence:
- [ ] `4.3` Agent-agnosticism grep; each platform-specific hit justified or generalized
      evidence:
- [ ] `4.4` Attention to detail: typos, grammar, broken links, stale references
      evidence:
- [ ] `4.5` Formatting consistency
      evidence:
- [ ] `4.6` Skill-authoring best practices evaluated
      evidence:

## Phase A — Codebase Assessment

- [ ] `A.1` Deterministic metrics collected for every in-scope repo (non-negotiable)
      evidence:
- [ ] `A.2` File-hierarchy signals run over `git ls-files` (root count, files/dir, depth, oversized, type spread) (non-negotiable)
      evidence:
- [ ] `A.3` §2a-2f judgment: naming, separation, abstraction, coupling, error handling, test architecture
      evidence:
- [ ] `A.4` §2g state & data architecture: one authoritative store per runtime fact; detectors run (non-negotiable)
      evidence:
- [ ] `A.5` §2h file hierarchy judged; concrete prioritized `from -> to` moves emitted (non-negotiable)
      evidence:
- [ ] `A.5b` §2i prose about code: comment proportionality and documentation currency judged; reported, never gated
      evidence:
- [ ] `A.5c` §2j duplication & factorization: repeated logic across scripts/modules/repos judged; extraction target named or duplication recorded as deliberate (non-negotiable)
      evidence:
- [ ] `A.6` Three scores produced: cleanliness, maintainability, architecture (1-10) (non-negotiable)
      evidence:
- [ ] `A.7` Ranked improvement list with Impact/Effort/Affected-files per item (non-negotiable)
      evidence:

## Phase 5 — Plan & Implement

- [ ] `5.1` Structured change plan compiled from all findings, grouped by repo and type (non-negotiable)
      evidence:
- [ ] `5.2` Ambiguous items raised with the user one question at a time (non-negotiable)
      evidence:
- [ ] `5.3` Ownership checked against MAINTAINED_SKILLS before each file edit (non-negotiable)
      evidence:
- [ ] `5.4` Approved changes implemented this session, not postponed (non-negotiable)
      evidence:

## Phase 6 — Regression & Delivery

- [ ] `6.1` Changes committed
      evidence:
- [ ] `6.2` Second full review pass over the delta (non-negotiable)
      evidence:
- [ ] `6.3` `prek run --all-files` green
      evidence:
- [ ] `6.4` Follow-up commit if the second pass produced fixes
      evidence:
- [ ] `6.5` Definition of done: re-running this review on the same scope yields zero new findings (non-negotiable)
      evidence:
- [ ] `6.6` Own commits squashed into human-sized units
      evidence:
- [ ] `6.7` Delivery status reported across all managed repos
      evidence:
- [ ] `6.8` Retro run (non-negotiable)
      evidence:
