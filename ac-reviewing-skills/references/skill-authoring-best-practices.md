# Skill Authoring Best Practices

Combines Anthropic's [official best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) with [Cherny's recommendations](https://paddo.dev/blog/how-boris-uses-claude-code/) from building Claude Code's skill system.

## Frontmatter Spec

The `name` and `description` fields are required by the [Agent Skills open standard](https://agentskills.io); additional fields are optional extensions.

| Field | Required | Constraints |
|-------|----------|-------------|
| `name` | Yes | Max 64 chars, lowercase + numbers + hyphens only. No "anthropic" or "claude". Use gerund form for action skills (`adopting-ruff`), plain noun for domain skills (`django`). |
| `description` | Yes | Max 1024 chars, third person ("Scaffolds a new skill repo..."). Must include **what** the skill does and **when** to use it. End with trigger phrases: `Use when user says "..."`. |
| `compatibility` | No | Platforms and requirements (e.g., `macOS/Linux, Python 3.12+, uv, git`). |
| `metadata.version` | No | SemVer string (e.g., `0.0.1`). |
| `metadata.subagent_safe` | No | `true` only if the skill is pure methodology with no shell/MCP/env deps. |

## Body Size & Progressive Disclosure

- Keep `SKILL.md` body under ~500 lines. Only include context the model does not already have.
- Split detailed content into reference files one level deep (`references/`, `scripts/`). Avoid deeply nested chains — if reading the skill requires A -> B -> C to reach actual content, flatten it.
- If contexts are mutually exclusive or rarely used together, keep them in separate files to reduce token usage.

## Degrees of Freedom

Match the specificity of instructions to the fragility of the operation:

- **High freedom** (judgment calls): "Choose an appropriate data structure."
- **Medium freedom** (bounded choices): "Use either `select_related` or `prefetch_related` depending on the relationship type."
- **Low freedom** (fragile/exact sequences): "Run `makemigrations`, then `migrate`, then verify with `showmigrations`. Do not skip steps."

Over-constraining wastes tokens and limits the model. Under-constraining causes errors on fragile operations.

## Scripts Over Prose

When a workflow is deterministic and multi-step, implement it as a callable script rather than prose instructions. Scripts are faster (no LLM reasoning overhead), cheaper (no tokens), and more reliable (no model deviation). The model just needs to know the script exists and when to call it.

## Evaluation-Driven Development

1. Run the agent on representative tasks and observe where it struggles.
2. Build skills incrementally to address specific shortcomings.
3. Monitor how the agent uses skills in real scenarios — watch for unexpected trajectories.
4. After each correction, update the skill so the mistake cannot recur ("every correction is a skill bug").

## Consistent Terminology

Use one term per concept throughout the skill. If you call it "worktree" in one section, don't call it "workspace" in another.

## Self-Improvement Loop

Skills improve through use. After each session, ask: "Did the agent make a mistake that a skill update would prevent?" If yes, update the skill — not just the code. This compounds: after many sessions, the skill encodes hundreds of hard-won fixes.

## Security

- Install skills only from trusted sources. For less-trusted sources, audit all bundled files before use.
- Make clear whether the agent should run scripts directly or read them as reference.
- Never include secrets in skill files.

## References

- [Agent Skills Open Standard](https://agentskills.io)
- [Anthropic Skill Authoring Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Agent Skills Overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Equipping Agents for the Real World](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills) — Anthropic engineering blog
- [How Boris Cherny Uses Claude Code](https://paddo.dev/blog/how-boris-uses-claude-code/)
- [10 Tips from the Claude Code Team](https://paddo.dev/blog/claude-code-team-tips/)
