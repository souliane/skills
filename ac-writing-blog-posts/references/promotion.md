# Promoting Blog Posts

Per-outlet submission guide. Each entry describes the submission method, what
to include, and how the agent can help (or must defer to the user).

> **URLs were verified in March 2026.** Before submitting, confirm that forms
> and email addresses still work — newsletters change processes without notice.

## Config File

The agent reads `~/.ac-writing-blog-posts.yml` to know which outlets the user
cares about. If the file doesn't exist, the agent suggests common outlets and
asks the user to create one.

```yaml
# ~/.ac-writing-blog-posts.yml
outlets:
  - name: "PyCoder's Weekly"
    type: form
    url: "https://pycoders.com/submissions"
    tags: [python]

  - name: "Django News"
    type: form
    url: "https://django.news/submit_post/"
    tags: [django, python]
```

See the "Config Format" section below for the full schema.

## Newsletters & Aggregators

### PyCoder's Weekly

| Field | Value |
|-------|-------|
| **Method** | Web form (Google Form) |
| **URL** | <https://pycoders.com/submissions> |
| **What to include** | Article URL, short description, contact info |
| **Agent can** | Open the URL for the user, draft the description |
| **Tags** | python |

### Django News

| Field | Value |
|-------|-------|
| **Method** | Web form |
| **URL** | <https://django.news/submit_post/> |
| **What to include** | Name, email, link URL |
| **Agent can** | Open the URL, draft the submission text |
| **Tags** | django, python |

### TLDR AI

| Field | Value |
|-------|-------|
| **Method** | Email pitch to curators |
| **Email** | <dan@tldr.tech> |
| **What to include** | Article link, 2-3 sentence pitch explaining why it's relevant to AI practitioners |
| **Agent can** | Draft the email body; user sends manually |
| **Tags** | ai |
| **Notes** | No public submission form. Curators select content independently. Paid sponsorship available at <https://advertise.tldr.tech/> |

### TLDR Dev (Software Engineering)

| Field | Value |
|-------|-------|
| **Method** | Email pitch to curators |
| **Email** | <dan@tldr.tech> |
| **What to include** | Article link, 2-3 sentence pitch focused on dev tooling / workflow |
| **Agent can** | Draft the email body; user sends manually |
| **Tags** | software-engineering |
| **Notes** | Same process as TLDR AI. Full list of TLDR newsletters: <https://tldr.tech/newsletters> |

### The Rundown AI

| Field | Value |
|-------|-------|
| **Method** | Web form (embedded Tally form) |
| **URL** | <https://www.rundown.ai/submit> |
| **What to include** | Tool/article details |
| **Agent can** | Open the URL, draft the description |
| **Tags** | ai |

### Awesome Python (GitHub)

| Field | Value |
|-------|-------|
| **Method** | GitHub Pull Request |
| **Repo** | <https://github.com/vinta/awesome-python> |
| **What to include** | `[project-name](link) - Description.` in the appropriate category |
| **Agent can** | Draft the PR description; user opens the PR |
| **Contributing guide** | <https://github.com/vinta/awesome-python/blob/master/CONTRIBUTING.md> |
| **Tags** | python, open-source |
| **Notes** | PRs need ~20 thumbs-up reactions to be merged. Project should be established (not brand-new with zero stars). |

## Social Media Platforms

### Hacker News

| Field | Value |
|-------|-------|
| **Method** | Web form (login required) |
| **URL** | <https://news.ycombinator.com/submit> |
| **What to include** | Title and URL. Use "Show HN:" prefix only for interactive projects, not blog posts. |
| **Agent can** | Draft the title; user submits |
| **Tips** | Factual titles only (mods edit clickbait). Best posting: 8-10am US Eastern, weekdays. Don't ask for upvotes. Be present in comments. |
| **Guidelines** | <https://news.ycombinator.com/newsguidelines.html> |

### Reddit

No single submission process — post directly to relevant subreddits.

| Subreddit | Focus | Self-promo rules |
|-----------|-------|-----------------|
| **r/Python** | Libraries, tutorials | Use weekly "What did you do" thread or follow 9:1 rule |
| **r/django** | Django-specific | Welcoming of tutorials and tools |
| **r/MachineLearning** | Academic/research | Use `[P]` tag for projects, `[D]` for discussion |
| **r/artificial** | General AI news | Lower bar than r/MachineLearning |
| **r/LocalLLaMA** | Local AI/LLM tooling | Active community for self-hosted AI |
| **r/programming** | General programming | Must be direct links, no memes |
| **r/SideProject** | Launching tools/projects | Good for tool announcements |

**Agent can:** Draft post titles and bodies per subreddit; user posts manually.

### LinkedIn

| Field | Value |
|-------|-------|
| **Method** | Direct post on profile |
| **Agent can** | Draft the post text with hashtags |
| **Tips** | Put the blog link in the **first comment** (not the post body) — LinkedIn deprioritizes external links. Write a compelling opening hook (first 2-3 lines visible before "see more"). Use 3-5 hashtags: #Python, #Django, #AI, #MachineLearning, #SoftwareEngineering. Post Tue-Thu mornings. |

### Lobste.rs

| Field | Value |
|-------|-------|
| **Method** | Web form (invite-only) |
| **URL** | <https://lobste.rs> |
| **Agent can** | Draft the submission; user posts if they have an account |
| **Notes** | Invite-only. Self-promotion must be < 25% of submissions. New accounts restricted for 70 days. High-quality, small community. |
| **About** | <https://lobste.rs/about> |

## Cross-Posting Platforms

### dev.to

| Field | Value |
|-------|-------|
| **Method 1** | RSS import (recommended): <https://dev.to/settings/extensions> — enter RSS feed URL, check "Mark RSS source as canonical URL" |
| **Method 2** | Manual: <https://dev.to/new> — paste content, set canonical URL in settings |
| **Agent can** | Generate dev.to-ready markdown with frontmatter (see `devto-publishing.md`) |
| **Tips** | Always set canonical URL. Max 4 tags. |

### Hashnode

| Field | Value |
|-------|-------|
| **Method 1** | RSS import: Blog Dashboard > Import > RSS Importer |
| **Method 2** | Manual: create story, set canonical URL under "Is this a republished article?" |
| **Agent can** | Draft the content; user cross-posts manually |
| **Tips** | Always set canonical URL. Free subdomain or custom domain. |

## Config Format

```yaml
# ~/.ac-writing-blog-posts.yml
#
# Outlets the agent should suggest when promoting a blog post.
# Remove or comment out entries you don't use.
# The agent uses 'tags' to filter outlets by article topic.

outlets:
  - name: "PyCoder's Weekly"
    type: form            # form | email | github-pr | manual
    url: "https://pycoders.com/submissions"
    tags: [python]

  - name: "Django News"
    type: form
    url: "https://django.news/submit_post/"
    tags: [django, python]

  - name: "TLDR AI"
    type: email
    email: "dan@tldr.tech"
    tags: [ai]

  - name: "TLDR Dev"
    type: email
    email: "dan@tldr.tech"
    tags: [software-engineering]

  - name: "The Rundown AI"
    type: form
    url: "https://www.rundown.ai/submit"
    tags: [ai]

  - name: "Awesome Python"
    type: github-pr
    url: "https://github.com/vinta/awesome-python"
    tags: [python, open-source]

  - name: "Hacker News"
    type: form
    url: "https://news.ycombinator.com/submit"
    tags: [any]

  - name: "Reddit"
    type: manual
    subreddits:
      - name: "r/Python"
        tags: [python]
      - name: "r/django"
        tags: [django]
      - name: "r/MachineLearning"
        tags: [ai]
      - name: "r/LocalLLaMA"
        tags: [ai, local-llm]
      - name: "r/programming"
        tags: [any]
    tags: [any]

  - name: "LinkedIn"
    type: manual
    tags: [any]

  - name: "dev.to"
    type: manual
    url: "https://dev.to/new"
    tags: [any]

  - name: "Lobste.rs"
    type: manual
    url: "https://lobste.rs"
    tags: [any]

# Credentials stored in `pass` (optional).
# The agent will read these with `pass show <entry>` when needed.
credentials:
  devto: "blog/devto-api-key"
  hackernews: "blog/hackernews"
  # reddit: "blog/reddit"
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable outlet name |
| `type` | Yes | `form` (web form), `email` (pitch email), `github-pr` (PR to a repo), `manual` (user handles it) |
| `url` | No | Submission URL (for `form` and `github-pr` types) |
| `email` | No | Contact email (for `email` type) |
| `tags` | Yes | Topic tags — agent filters outlets by matching article tags. Use `any` for always-relevant outlets. |
| `subreddits` | No | Reddit-specific: list of subreddits with per-sub tags |
| `credentials` | No | Top-level map of `pass` entries for API keys and logins |
