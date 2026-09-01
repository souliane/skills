# Models & Schema Bible + QuerySets (Sections 4–5)

> Load when working on model changes, query optimization, or schema design.

---

## 4. Models & schema bible

Minimum supported databases: PostgreSQL 15+, MySQL 8.4+, MariaDB 10.11+, SQLite 3.37+.

### 4.1 Model class ordering (strict)

1. constants
2. choices (`TextChoices`/`IntegerChoices`)
3. fields
4. managers
5. `Meta`
6. `__str__`
7. `save()` (avoid overriding if a declarative alternative exists)
8. `get_absolute_url()`
9. `@property`
10. public domain methods
11. private methods

### 4.2 Field semantics (docs-aligned)

- `null` controls DB nullability; `blank` controls validation.
- Avoid `null=True` on strings unless tri-state semantics are required.
- `choices` can be a callable (Django 5.0+) instead of a static list/mapping — use it for choices that change without a schema change (settings-driven, looked up from another table, a third-party inventory like currencies/timezones). Migrations serialize the function reference, not the values, so the list changing never produces a no-op migration ([Adam Johnson](https://adamj.eu/tech/2025/05/03/django-choices-change-without-migration/)). Doesn't help if the choices are also enforced by a DB-level constraint — that still needs its own migration.

### 4.3 Constraints and indexes (correctness-first)

Use:

- `UniqueConstraint` (including conditional uniqueness)
- `CheckConstraint` (valid state combos, non-negative amounts, etc.)
- indexes that map to known query shapes

Rule: indexes are not decoration.

### 4.4 Relationship discipline

- Always set `related_name` intentionally.
- Choose `on_delete` intentionally.
- Avoid accidental cascades on core domain data.
- `on_delete=models.DB_CASCADE` / `DB_SET_NULL` / `DB_SET_DEFAULT` (6.1+) push the delete into the database's own `ON DELETE` clause instead of Django loading the referencing rows first. Faster for large fan-out deletes, but `DB_CASCADE` does **not** fire `pre_delete`/`post_delete` signals — don't reach for it on a relation whose deletion something else listens for.

#### 4.4.1 ForeignKey discipline (indexing + locks + migrations)

Foreign keys are not "just relationships" in production: they affect **indexes**, **delete performance**, and **locks**.

- A `ForeignKey` creates a database index by default.
  - Only disable it (`db_index=False`) when you are intentionally creating a better index via `Meta.indexes` (multi-column or partial), and you have verified query shapes.
- Avoid redundant indexes.
  - If you already have a `UniqueConstraint` / `Index` whose leading columns start with the FK column (e.g. `(customer_id, external_id)`), the implicit FK index on `customer_id` is often redundant.
- Don't remove FK indexes "because we rarely join".
  - FK indexes also matter for deletes of the referenced row (e.g. `PROTECT`, `CASCADE`, `RESTRICT`) since the database must check referencing rows.
- Nullable + sparse FK columns can often use a partial index (Postgres) to save space and improve write speed.
  - Pattern: set `db_index=False` on the FK field, then add a partial index for `WHERE fk_id IS NOT NULL`.

Example (Postgres partial index for a sparse nullable FK):

```py
from django.db import models
from django.db.models import Q

class Event(models.Model):
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_index=False,
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["customer"],
                name="event_customer_not_null_idx",
                condition=Q(customer__isnull=False),
            ),
        ]
```

### 4.5 Generated fields / DB defaults / composite keys

- Prefer `models.GeneratedField` for queryable derived values.
- Prefer `db_default=` when the DB must own default behavior.
- Composite primary keys are allowed when they match domain identity.
  - If you use them, prefer the native API (e.g. `models.CompositePrimaryKey(...)`) when available for your Django version.
- `JSONNull()` (6.1+) is the explicit way to store or query a top-level JSON `null` on a `JSONField`. Bare `None` for that purpose is deprecated; key and index lookups are unaffected.
- `UUID4()` and `UUID7()` (6.1+) generate UUIDs database-side. `UUID7()` produces a version 7 UUID, which starts with a time-based component; it needs PostgreSQL 18+, MariaDB 11.7+, or SQLite under Python 3.14 or later.

---

## 5. QuerySets, Managers, and ORM performance

### 5.1 QuerySet methods are the collection API

Rules:

- return QuerySets (not lists)
- keep them chainable
- name them after business meaning (`overdue()`, `payable()`, `visible_to(user)`)

### 5.2 Graph loading helpers

Patterns:

- `for_api()` for DRF
- `for_list()` / `for_detail()`
- `with_*()` for specific relations

### 5.3 N+1 elimination checklist

- FK/OneToOne: `select_related()`
- reverse FK/M2M: `prefetch_related()`
- filtered prefetch: `Prefetch(...)`
- templates must not trigger queries
- `select_related()` with no arguments is deprecated (6.1+) — name the fields you want, or use `FETCH_PEERS`.

#### Fetch modes (6.1+)

A fetch mode decides what Django does when code touches a field the original
query did not load. Set one with `QuerySet.fetch_mode(mode)`. The modes are
defined in `django.db.models.fetch_modes` and re-exported into
`django.db.models`; the documented convention is `from django.db import models`
and then `models.<mode>`.

```py
from django.db import models

books = Book.objects.fetch_mode(models.FETCH_PEERS)  # 2 queries, not 1 + N
```

| Mode | Behavior |
| --- | --- |
| `FETCH_ONE` | Fetches the field for the current instance only. The default, and the 1 + N shape. |
| `FETCH_PEERS` | Fetches the field for every instance that came from the same QuerySet — 2 queries total, like an on-demand `prefetch_related()`. |
| `FETCH_RAISE` | Raises `FieldFetchBlocked` instead of querying. |

They apply to `ForeignKey`, `OneToOneField` and their reverse accessors, fields
deferred by `defer()` / `only()`, and generic relations. Django copies an
instance's mode onto the related objects it fetches, so a mode covers a whole
relationship tree, not just the model the QuerySet started from. Make one the
default for a model by overriding `get_queryset()` on a custom manager:

```py
class BookManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().fetch_mode(models.FETCH_PEERS)
```

`FETCH_PEERS` is an on-demand batch, not a replacement for a deliberately shaped
`for_api()` queryset — it is the safety net for the accesses that shaping missed.

### 5.4 Query hygiene

- don't rely on implicit ordering
- `QuerySet.totally_ordered` (6.1+) reports whether a queryset is ordered and that ordering is deterministic
- `first()` / `last()` no longer fall back to primary-key ordering once `order_by()` has been called with no arguments (6.1+)
- `union()` / `difference()` / `intersection()` now apply default ordering, and raise `DatabaseError` when an `Options.ordering` field is not selected by `values()` / `values_list()` (6.1+) — call `order_by()` with no arguments after combining to clear it
- use `exists()` when you only need existence
- prefer DB-side computation for derived query values

### 5.5 Example: custom QuerySet with graph loading

```py
from django.db import models
from django.db.models import QuerySet, Prefetch

class InvoiceQuerySet(QuerySet):
    def overdue(self):
        return self.filter(due_date__lt=timezone.now(), paid_at__isnull=True)

    def for_api(self):
        return self.select_related("customer").prefetch_related(
            Prefetch("line_items", queryset=LineItem.objects.select_related("product"))
        )

    def visible_to(self, user):
        if user.is_staff:
            return self
        return self.filter(customer__user=user)

class Invoice(models.Model):
    objects = InvoiceQuerySet.as_manager()
    # ...
```

Usage in views/serializers:

```py
Invoice.objects.overdue().for_api().visible_to(request.user)
```
