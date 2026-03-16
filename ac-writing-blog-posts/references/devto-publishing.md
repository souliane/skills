# Publishing to dev.to from a Private Repo

A reusable pattern for publishing markdown blog posts to dev.to when the
source repo is private. Images are hosted in a separate public repo that
acts as a CDN.

> **Check for newer approaches before adopting.** This pattern was designed
> in March 2026. dev.to may have added an image upload API since then, or
> better GitHub Actions may exist. Search before copying blindly.

## Problem

- Blog repo is private → `raw.githubusercontent.com` URLs return 404.
- dev.to has no public image upload API (as of March 2026).
- Medium deprecated their write API in January 2025 — no new tokens.

## Architecture

Two repos:

```text
<user>/blog (private, source of truth)      <user>/blog-assets (public, images only)
├── posts/                                  ├── assets/      ← static images
│   ├── 20260309-my-article.md              └── generated/   ← rendered diagrams
│   └── assets/
│       └── banner.jpg
├── output/
│   └── devto/             ← CI-generated, platform-ready markdown
├── assets-manifest.json   ← tracks uploaded image hashes
└── .github/workflows/publish-devto.yml
```

- **Source of truth** is `posts/*.md` in the private repo.
- **`<user>/blog-assets`** is a public repo containing only images. No markdown.
- **`output/devto/`** holds CI-generated markdown with rewritten image URLs and dev.to article `id:` fields. Should not be manually edited.
- **`assets-manifest.json`** maps each image to its SHA256 hash and CDN URL. Images are only re-uploaded when their hash changes.

## Image Pipeline

1. CI renders diagrams (e.g., mermaid → PNG via `npx mmdc`).
2. All images (static from `posts/assets/` + generated) are SHA256-hashed.
3. Hashes compared against `assets-manifest.json` — only changed images pushed.
4. Updated manifest committed back to the blog repo.

### Manifest Format

```json
{
  "assets/banner.jpg": {
    "sha256": "c38db5...",
    "url": "https://raw.githubusercontent.com/<user>/blog-assets/main/assets/banner.jpg"
  },
  "generated/20260309-my-article-1.png": {
    "sha256": "dec92f...",
    "url": "https://raw.githubusercontent.com/<user>/blog-assets/main/generated/20260309-my-article-1.png"
  }
}
```

## Workflow

Two jobs in `publish-devto.yml`:

1. **`sync-assets`** — runs on push to `main` (when `posts/` changes).
   Renders diagrams, hashes images, pushes changed ones to `blog-assets`,
   commits manifest.

2. **`publish`** — manual `workflow_dispatch` with `publish: true`.
   Depends on `sync-assets`. Generates `output/devto/` markdown (rewrites
   image URLs from manifest), runs `npx devto-cli push`, writes `id:`
   fields back to both `posts/*.md` and `output/devto/*.md`.

### Triggers

- Push to `main` → only `sync-assets` (image sync).
- Manual dispatch with `publish: true` → both jobs.
- Manual dispatch with `dry_run: true` → preview without publishing.

### Article ID Tracking

`devto-cli` adds an `id` field to frontmatter after first publish. The
workflow writes IDs back to `posts/*.md` (source of truth) and
`output/devto/*.md`. On subsequent runs, only articles with changed
content are updated.

## Secrets

| Secret | Purpose |
|--------|---------|
| `DEVTO_TOKEN` | dev.to API key |
| `BLOG_ASSETS_TOKEN` | Fine-grained GitHub PAT scoped to `<user>/blog-assets` (Contents: read+write) |

## dev.to Frontmatter

```yaml
---
title: "Article Title"
published: false
description: "One-liner for the article"
tags: tag1, tag2              # Max 4 tags on dev.to
cover_image: assets/banner.jpg  # Rewritten to CDN URL by CI
# id: 1234567                 # Added automatically after first publish
---
```

## Adding Another Platform

1. Add a `<platform>/` directory under `output/`.
2. Add a CI step that generates platform-specific markdown.
3. Add a publish step using the platform's CLI/API.
4. Write article IDs back to `posts/*.md` using a platform-specific key
   (e.g., `hashnode_id`).
