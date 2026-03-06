---
name: ac-writing-blog-posts
description: Write blog articles and generate social media posts to promote them. Use when user says "blog", "article", "write post", "blog post", or wants to create/update a blog article or generate social media content.
compatibility: Any agent that can read/write files.
metadata:
  version: 0.0.1
  subagent_safe: true
---

# Blog Post

Write blog articles and generate promotional social media content.

## Dependencies

Standalone. No dependencies on other skills.

## Rules

### Never Invent Biographical or Personal Details (Non-Negotiable)

**Never state anything in the author's name that isn't explicitly provided by the author or sourced from verifiable project files (README, SKILL.md, commit history, etc.).** This includes:

- Life events, career history, motivations, or emotional experiences
- Time estimates ("I spent 15 minutes...", "after months of...")
- Habits or workflow descriptions ("I always...", "every morning I...")
- Opinions or preferences not explicitly stated

When biographical context would improve the article, **ask the user** with a specific question. Example: "The intro would benefit from context about how you started using this tool — can you share a sentence or two?"

Save user-provided biographical details to the agent's memory file for reuse in future articles.

### Humble, Non-Pretentious Tone (Non-Negotiable)

- Never position the author as smarter or more insightful than others.
- Present learnings as personal takeaways, not corrections of others' work.
- "I found that..." over "The right way to..."
- "This works well for my workflow" over "This is the best approach"
- Acknowledge limitations and experimental status honestly.
- Avoid superlatives and marketing language.

### Source-Grounded Claims Only (Non-Negotiable)

Every technical claim in the article must be verifiable against the actual codebase, documentation, or skill files. Before writing about a tool or project:

1. Read the source files (README, SKILL.md, scripts, config).
2. Base descriptions on what the code actually does, not what it might do.
3. When unsure about a feature's status or behavior, ask the user.

### Draft Status

Blog posts should include `draft: true` in their frontmatter until the user explicitly marks them as published. Published posts (`draft: false`) must not be modified — they are snapshots in time.

## Workflow

### 1. Gather Context

Before writing, collect:

- **Topic and scope** — what is the article about? Ask if unclear.
- **Target audience** — developers? managers? specific community?
- **Author bio context** — check the agent's memory for stored biographical details. If none found, ask: "How should I introduce you? (role, company, relevant background)"
- **Key points** — what must the article cover? Let the user list them or extract from source material.
- **Existing content** — are there README files, SKILL.md files, or documentation to base the article on?

Save gathered preferences to the agent's memory file:

```
## Blog Post Preferences
- Author intro: [what the user provided]
- Default tone: [any specific preferences]
- Preferred structure: [if stated]
```

### 2. Structure the Article

Standard blog post structure (adapt as needed):

1. **Title** — concise, specific, no clickbait
2. **Opening** — 2-3 sentences establishing context and what the reader will learn
3. **Problem/motivation** — why this exists (grounded in real experience, not invented)
4. **Solution/content** — the meat of the article
5. **Examples** — concrete, runnable where possible
6. **Limitations/status** — honest about maturity and scope
7. **Links** — repo, license, related resources

### 3. Write the Draft

- Use the frontmatter format:

  ```yaml
  ---
  title: "Article Title"
  date: YYYY-MM-DD
  draft: true
  ---
  ```

- Write in first person when the author is sharing personal experience.
- Use code blocks with language annotations.
- Keep paragraphs short (3-5 sentences max).
- Use headings to create scannable structure.
- Include links to source repos, documentation, and referenced projects.

### 4. Review Against Source Material

After writing the draft, verify:

- [ ] Every technical claim matches the actual codebase
- [ ] No biographical details were invented
- [ ] Tone is humble and non-pretentious
- [ ] All links are valid
- [ ] Code examples are correct and runnable
- [ ] Limitations are honestly stated

### 5. Iterate with the User

Present the draft and ask for feedback. Common revision areas:

- Biographical accuracy
- Technical depth (too shallow / too detailed)
- Tone adjustments
- Missing topics or over-emphasis

## Social Media Generation

When asked to generate social media content (or when the user passes a platform name), generate a short promotional message for the specified platform. Output to console — do not save to a file unless asked.

### Supported Platforms

| Platform | Style | Length | Notes |
|----------|-------|--------|-------|
| **linkedin** | Professional, descriptive | 200-300 words | Include 3-5 hashtags. Mention role/company if known. |
| **mastodon** | Technical, community-focused | Under 500 chars | Include 3-5 hashtags. Link to repo/article. |
| **hackernews** | Minimal, factual | Title + 2-3 sentence comment | No hashtags. Focus on technical merit. Avoid self-promotion tone — HN readers detect it instantly. |
| **reddit** | Conversational, community-aware | Title + short body | Suggest appropriate subreddits (r/programming, r/python, r/django, etc.). Be genuine, not salesy. |

### Generation Process

1. Read the blog post being promoted.
2. Extract the 2-3 most compelling points for the target audience.
3. Generate the message following platform conventions.
4. Present to the user for review — never post automatically.

### Asking User for Social Media Preferences

On first social media generation, ask:

- "Which platforms do you typically post to?"
- "Do you have specific handles or hashtags you always include?"
- "Any platforms where you prefer a specific tone?"

Save answers to the agent's memory file for future use.

## File Conventions

- Blog posts go in the project's `blog/` directory.
- Filename format: `YYYYMMDD-slug.md` (e.g., `20260310-introducing-teatree.md`).
- Images go in `blog/assets/` or alongside the post.

## References

None.
