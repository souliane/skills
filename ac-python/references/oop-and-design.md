# OOP and Design

## Data Models Are First-Class Citizens

Avoid passing raw dicts or tuples across module boundaries. Model your domain with classes.

```python
# bad
def process(data: dict) -> dict:
    return {"total": data["price"] * data["qty"], "sku": data["sku"]}

# good
@dataclass(frozen=True)
class LineItem:
    sku: str
    price: Decimal
    qty: int

    @property
    def total(self) -> Decimal:
        return self.price * self.qty
```

Use `@dataclass`, `NamedTuple`, or `pydantic.BaseModel` depending on the use case:

| Use case | Recommended |
|---|---|
| Immutable value objects | `@dataclass(frozen=True)` or `NamedTuple` |
| Mutable domain models | `@dataclass` |
| External data parsing / validation | `pydantic.BaseModel` |
| DB row mapping | framework-specific (SQLAlchemy, Django ORM, etc.) |

---

## Factories Named `build_...`

Factory functions that construct a model instance are named `build_<model>`:

```python
def build_line_item(
    sku: str = "SKU-001",
    price: Decimal = Decimal("9.99"),
    qty: int = 1,
) -> LineItem:
    return LineItem(sku=sku, price=price, qty=qty)
```

This naming is deliberate: it distinguishes construction helpers from domain operations (`create`, `register`, `submit`) which may have side effects.

---

## Methods Over Module-Scope Functions

Application logic belongs on a class, not floating at module scope.

```python
# bad — module-scope function taking a dict
def calculate_discount(order: dict) -> Decimal:
    ...

# good — method on the domain object
class Order:
    def calculate_discount(self) -> Decimal:
        ...
```

Module-scope functions are appropriate for:

- Pure utilities with no domain state (`parse_date`, `slugify`, `truncate`)
- Adapters / glue code at integration boundaries

---

## `@property` and `@cached_property` for Derived Attributes

Do not compute derived values in `__init__` and store them as plain attributes. Use `@property` so derivation is transparent, or `@cached_property` when computation is expensive:

```python
# bad
class Invoice:
    def __init__(self, lines: list[LineItem]) -> None:
        self.lines = lines
        self.total = sum(l.total for l in lines)  # stale if lines mutates

# good
class Invoice:
    def __init__(self, lines: list[LineItem]) -> None:
        self.lines = lines

    @property
    def total(self) -> Decimal:
        return sum(line.total for line in self.lines)
```

Use `@cached_property` when the computation is deterministic and expensive, and the object is not mutated after construction:

```python
from functools import cached_property

class ReportData:
    def __init__(self, rows: list[Row]) -> None:
        self.rows = rows

    @cached_property
    def summary(self) -> Summary:
        return compute_expensive_summary(self.rows)
```

---

## Best Practices

### UTC timezone-aware datetimes

Always use timezone-aware `datetime` objects in UTC. Never use naive datetimes.

```python
from datetime import datetime, UTC

# bad
now = datetime.now()

# good
now = datetime.now(UTC)
```

If the project uses `arrow` or `pendulum`, follow its equivalent pattern — but always UTC-aware.

### Top-level imports only

All `import` statements must be at the top of the file. No function-level imports.

```python
# bad
def process() -> None:
    import json  # forbidden
    ...

# good (always at top)
import json

def process() -> None:
    ...
```

No `try...except ImportError` compatibility guards:

```python
# bad
try:
    import ujson as json
except ImportError:
    import json

# good — pick one and add it as a proper dependency
import ujson as json
```

### Straightforward solutions only

Pick the direct path. If a clean solution does not exist, reconsider the design before resorting to a workaround.

Do not fight third-party frameworks. If a framework provides a lifecycle hook, use it. If it expects a certain structure, follow it.

### Project layout: `src/` layout

```text
src/
  mypackage/
    __init__.py
    models.py
    api.py
tests/
  test_models.py    # mirrors src/mypackage/models.py
  test_api.py
```

Prefer `src/` layout to avoid accidental imports of the source tree without installation.
