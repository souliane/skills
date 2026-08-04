# Scaffold Templates

Templates for scaffolding a new skill repo. Each template is a real file that can be copied directly.

## Template Files

| File | Destination | Notes |
|------|-------------|-------|
| [`templates/SKILL.md.template`](templates/SKILL.md.template) | `<skill>/SKILL.md` | Rename to `SKILL.md`, fill placeholders |
| [`templates/pyproject.toml`](templates/pyproject.toml) | `pyproject.toml` | Replace `<repo-name>` and `<description>` |
| [`templates/pre-commit-config.yaml`](templates/pre-commit-config.yaml) | `.pre-commit-config.yaml` | Pin all `<sha>` to full git SHAs (see below) |
| [`templates/ci.yml`](templates/ci.yml) | `.github/workflows/ci.yml` | Ready to use |
| [`templates/test-matrix.sh`](templates/test-matrix.sh) | `dev/test-matrix.sh` | `chmod +x` after copying |
| [`templates/.markdownlint-cli2.yaml`](templates/.markdownlint-cli2.yaml) | `.markdownlint-cli2.yaml` | Ready to use |
| [`templates/.editorconfig`](templates/.editorconfig) | `.editorconfig` | Ready to use |
| [`templates/README.md.template`](templates/README.md.template) | `README.md` | Rename, fill placeholders |

## SKILL.md Frontmatter

See [`ac-reviewing-codebase/references/skill-authoring-best-practices.md`](../../ac-reviewing-codebase/references/skill-authoring-best-practices.md) § Frontmatter Spec for the full field reference.

## Pinning Strategy

All external repos in `.pre-commit-config.yaml` must be pinned to a full git SHA with the version in a comment:

```bash
git ls-remote https://github.com/<org>/<repo>.git refs/tags/<version> | cut -f1
```

## README Auto-Generation

The `update-readme-skills` hook auto-generates the skills table between `<!-- BEGIN SKILLS -->` and `<!-- END SKILLS -->` from SKILL.md frontmatter. `skill-repo-boilerplate` owns the script and publishes it in its `.pre-commit-hooks.yaml`, so repos pin it by SHA rather than keeping a copy:

```yaml
  - repo: https://github.com/souliane/skill-repo-boilerplate
    rev: <sha>  # <date>
    hooks:
      - id: update-readme-skills
      - id: bump-pyproject-deps-from-lock-file
        stages: [manual]
```
