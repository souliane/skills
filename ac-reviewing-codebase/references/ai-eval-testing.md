# Testing AI-Evaluated Behavior — read when a repo ships skills or non-deterministic agent behavior

Most of this skill's checks assume deterministic code: a function with one
correct output, gradeable by an assertion. Skills and agent prompts are
different — their "output" is *a model's behavior*, which is non-deterministic
and not assertable with `==`. A skill can read perfectly and still fail to
change what the agent does; a rule the author believes is enforced can silently
regress when the model drifts. This file describes how to **suggest** that such
behavior be put under test — not how to enforce it.

## Suggest, never enforce (Non-Negotiable framing)

This is a **suggestion**, conditional and per-case:

- **Only suggest it when the repo has no equivalent mechanism already.** If the
  repo already has a working way to test its non-deterministic behavior (its own
  eval harness, a baseline-vs-skill subagent comparison, the Anthropic
  skill-creator eval pipeline, a custom LLM-judge), do **not** push this one on
  top — note that coverage exists and move on. Two competing eval mechanisms in
  one repo is itself a finding.
- **Suggest partly or completely.** A repo may want only the cheap deterministic
  layer (trigger/activation checks) and not a paid model-run suite, or only an
  embedded per-skill spec and not a portfolio-wide integration suite. Recommend
  the smallest slice that closes the actual gap you observed.
- **Match the suggestion to a real gap.** Recommend evals where you saw (or can
  point to) a behavior that *should* be observable-and-gated: a Non-Negotiable
  rule with no test, a recurring correction the author keeps re-applying by
  hand, a skill whose prose changed but whose effect on the agent was never
  verified. "Every correction is a skill bug" — and a skill bug, like any bug,
  wants a regression test.

## Two altitudes of AI eval

Distinguish these when reviewing — they answer different questions and a repo
may have one without the other:

1. **Embedded per-skill behavioral evals.** Co-located with the skill (e.g.
   `<skill>/evals/*.yaml` or a shared `scenarios/` catalog with
   `agent_path: <skill>/SKILL.md`). They answer "does *this skill* make the
   agent do the right thing?" — one skill under test, a concrete prompt, a
   graded trajectory. This is the unit-test altitude for skills.
2. **Upper-level integration AI evals.** Cross-skill / cross-overlay scenarios
   that pin a *system* behavior — e.g. "every review task loads the skill set
   the active overlay declares", which spans the routing code, the overlay
   config, and several skills at once. They answer "does the whole assembly
   route/compose correctly?" This is the integration altitude.

A reviewer checks for **both**, and suggests whichever is missing for the
behavior at hand: a freshly written or changed skill wants (1); a new
routing/composition/orchestration rule wants (2).

## The mechanism (so you can describe it when suggesting it)

A concrete, working reference implementation of this pattern is teatree's
behavioral-eval harness (`t3 eval`); the shape generalizes to any skill repo.
A reviewer should be able to describe it well enough to recommend it.

### EvalSpec — one scenario

A scenario hands one `SKILL.md` to a one-shot `claude -p` session, watches the
resulting `stream-json` transcript, and asserts the agent reached for the right
tool calls (and avoided the wrong ones). The point is to convert "the agent
knows this rule" into "the agent's compliance is **observable and gated**", so
a regression surfaces as a red test instead of a recurring red-card moment.

```yaml
- name: worktree_first                 # unique id; the test id
  scenario: agent must create a worktree before editing the canonical clone
  agent_path: skills/code/SKILL.md     # the single skill under test
  model: haiku                         # cheap tier; cost is cents per run
  max_turns: 3
  tools: [Bash]
  prompt: >-
    You are working in <path>. ...     # hermetic: no real network, no secrets
  expect:
    - tool_call: bash                  # POSITIVE — such a call must exist
      args.command: contains "git worktree add"
    - no_tool_call_matching:           # NEGATIVE — such a call must NOT exist
        bash.command: ~ "Edit.*README\\.md"
```

Matcher operators: `contains "<substring>"` and `~ "<regex>"`. `any_of: [...]`
expresses a disjunction of equally-valid positive branches (e.g. "background
the long op via a `Task` dispatch OR a Bash call with `run_in_background:
true`") so a compliant trajectory taking either branch stays green instead of
over-fitting one phrasing.

### Anti-vacuity — the part reviewers most often miss

A scenario built only of negative matchers (`no_tool_call_matching`) is
**trivially satisfied by an agent that does nothing**. A toothless matcher that
passes on every transcript provides false confidence — worse than no test. The
defense is fixtures plus a meta-test:

- **`<name>_pass.stream.jsonl`** — a compliant transcript; the scenario must go
  GREEN.
- **`<name>_fail.stream.jsonl`** — a regressing transcript that makes exactly
  the forbidden call; the scenario must go RED.
- **`<name>_noop.stream.jsonl`** — a transcript with *no tool calls at all*; the
  scenario must go RED. This is what proves the spec is non-vacuous: it forces
  every scenario to carry at least one *positive* matcher that a do-nothing run
  fails.

A meta-test (teatree: `tests/eval/test_scenarios_anti_vacuous.py`) runs all
three directions for every shipped scenario on **every PR**, so a matcher that
cannot catch its own regression cannot merge. **When you review an eval suite,
this is the first thing to check** — a suite without anti-vacuous fixtures is
the eval-equivalent of tests with no assertions.

### LLM-judge — for the non-matcher-gradeable rules

Some behaviors don't reduce to "a tool call with arg X containing Y exists":
tone ("stays non-blaming"), faithfulness ("the explanation matches the diff it
actually made"), "did it actually answer the question". A scenario opts into an
LLM judge with a `judge:` block carrying a `rubric`; a judged scenario passes
only when its matchers pass **and** the judge returns PASS. Cost is bounded by
construction: a cheap default judge tier, a per-call budget cap, a per-output
token cap, and a per-run cap on the number of judge calls. When `claude` is not
on PATH the judge skips rather than failing by absence. Default to deterministic
matchers; reach for the judge only when the rule is genuinely subjective.

### Regression + generalization

A robust suite tests two directions:

- **Regression** — the exact must-do case is named in the prompt. Catches the
  specific failure that prompted the test.
- **Generalization** — a *held-out* case where the prompt states the *rule* but
  withholds the specifics, so a green trajectory has to *derive* the right
  action rather than pattern-match the prompt. A generalization scenario whose
  prompt enumerated the answer would only test instruction-following, not the
  rule. (teatree example: a coding scenario says "load the language bible that
  matches THIS service's language" without naming it — loading the wrong bible
  by pattern-matching a sibling case FAILS.)

Pair these with **negative** scenarios (the over-load / over-fire direction): a
gate that must allow as well as block, a skill that must *not* fire on a control
prompt. A pass-only suite hides the symmetric failure.

### Deterministic layers run free on every PR; paid model runs are rare

Not every eval needs a paid model run. Teatree's harness has cheap, free,
deterministic layers that gate every PR through the normal pytest run, with the
paid `claude -p` scenario run reserved for a low cadence (weekly):

- **Trigger/activation QA** — load each skill's trigger keywords and check a
  must-fire / must-not-fire prompt corpus. Catches under-triggering (in-scope
  prompt that doesn't fire the skill) and over-triggering (control prompt that
  does). No model run.
- **Regression corpus** — where a scenario grades what an agent *says* it would
  do, this grades what the gate/checker *code does*: each check calls the **real**
  function for a recurring failure class on a constructed must-block input and a
  must-allow input, reporting a violation when either direction is wrong. Each
  check carries a clickable `origin` (the fix PR/issue) and the `invariant` it
  pins, and ships with an anti-vacuous test proving a deliberately-broken
  stand-in turns it RED.

**Prefer the deterministic layer every time it applies** — a code-enforceable
rule ("scanner skips MRs the user authored") belongs in a normal pytest test
that mocks the boundary and asserts the side-effect is absent, not in a paid
eval scenario. Reserve transcript scenarios for what code-level tests cannot
reach: behaviors that constrain what the agent *says* or *invokes* rather than
what a code path *does*.

### Discovery: core + overlay

Scenarios live in a core catalog and each installed overlay contributes its own
directory via a hook (teatree: `OverlayBase.get_eval_scenarios_dir()`), so the
core catalog stays project-agnostic (placeholder identities like `widget-user`)
while an overlay supplies real tenant identities and overlay-specific scenarios.
Discovery is isolated: a broken overlay is logged and skipped, never failing the
whole catalog.

## Reviewer checklist (what to actually do)

When a repo ships skills or other AI-evaluated (non-deterministic) behavior:

1. **Does AI-evaluated behavior have *any* test?** If the repo already has an
   eval mechanism, verify it actually bites (run the anti-vacuity check below)
   and stop — do not propose a second mechanism.
2. **Embedded per-skill evals.** For each maintained skill carrying or changing
   a behavioral Non-Negotiable, is there a co-located or cataloged spec with
   `agent_path` pointing at it? If a skill's prose changed but no spec verifies
   the effect, suggest one (smallest slice that covers the changed rule).
3. **Integration AI evals.** For cross-skill routing/composition/orchestration
   rules, is there an upper-level scenario pinning the *system* behavior? Suggest
   one when a new such rule lands without coverage.
4. **Anti-vacuity (the toothless-matcher check).** For any eval suite present:
   does each scenario ship a fail fixture (and a noop fixture for negative-only
   specs), with a meta-test asserting RED on fail/noop and GREEN on pass? A suite
   without this is providing false confidence — flag it.
5. **Regression *and* generalization, positive *and* negative.** Flag pass-only
   / regression-only suites that can't catch over-fire or fail-to-generalize.
6. **Cost discipline.** Deterministic layers (trigger QA, real-code regression
   corpus) on every PR; paid model runs at a low cadence with budget caps and a
   PATH-absent skip. Flag a suite that runs paid model calls on every push.
7. **Conditional suggestion.** Recommend partly or completely, matched to the
   gap, and only where it does not conflict with a mechanism the repo already
   uses.

## How third parties frame the same idea (inspiration, not dependency)

The "test skills against a baseline" idea is convergent across the ecosystem —
useful framings to borrow when explaining a suggestion:

- **Anthropic skill-creator eval pipeline** — `evals/evals.json` (prompt +
  expected output + assertions), parallel **with-skill vs baseline** subagent
  runs, a **grader** subagent scoring assertions, a **benchmark** aggregating
  pass-rate / tokens / time, and an optional **blind A/B comparator** that judges
  two outputs without knowing which is which. Anthropic's own stance: evals are
  **suggested for objectively-verifiable skills, optional for subjective ones** —
  the same conditional posture this file takes. A genuine companion-skill
  candidate (the user must decide whether to adopt it as a standing dependency).
- **obra/superpowers `writing-skills` / `test-driven-development`** (MIT) — a
  RED/GREEN/REFACTOR loop *applied to skills*: run a pressure scenario in a
  subagent **without** the skill and document the violation (RED), add the
  minimal skill content, re-run **with** the skill until the agent complies
  (GREEN), and when the agent finds a new rationalization, add an explicit
  counter and re-test (REFACTOR) — "no skill without a failing test first". A
  good lightweight framing when a full harness is overkill.
- **Anthropic "Demystifying evals for AI agents"** — eval-driven development:
  build the evals first, write minimal instructions to pass them, and use an LLM
  judge for behaviors deterministic checks can't reach.

## References

- [Anthropic skill-creator (anthropics/skills)](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) — eval / benchmark / blind-A-B pipeline
- [Anthropic — Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [obra/superpowers `writing-skills`](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md) (MIT) — RED/GREEN/REFACTOR skill testing
