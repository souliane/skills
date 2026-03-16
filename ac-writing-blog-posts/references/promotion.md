# Promoting Blog Posts

Per-outlet submission guide. Each entry describes the submission method, what
to include, and how the agent can help (or must defer to the user).

> **URLs were verified on 2026-03-16.** Before submitting, confirm that forms
> and email addresses still work — newsletters change processes without notice.
> **Verify before drafting (Non-Negotiable).** Before drafting a pitch for any
> outlet, fetch its submission page and confirm the method is still accurate.
> Do not trust cached info from this file — outlets change without notice.

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
| **Method** | Web form (Google Form behind a landing page) |
| **URL** | <https://pycoders.com/submissions> → "Submit Your Link" button → Google Form at `https://goo.gl/forms/aue40zIzE9jzetUa2` |
| **What to include** | Article URL, short description, contact info |
| **Agent can** | Draft the description; user fills in the Google Form |
| **Tags** | python |
| **Notes** | Not every submission is featured. Accepts projects, conferences, and articles. |

### Django News

| Field | Value |
|-------|-------|
| **Method** | Web form |
| **URL** | <https://django.news/submit_post/> |
| **Form fields** | Your Name ("How you'd like to be credited"), Email Address ("We'll only use this to contact you if needed"), Link URL ("The full URL of the article or resource") |
| **What to include** | Name, email, link URL. Content should relate to Django or Python web development and be recent (within the last few weeks). |
| **Agent can** | Draft the form field values; user submits |
| **Tags** | django, python |

### TLDR AI / TLDR Dev

| Field | Value |
|-------|-------|
| **Method** | Paid advertising only |
| **URL** | <https://advertise.tldr.tech/> |
| **Tags** | ai, software-engineering |
| **Notes** | No free submission form or email pitch option. All newsletter placements (Quick Links, Secondary, Primary) are paid. 12 newsletters, 6M+ subscribers. As of March 2026, the only way to get content into TLDR is through paid sponsorship. |

### The Rundown AI

| Field | Value |
|-------|-------|
| **Method** | Web form — "Recommend a Tool" (embedded Tally form) |
| **URL** | <https://www.rundown.ai/submit> |
| **What to include** | Tool name, description, link, blog post URL |
| **Agent can** | Draft the form fields; user pastes into the Tally form |
| **Tags** | ai |
| **Notes** | Two paths: (1) "Recommend a Tool" form for free submissions, (2) "Newsletter Feature" via separate Typeform for broader visibility. Use path 1 for organic promotion. |

### The Pragmatic Engineer

| Field | Value |
|-------|-------|
| **Method** | Google Form (topic/question suggestion) |
| **URL** | <https://docs.google.com/forms/d/e/1FAIpQLSeBJIIBqe2aHZaZU2AVE_lWNlSO2EDOy4VsDL7yGf7T8tu5VA/viewform> |
| **Form fields** | Topic suggestion (required, long text), Position (IC or Manager), Name (required, not published), Email (optional), Subscriber status (yes/no — paying subscribers prioritized), Additional comments (optional) |
| **Agent can** | Draft the topic suggestion text; user fills in the form |
| **Tags** | software-engineering, ai |
| **Notes** | This is a topic suggestion form, not a link submission. Frame submissions as "here's a topic that might interest your readers" with context, not as self-promotion. Gergely Orosz explicitly does not accept guest posts or sponsored content. Also reachable at <hello@pragmaticengineer.com>. |

### Python Weekly

| Field | Value |
|-------|-------|
| **Method** | Unknown — no public submission form found as of 2026-03-16 |
| **URL** | <https://www.pythonweekly.com/> |
| **Agent can** | Nothing automated |
| **Tags** | python |
| **Notes** | No submission form, email, or contact method found. The newsletter is curated editorially. May need to contact via social media or other channels. |

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
| **What to include** | Title and URL only. Use "Show HN:" prefix only for interactive projects, not blog posts. |
| **Agent can** | Draft the title only. **Never draft HN comments** — HN explicitly prohibits AI-generated comments ("Don't post generated comments or AI-edited comments. HN is for conversation between humans."). The user must write all comments themselves. |
| **Tips** | Factual titles only (mods edit clickbait). Best posting: 8-10am US Eastern, weekdays. Don't ask for upvotes. Be present in comments (written by you, not AI). |
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
| **Tips** | Include the blog link directly in the post body. Write a compelling opening hook (first 2-3 lines visible before "see more"). Use 3-5 hashtags: #Python, #Django, #AI, #MachineLearning, #SoftwareEngineering. Post Tue-Thu mornings. |

### Mastodon

| Field | Value |
|-------|-------|
| **Method** | Direct post on instance |
| **URL** | Instance-specific compose page (e.g., `https://fosstodon.org/publish` for Fosstodon) — check the user's config for their instance URL |
| **Agent can** | Draft the post text (under 500 chars), copy to clipboard, open the compose URL |
| **Tips** | Include 3-5 hashtags. Link directly to the article. Technical, community-focused tone. Fosstodon is a popular instance for open-source/tech content. |
| **Tags** | any |

### Lobste.rs

| Field | Value |
|-------|-------|
| **Method** | Web form (invite-only) |
| **URL** | <https://lobste.rs> |
| **Agent can** | Draft the title; user posts if they have an account |
| **Notes** | Invite-only (invitation tree is public). Self-promotion must be < 25% of stories and comments. New accounts ("green" for 70 days) cannot: submit to previously unseen domains, send invitations, flag, suggest edits, or post in certain tags (meta, rant, show, announce, satire, job, interview, ask, culture, vibecoding, merkle-trees). |
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

  # TLDR AI / TLDR Dev — paid advertising only (no free submission).

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
