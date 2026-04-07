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
| `metadata.last_research_date` | No | ISO date (e.g., `"2026-03-14"`). For research-intensive skills where external tools, APIs, or installation procedures may change. Reviewers should flag skills whose research date is >6 months old. |
| `when_to_use` | No | Free-text guidance shown alongside description in skill listing. The model reads this to decide when to invoke the skill. Some platforms use this as a native discovery field. |
| `allowed-tools` | No | Tools the skill grants access to. Supports `"*"` wildcard and brace expansion (`mcp__{a,b}__*`). |
| `model` | No | Override model for this skill. `"inherit"` = use parent model. |
| `effort` | No | Override reasoning effort level for this skill. |
| `context` | No | `"fork"` runs the skill as an isolated sub-agent. |
| `hooks` | No | Inline hooks — skill registers its own hooks for agent lifecycle events (e.g., pre/post tool use, file changed). Event names are platform-specific. |
| `paths` | No | Glob patterns for conditional activation. Skill stays dormant until a file operation touches a matching path. |
| `disable-model-invocation` | No | If `true`, the skill is excluded from the model's auto-discovery listing. Only invocable manually via `/skill-name`. |
| `argument-hint` | No | Hint shown in typeahead for the skill's argument. |
| `arguments` | No | Named arguments the skill accepts (e.g., `"url branch"`). |

## Body Size & Progressive Disclosure

- Keep `SKILL.md` body under ~500 lines and under ~2,000 tokens. Only include context the model does not already have. Over that threshold, split into core SKILL.md + `references/` files.
- Split detailed content into reference files one level deep (`references/`, `scripts/`). Avoid deeply nested chains — if reading the skill requires A -> B -> C to reach actual content, flatten it.
- If contexts are mutually exclusive or rarely used together, keep them in separate files to reduce token usage.
- **Token estimation:** `text.length / 4` gives a rough token count. A 8,000-character SKILL.md is ~2,000 tokens.

## Compaction Survival

Agent platforms compress conversation context as it grows. Mechanisms vary (lightweight cleanup of old tool results, full summarization, sliding window), but the risk is the same: skill content loaded early in the session may be lost or summarized.

- **Front-load non-negotiables.** The first ~100 lines of every SKILL.md should contain: all non-negotiable rules, the command reference, and the workflow summary. Put examples, verbose explanations, and edge cases after line 100. Summaries are more likely to retain content the model engaged with early.
- **Include a reload directive.** At the end of the skill body, add: "If this skill was truncated during context compression, re-read it from disk." This gives the agent a recovery path.
- **Reference files survive independently.** Content in `references/*.md` that the agent reads on demand can be re-read after compression. Content embedded inline in SKILL.md may not survive.

## Reference Content: Lazy Loading vs Embedding

Some agent platforms can selectively clear old file-read results from context, but content embedded in the skill body stays loaded until full compression.

- **For content >1,500 tokens, put it in a `references/*.md` file** and instruct the agent to read it on demand. This makes the content eligible for selective cleanup when no longer needed.
- **Keep only core instructions in SKILL.md** — non-negotiables, workflow steps, command reference. Move examples, code patterns, and detailed explanations to reference files.
- **Each reference file should start with a one-line purpose header** so the agent knows when to re-read it after compression (e.g., "# Model Patterns — read when working on models or migrations").

## Deterministic Ordering & Cache Stability

Agent platforms cache the conversation prefix server-side for performance. If content appears in a different order between interactions, the cache is invalidated — costing latency and money on every call.

- **Load reference files in alphabetical order** (by filename) unless a specific order is required by the workflow.
- **Static content before dynamic content.** When a skill reads both stable references (guidelines, architecture docs) and dynamic data (diffs, test output, API responses), read the stable references first. This maximizes the reusable cache prefix.
- **Avoid reordering loaded content mid-session.** If you read `guidelines.md` then `patterns.md` at the start, maintain that order throughout.

## Memory Conventions

When a skill instructs the agent to save information for future sessions, use a consistent schema across all skills. This enables cross-skill memory access — a convention saved by one skill can be found and used by another.

**Standard memory types** (match the agent platform's built-in types when available):

| Type | When to use | Body structure |
|------|-------------|---------------|
| `user` | User's role, preferences, expertise | Free-form profile notes |
| `feedback` | How-to-work guidance from the user | Rule, then `**Why:**` and `**How to apply:**` |
| `project` | Ongoing work, goals, deadlines | Fact/decision, then `**Why:**` and `**How to apply:**` |
| `reference` | Pointers to external resources | URL/location + when to consult it |

**Conventions:**

- Use a short, specific `description` on each memory entry — it is used for relevance matching when the platform selects which memories to load.
- Do not save information that can be derived from the code, git history, or existing documentation.
- When updating a convention previously saved by another skill, update in place rather than creating a duplicate.

Skills should reference this schema rather than defining their own memory format. Instead of "save to MEMORY.md with `## Django Team Convention: <topic>`", say "save as a `project` memory with a descriptive title."

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
