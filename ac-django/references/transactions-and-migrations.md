# Transactions, Locking, and Migrations (Sections 6–7)

> Load when working on multi-step writes, migrations, or schema changes.

---

## 6. Transactions, locking, and idempotency

### 6.1 Transaction boundaries

- Put multi-step domain operations inside `transaction.atomic()`.
- Prefer putting the `atomic()` inside the aggregate root method.

### 6.2 Row-level locking

Use `select_for_update()` when:

- concurrent writers can violate invariants
- two transitions must not race

Keep lock scope minimal and fast.

Relationship nuance (Postgres especially):

- `select_for_update()` combined with `select_related()` can lock **more rows than you intended** (joined tables).
  - If you only need to lock the base table's rows, specify the lock target explicitly: `select_for_update(of=("self",))`.
- Prefer permissive locks when possible: if you're not changing any key/unique values, `select_for_update(no_key=True)` can reduce contention by allowing inserts that reference the locked row.
  - Treat this as a conscious choice: verify it matches your invariant and your database supports it.

### 6.3 `on_commit` for side effects

When writes trigger tasks/emails/webhooks:

- schedule via `transaction.on_commit(...)`
- tasks should accept identifiers (IDs), not ORM objects

### 6.4 Idempotency and retries

- task handlers must be idempotent or safely retryable
- domain methods should tolerate duplicates where feasible (e.g., `mark_paid()` becomes a no-op if already paid)

### 6.5 Example: atomic model method with locking and on_commit

```py
from django.db import models, transaction

class Order(models.Model):
    status = models.CharField(max_length=20, default="pending")
    paid_at = models.DateTimeField(null=True, blank=True)

    def mark_paid(self):
        """Idempotent: no-op if already paid."""
        with transaction.atomic():
            order = (
                Order.objects
                .select_for_update(of=("self",))
                .get(pk=self.pk)
            )
            if order.status == "paid":
                return  # idempotent
            order.status = "paid"
            order.paid_at = timezone.now()
            order.save(update_fields=["status", "paid_at"])

            transaction.on_commit(lambda: send_receipt.enqueue(order.pk))
```

---

## 7. Migrations: safety + zero-drama ops

### 7.1 Non-negotiable CI checks

- Enforce linear migrations: `django-linear-migrations`
- Pending migrations check:

```bash
python manage.py makemigrations --check
```

### 7.2 Migration merge conflicts (Non-Negotiable)

When CI fails with "Conflicting migrations detected; multiple leaf nodes in the migration graph", the fix (`makemigrations --merge`) must go through its **own dedicated MR/ticket** — never piggybacked onto an unrelated feature or fix branch. Merge migrations affect the entire migration graph and must be reviewed independently.

### 7.3 Rebasing a migration (renumbering after master moves ahead)

When master gains a new migration with the **same number** as one on your branch (e.g., both have `0297_…`), the fix is to **renumber your migration** — not `git rebase` the branch. "Rebase the migration" is Django terminology, not git terminology.

If the project uses [`django-linear-migrations`](https://adamj.eu/tech/2020/12/10/introducing-django-linear-migrations/), run `python manage.py rebase_migration <app_label> <migration_name>` — it handles renumbering and dependency updates automatically.

Manual steps (when `django-linear-migrations` is not installed):

1. `git fetch origin master` (get the latest migration list).
2. Identify the conflict: `ls <app>/migrations/<number>*` shows two files with the same prefix.
3. Rename your file to the next available number (e.g., `0297_…` → `0298_…`).
4. Update the `dependencies` list inside the renamed migration to point to master's new migration (the one that now precedes yours).
5. Check if any **other** migration on the branch depends on the old name (`grep -r "old_name"`) and update those too.
6. Commit the rename + dependency update as a standalone commit.

**Do NOT `git rebase origin/master`** unless the user explicitly asks for a branch rebase. Rebasing rewrites all commit SHAs and is a much heavier operation.

### 7.4 Migration hygiene

- keep migrations small
- review generated SQL when impact is non-trivial
- separate schema vs data migrations when it improves safety

### 7.5 Large table / low-downtime shape

1. add nullable field / table
2. deploy
3. backfill in chunks (command/task), not a giant migration
4. add constraint / NOT NULL
5. cleanup

### 7.6 Data migrations discipline

- deterministic
- idempotent
- no external API calls
- chunk work to reduce lock time

#### `apps.get_model()` results are classes — use PascalCase

Django models are classes. When you retrieve them via `apps.get_model()` in a `RunPython` migration function, the result is a model **class**, not an instance. Use PascalCase for the variable name, matching standard Python class naming:

```python
# Correct — model classes use PascalCase
ContentType = apps.get_model("contenttypes", "ContentType")
Permission = apps.get_model("auth", "Permission")
MyModel = apps.get_model("myapp", "MyModel")

# Wrong — do NOT rename to snake_case even if linters complain
content_type = apps.get_model("contenttypes", "ContentType")  # ← no
```

Static analysis tools (SonarQube, pylint) may flag PascalCase local variables. **Ignore or suppress these warnings** — the Django convention of PascalCase for model references is correct and takes precedence.

### 7.7 `post_migrate` signal and permission assignment

Django's `post_migrate` signal — which auto-creates `Permission` objects for new models — fires **after all migrations have run**, not after each individual migration. This means:

- A `RunPython` step **in the same migration** that creates a model will **not** find the auto-generated `Permission` rows; they don't exist yet.
- Code that does `Permission.objects.filter(codename=...).first()` will silently return `None`, and group assignments will be skipped with no error.

**Two safe patterns:**

#### Pattern A: Explicitly create ContentType + Permission in the migration

Use `get_or_create` so the `RunPython` doesn't depend on the signal:

```python
def assign_permissions(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    for model_name in ["mymodel"]:
        ct, _ = ContentType.objects.using(db_alias).get_or_create(
            app_label="myapp", model=model_name,
        )
        perms = {}
        for action in ("add", "change", "delete", "view"):
            perm, _ = Permission.objects.using(db_alias).get_or_create(
                codename=f"{action}_{model_name}",
                content_type=ct,
                defaults={"name": f"Can {action} {model_name}"},
            )
            perms[action] = perm

        # Now safe to assign to groups
        if group := Group.objects.using(db_alias).filter(name="MyGroup").first():
            group.permissions.add(perms["view"])
```

#### Pattern B: Use two separate migrations

1. **Migration N** — `CreateModel` only (schema).
2. **Migration N+1** — `RunPython` for data seeding + permission assignment.

Because `post_migrate` fires between `migrate` invocations in dev (and between migration files when the full batch completes in CI), the second migration will find the auto-created `Permission` objects.

> **Prefer Pattern A** — it is self-contained, works in all environments, and doesn't rely on signal timing. Use Pattern B only when you intentionally want a clean separation between schema and data.

### 7.8 ForeignKey + index migrations (Postgres: avoid accidental constraint rebuilds)

Non-obvious but critical: small model changes can translate to **dangerous SQL** on large tables.

- Always inspect generated SQL for relationship/index changes:
  - `sqlmigrate` is mandatory when touching `ForeignKey` fields, `db_index`, `db_constraint`, or custom indexes.
- Beware of "index-only" changes that trigger `AlterField`.
  - Depending on the backend and Django's migration planner, an `AlterField` may drop/recreate the FK constraint (and associated objects), causing locks/downtime.
  - If you only want to change indexes, prefer explicit index operations.

Low-downtime index ops on live Postgres:

- Use concurrent index operations where possible (not allowed inside a transaction).
  - Prefer `AddIndexConcurrently` / `RemoveIndexConcurrently` (from `django.contrib.postgres.operations`).
  - Set `atomic = False` on the migration.
- `DROP INDEX CONCURRENTLY` has limitations (Postgres): you can't use it for an index that backs a `UNIQUE` / `PRIMARY KEY` constraint.
- In non-atomic migrations, ordering matters:
  - create the new index first
  - then drop the old index
  - avoid a window with _no_ supporting index.

When Django's model state must change but DB operations must be controlled:

- Use `SeparateDatabaseAndState` to keep Django's migration state accurate while executing only the safe DB operations you intend.
- Custom SQL must be reversible (`reverse_sql`) and follow concurrency constraints (e.g. `DROP INDEX CONCURRENTLY` requires `atomic = False`).
