# Models & Schema Bible + QuerySets (Sections 4–5)

> Load when working on model changes, query optimization, or schema design.

---

## 4. Models & schema bible

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

### 5.4 Query hygiene

- don't rely on implicit ordering
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
