---
name: ac-django
description: Definitive Django bible covering Django 6.x, 5.2 LTS, and optional DRF. Fat Models doctrine with migrations, transactions, security, testing, and tooling. Use when writing Django models, views, forms, serializers, migrations, tests, or reviewing Django code. Do NOT use for project-specific Django patterns (load the project overlay skill instead).
compatibility: python3. Knowledge-only skill with no external tool requirements beyond a Django codebase.
metadata:
  version: 0.0.1
  subagent_safe: true
---

# Django Bible (Django 6.x baseline · Django 5.2 deltas · optional DRF)

**Baseline:** Django **6.x** + Python **3.12+** · **Compat:** Django **5.2 LTS** · **API:** DRF _when you choose it_

## Canonical Sources

- Django docs index (6.0): <https://docs.djangoproject.com/en/6.0/>
- Django 6.0 release notes: <https://docs.djangoproject.com/en/6.0/releases/6.0/>
- Adam Johnson — `django-upgrade`: <https://adamj.eu/tech/2021/09/16/introducing-django-upgrade/>
- Adam Johnson — `django-linear-migrations`: <https://adamj.eu/tech/2020/12/10/introducing-django-linear-migrations/>
- Haki Benita — Django Foreign Keys: <https://hakibenita.com/django-foreign-keys>
- James Bennett — Fat Model / "no service layer": <https://www.b-list.org/weblog/2020/mar/16/no-service/>
- DRF API guide: <https://www.django-rest-framework.org/api-guide/>
- Factory Boy best practices: <https://github.com/camilamaia/factory-boy-best-practices>

## Reference Files (load as needed)

| File | Covers | When to load |
|---|---|---|
| [`references/models-and-schema.md`](references/models-and-schema.md) | Models, fields, constraints, QuerySets, managers, ORM performance | Model changes, query optimization, schema design |
| [`references/transactions-and-migrations.md`](references/transactions-and-migrations.md) | Transactions, locking, idempotency, migration safety, FK index ops | Multi-step writes, migrations, schema changes |
| [`references/views-and-templates.md`](references/views-and-templates.md) | Views, forms, templates, partials, HTMX, file uploads, i18n, middleware, management commands, connection pooling, Django 6 snippets | View/template work, form handling, HTMX, uploads |
| [`references/background-and-infra.md`](references/background-and-infra.md) | Background tasks, security, settings, observability, caching, async | Tasks, deployment, logging, caching, async views |
| [`references/admin-and-drf.md`](references/admin-and-drf.md) | Django Admin, DRF serializers, viewsets, permissions, pagination, versioning | Admin customization, API endpoints |
| [`references/testing-and-tooling.md`](references/testing-and-tooling.md) | Testing bible, Factory Boy, tooling, DX enforcement | Writing tests, CI setup, linting |
| [`references/antipatterns.md`](references/antipatterns.md) | django-antipatterns.com tips, patterns | Code review, avoiding common mistakes |
| [`references/troubleshooting.md`](references/troubleshooting.md) | Common Django errors and fixes | Diagnosing migration, N+1, on_commit issues |

## Dependencies

Standalone. No dependencies on other skills.

When used alongside lifecycle skills, provides Django best practices context for Django projects using the worktree workflow.

## Overrides When Loaded Alongside ac-python

When both ac-django and ac-python are loaded, the following Django-specific rules take precedence over the generic Python guidelines:

| Topic | ac-python (generic) | ac-django (wins) |
|---|---|---|
| Test base class | Plain pytest classes (`class TestFoo:`) | `django.test.TestCase` (or `TransactionTestCase` when needed) |
| Parametrization | `pytest.mark.parametrize` | `unittest_parametrize` |
| Test data factories | `build_...()` plain functions | Factory Boy with `DjangoModelFactory`, traits, `build()` / `create()` |
| Shared setup | pytest fixtures | `setUpTestData()` (class-level, faster for DB-backed tests) |
| Time mocking | any (`freezegun`, `time_machine`, etc.) | `time_machine` (house default) |

All other ac-python guidelines (style, typing, OOP, imports, ruff config) apply unchanged in Django projects.

## Trigger QA (Release Gate)

Before shipping skill changes, validate activation behavior with sample prompts:

- Should trigger:
  - "Add a Django model field and migration."
  - "Review this DRF serializer and queryset for performance issues."
  - "Fix this Django transaction/on_commit bug."
- Should NOT trigger:
  - "Set up git worktrees for a ticket."
  - "Implement project delivery workflow and create an MR."
  - "Create a Notion research summary."

If behavior under-triggers or over-triggers, tighten `description` cues before release.

## Example: Adding a new model field

User says: "Add a postal_code field to the Address model"

1. Load [`references/models-and-schema.md`](references/models-and-schema.md) for field types and constraints
2. Load [`references/transactions-and-migrations.md`](references/transactions-and-migrations.md) for migration safety
3. Add field to model with appropriate validators, constraints, and `db_index` if queried
4. Create migration, verify with `makemigrations --check`
5. Add factory trait for the new field in tests

## Prime Directives

### Django docs first (always)

- Use Django the way Django documents it.
- Prefer built-ins over dependencies unless Django has a clear documented gap (notably Django 5.2 lacking native Tasks/CSP/Partials).

### Fat Model wins (no domain service layer)

- No `services.py` for domain logic.
- Business rules and invariants must be discoverable on:
  - model instance methods (single-object behavior)
  - QuerySet/Manager methods (collection behavior)

### Locality of behavior (anti-octopus)

- Co-locate behavior with:
  - the data (models/querysets)
  - the UI (partials inside the template that uses them)

### Coordination vs business logic

Allowed at boundaries (views/forms/serializers):

- sequencing calls
- selecting aggregate root objects
- transaction bracketing when spanning multiple domain calls

Not allowed at boundaries:

- invariants
- workflow rules
- state transitions that define correctness

## Version Matrix (Django 6 vs 5.2)

| Capability | Django 6.x | Django 5.2 LTS delta |
|---|---|---|
| Template partials | Native `{% partialdef %}` | Use `django-template-partials` (remove on upgrade) |
| Background tasks | Native `django.tasks` (`@task`, `.enqueue()`) | Use Celery/Huey/RQ/etc. |
| CSP | Native CSP middleware + `SECURE_CSP` | Use `django-csp` |

Upgrade posture:

- Run `django-upgrade` before manual refactors.
- Leave explicit upgrade TODOs:
  - `# TODO(Django6): switch @shared_task -> @task and .delay() -> .enqueue()`
  - `# TODO(Django6): remove {% load partials %} (partials become native)`
  - `# TODO(Django6): replace django-csp with built-in CSP middleware`

## Project Layout & Boundaries

### Domain-first apps

- Split apps by domain capability, not by technical layer.
- Each app should be readable end-to-end.

### Public vs internal vs admin

- Separate public API/HTML surfaces from internal/admin surfaces.
- Prefer separate modules over one giant `views.py`.

### "core/" discipline

- **Allowed:** request-id middleware, logging helpers, settings checks, small shared base mixins
- **Forbidden:** hiding domain behavior "because it's shared"

### Naming

- Use business language.
- Prefer verb methods: `approve()`, `reject()`, `settle()`, `cancel()`.

## Team Style Conventions (ask once, remember)

Some style choices are equally valid — the "right" answer depends on the team. When you encounter one of these for the first time in a project, **ask the user** for their team's preference and save it to the project's `MEMORY.md` (auto-memory) so it persists across sessions.

| Topic | Option A | Option B | What to ask |
|---|---|---|---|
| Attribute/relation checks | **LBYL:** `hasattr()`, `isinstance()`, `getattr(obj, attr, default)` | **EAFP:** `try/except AttributeError` | "Does your team prefer LBYL (hasattr/getattr) or EAFP (try/except) for optional attribute and reverse-relation checks?" |
| Queryset existence checks | `if qs.exists():` then `qs.first()` | `obj = qs.first(); if obj:` | "Single query (`first()` + None check) or explicit `exists()` + `first()`?" |
| Null handling in serializers | Explicit `allow_null=True` on every nullable field | Rely on model field `null=True` inference | "Explicit `allow_null` on serializer fields, or infer from model?" |

**Rules:**

- Only ask on the **first occurrence** in a project — never re-ask if already saved.
- If a project overlay skill already documents the preference, treat that as the answer — don't ask again.
- Save the answer as: `## Django Team Convention: <topic>` in the project's `MEMORY.md`.

## Fat Model Doctrine (where logic lives)

### Placement table (strict)

| Concern | Home | Notes |
|---|---|---|
| invariants, transitions, domain calculations | model methods | "tell, don't ask" |
| collection logic | QuerySet methods | chainable |
| graph loading | QuerySet methods | `for_api()`, `for_list()`, `with_*()` |
| request validation | forms / DRF serializers | boundary validation |
| authorization | views / DRF permissions | check early |
| rendering | templates / serializers | no DB access |

### Encapsulate mutation

Expose domain methods that: validate state → perform mutation → persist changes → schedule side effects safely (after commit).

### Cross-aggregate operations

- Choose an aggregate root and implement a coordinating method there (preferred), or
- Coordinate in the boundary using a single `transaction.atomic()`
- Do **not** invent a separate "domain service layer".

### Narrow exceptions (allowed files)

- `selectors.py`: complex cross-model **read** operations (reporting/dashboards) returning typed DTOs
- `services.py`: **external API orchestration only** (Stripe, AWS, etc.) with **no DB business logic**

## Review Checklists

### Domain rules / Fat Model

- [ ] business rules live on models/querysets
- [ ] boundaries only orchestrate

### ORM performance

- [ ] no N+1
- [ ] queryset shaped for serializer/template needs
- [ ] constraints/indexes reviewed

### Transactions and side effects

- [ ] multi-step write flows wrapped in `atomic()`
- [ ] side effects scheduled via `on_commit`

### Migrations

- [ ] linear migrations enforced
- [ ] `makemigrations --check` passes
- [ ] migration safe/reviewable

### Tasks

- [ ] idempotent
- [ ] enqueued after commit

### Security

- [ ] authz checked early
- [ ] CSRF preserved
- [ ] CSP configured correctly

### Testing

- [ ] traits used for nullable/optional data
- [ ] tests explicit about preconditions
