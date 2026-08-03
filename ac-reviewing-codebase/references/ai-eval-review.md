# AI-Eval Review — read when a reviewed repo contains skills or non-deterministic, AI-evaluated behavior

A reference for **suggesting** behavioral-eval coverage during review. Deterministic tests (ruff, unit tests, coverage) grade what a code path *does*. They cannot reach what a `SKILL.md` instructs an agent to do, or whether a non-deterministic, LLM-driven behavior actually holds at runtime. Those need **behavioral evals**: a prompt is handed to a real agent run, and matchers (or an LLM judge) assert the resulting trajectory reached for the right tool calls and avoided the wrong ones.

## When to raise it (and when not to)

**Suggest** behavioral-eval coverage when both hold:

1. The reviewed artifact is a **skill** (a `SKILL.md` encoding a load-bearing rule) **or** runtime behavior whose correctness depends on what an LLM agent *says* or *invokes* (routing, "did it actually answer", tone, "claimed done without evidence").
2. The behavior has either **bitten before** (a recurring failure class) or is **load-bearing** (a wrong trajectory is costly or hard to detect).

**Do not raise it** — this is the conditional, non-enforcing part — when:

- The behavior is fully **code-enforceable**. If a rule reduces to "this function returns False on this input", it belongs in a deterministic test (cheaper, runs every PR for free), not a paid agent run. Prefer the deterministic layer every time it applies.
- The repo **already has** its own eval / behavioral-test mechanism. Align with that one; never layer a second, parallel mechanism on top. The suggestion is "cover this behavior in the way this repo already covers behavior", not "adopt my framework".
- The skill is purely **subjective / stylistic** (writing voice, design taste) with no objectively-verifiable assertion — forcing a matcher onto it produces a brittle, low-value eval.

The suggestion is also **partial by default**: propose evals for the *load-bearing* rules of a skill, not every sentence. "Cover the routing rule and the do-the-minimum rule" beats "add evals for everything".

## Two coverage tiers

Distinguish these in the finding — they answer different questions:

| Tier | Question it answers | Where it lives | Grades |
|---|---|---|---|
| **Per-skill embedded eval** | "Does a compliant trajectory follow *this skill's* rule?" | Co-located with the skill (`evals/*.yaml` or `eval/scenarios/*.yaml`) | One `SKILL.md` in isolation |
| **Upper-level integration AI eval** | "Across skills/overlays, does the right behavior emerge end-to-end?" | A central scenarios directory + per-overlay contributed dirs | The real selection / handoff logic, not one skill alone |

A per-skill eval pins the rule a single skill teaches. An integration eval pins emergent, cross-cutting behavior — e.g. "a task touching an overlay repo loads the overlay skill set, including the language bible, before editing", which no single `SKILL.md` fully owns. A portfolio that only has per-skill evals can still regress at the seams; one that only has integration evals can't localize *which* skill drifted. Suggest whichever tier the gap is in.

## The mechanism (so the finding is concrete, not vague)

This is the shape to point at when suggesting "add an eval like this". It is one concrete, working design taken from a lifecycle tool's `EvalSpec` harness; a repo with its own conventions should follow those instead.

### Scenario shape (EvalSpec)

Each scenario is a YAML spec: a prompt handed to a one-shot agent run (`claude -p` in `stream-json` mode), watched for the tool calls it makes.

```yaml
- name: register_routes_to_service        # unique id
  scenario: founding routes to the free service, not a DIY self-form-fill
  agent_path: <skill>/SKILL.md            # the SKILL.md under test
  model: haiku                            # cheap tier — keep cost in cents
  max_turns: 4
  tools: [Bash]
  prompt: >-
    Phrase the task so the agent RUNS concrete tool calls (echo the URL /
    verdict it would use) — matchers grade the trajectory, and a knowledge
    skill otherwise emits only text.
  expect:
    - tool_call: bash                     # POSITIVE: such a call must exist
      args.command: contains "book.service.example/wko"
    - no_tool_call_matching:              # NEGATIVE: such a call must NOT exist
        bash.command: ~ "usp\\.gv\\.at.*(form|fill|self)"
```

### Pass / fail / no-op — the anti-vacuous pairing

The core robustness idea: an eval that only checks "the right call happened" passes **vacuously** on a transcript where the agent did *nothing*. Each scenario therefore pairs a **positive** matcher (the right action *must* appear) with a **negative** `no_tool_call_matching` (the wrong action *must not* appear). The no-op transcript fails the positive matcher; the wrong-action transcript fails the negative one. Only a genuinely-compliant trajectory passes both.

Pin this at *test* time, not just in production, with **fail/pass fixtures**: ship a recorded `<name>_fail.stream.jsonl` where the agent makes exactly the forbidden call, and assert the scenario goes RED on it (and GREEN on a `<name>_pass` fixture). A matcher-toothless scenario is then caught by the test suite, not discovered when a real regression slips through. When suggesting an eval, suggest its fail-fixture too — an eval without one is a check whose teeth are unverified.

Matcher operators worth naming: `contains "<substring>"`, `~ "<regex>"`, and `any_of: [...]` — a disjunction of positive branches for "either of these equally-valid actions satisfies the rule", so the eval doesn't over-fit to one acceptable trajectory.

### Regression vs generalization

Two directions, both worth suggesting for an integration suite:

- **Regression** — the prompt names the exact must-do case. Catches the specific failure that prompted the eval. Necessary but not sufficient: a trajectory can pass by pattern-matching the prompt.
- **Generalization (held-out)** — the prompt states the *rule* but withholds the specifics, so a green trajectory has to *derive* the right action itself. Example: "load the language bible that matches this service's language" (without naming `ac-python` vs `ac-django`) tests routing-by-language, not instruction-following. A generalization scenario whose prompt enumerated the answer would only test obedience, not the rule.

### The LLM judge (for what matchers can't grade)

Matcher grading is the default — deterministic, free, right for "a call with arg X containing Y exists". Some behaviors don't reduce to that: "the explanation is faithful to the diff", "the tone stays non-blaming", "it actually answered". A scenario opts into an **LLM judge** with a `judge:` block:

```yaml
  judge:
    rubric: |
      The explanation names every file it changed and claims no change it
      did not make.
    model: haiku            # cheap tier
    max_output_tokens: 512  # one line, not an essay
```

A judged scenario passes only when its matchers pass **and** the judge returns `PASS`. A judge that returns no clear verdict is treated as FAIL (it must not pass a scenario by inability to decide). Cost is bounded by construction: cheap model tier, a per-call budget cap, and a per-run cap on the number of judge calls.

### Layering — prefer the cheaper layer

Behavioral rules fall into layers; suggest the cheapest one that reaches the behavior:

- **Layer 1 — deterministic, free, every PR.** When a rule is code-enforceable, pin it with a real test that mocks the boundary and asserts the side-effect is absent on the violating input (an integration test), or with a **regression corpus** that calls the real gate/checker function on a must-block and a must-allow input. These run in the normal test gate for free.
- **Layer 2 — transcript scenarios, paid agent run.** For LLM-output-only behavior (what the agent *says* or *invokes*), the YAML+matcher scenarios above. These cost a real model call, so the paid full run is typically cadenced (e.g. weekly / first-PR-of-week) while the deterministic layers and the anti-vacuous fixture tests guard every PR.

The reviewer's default order: code-enforceable → Layer 1; LLM-output-only → Layer 2. Suggesting a paid scenario for something a free deterministic test already reaches is a bad suggestion.

### Run-store, baselines, pass@k

For a maturing suite (mention only if the gap warrants it, don't over-prescribe): a single trial against an LLM is noisy. `--trials k --require any` measures *capability* (pass@k); `--require all` is a regression gate where intermittent compliance is itself a failure (pass^k). Runs persist to a ledger with model id, git sha, and per-scenario pass-rate, so a flagged run is reconstructable; a `--baseline` marks the reference and `--gate-regressions` fails on a drop against it. A model matrix (`--models opus,sonnet,haiku`) catches per-model regressions.

## How to phrase the finding

A good suggestion is specific and bounded:

> "`<skill>/SKILL.md` encodes a load-bearing routing rule (X, not Y) with no behavioral coverage. *Suggest* a per-skill eval: a positive matcher that the compliant action appears, paired with a `no_tool_call_matching` for the wrong one (anti-vacuous), plus a fail-fixture so the matcher's teeth are verified. The repo has no eval mechanism yet, so this would be the first — confirm before adopting."

A bad suggestion is "add evals" with no tier, no shape, and no check for an existing mechanism.

## Sources / inspiration

The mechanism documented here is a lifecycle tool's `EvalSpec` harness. Two third-party skills informed the framing and are inspiration only (not dependencies):

- **Anthropic `skill-creator`** (Apache-2.0) — its Eval mode runs a skill *with* and *without* itself in parallel and grades the outputs (with-skill vs baseline A/B), uses a grader sub-agent for non-deterministic assertions and deterministic scripts for verifiable ones, and warns against forcing assertions onto subjective skills. The "grade the delta the skill makes, not just the absolute output" idea is the strongest borrow.
- **obra `superpowers` / `writing-skills`** (MIT) — "no skill without a failing test first": establish the baseline behavior *without* the skill (RED), write the minimal skill (GREEN), then add counters for the rationalizations testing surfaces (REFACTOR). The "prove the skill changes behavior vs baseline" stance complements the anti-vacuous pairing above.
