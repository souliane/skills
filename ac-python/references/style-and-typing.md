# Style and Typing

## Style: Pythonic Code

### Prefer expressions over statements

Use list comprehensions, dict comprehensions, and generator expressions instead of `for` loops that build a collection:

```python
# bad
result = []
for item in items:
    if item.active:
        result.append(item.value)

# good
result = [item.value for item in items if item.active]
```

### Walrus operator for read-once values

```python
# bad
match = pattern.search(text)
if match:
    process(match.group(1))

# good
if match := pattern.search(text):
    process(match.group(1))
```

### stdlib first (`itertools`, `operator`, `functools`)

```python
from itertools import groupby, chain, islice
from operator import attrgetter, itemgetter
from functools import reduce

# bad
groups = {}
for item in items:
    groups.setdefault(item.category, []).append(item)

# good
sorted_items = sorted(items, key=attrgetter("category"))
groups = {k: list(v) for k, v in groupby(sorted_items, key=attrgetter("category"))}
```

### No single-use intermediate variables

```python
# bad
filtered = [x for x in items if x > 0]
total = sum(filtered)

# good
total = sum(x for x in items if x > 0)
```

Exception: when naming the intermediate result genuinely aids comprehension at the call site.

### Minimal `try` blocks and context managers

Keep `try` blocks and `with` statements to a single logical operation:

```python
# bad
try:
    data = load_file(path)
    parsed = parse(data)
    result = transform(parsed)
except ValueError:
    ...

# good
try:
    data = load_file(path)
except ValueError:
    ...
parsed = parse(data)
result = transform(parsed)
```

### Vertical whitespace for grouping

Group related lines together, separated by a blank line from unrelated logic:

```python
def process(order: Order) -> Receipt:
    customer = order.customer
    discount = customer.active_discount()

    total = order.subtotal * (1 - discount.rate)
    tax = compute_tax(total, customer.jurisdiction)

    return Receipt(total=total + tax, customer=customer)
```

---

## Typing: Full Modern Annotations

### Use built-in generics (Python 3.9+)

```python
# bad (old style)
from typing import Dict, List, Optional, Tuple

def process(items: List[str]) -> Optional[Dict[str, int]]:
    ...

# good
def process(items: list[str]) -> dict[str, int] | None:
    ...
```

### Union syntax with `|`

```python
def find(id: int) -> User | None: ...
def merge(a: str | bytes) -> str: ...
```

### `type` statement for recurring complex types (Python 3.12+)

```python
type Matrix = list[list[float]]
type Headers = dict[str, str]

def apply(m: Matrix, headers: Headers) -> Matrix: ...
```

### No duck-typing — narrow types instead

```python
# bad — checking attributes at runtime means the type is wrong
def render(obj: Any) -> str:
    if hasattr(obj, "label"):
        return obj.label
    return str(obj)

# good — use a Protocol or Union
from typing import Protocol

class Labeled(Protocol):
    label: str

def render(obj: Labeled | str) -> str:
    if isinstance(obj, str):
        return obj
    return obj.label
```

### `TYPE_CHECKING` guard for import cycles

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
```

### Annotate everything public

Functions, methods, class attributes, and module-level variables all get annotations. Private helpers too, where the type is non-obvious.

---

## Readability

### Names over comments

```python
# bad
# check if the user has not cancelled and their plan is not expired
if not user.cancelled and user.plan.end_date > now:
    ...

# good
if user.is_active:
    ...
```

### No docstrings

No docstrings on modules, classes, or functions. If the name and signature are insufficient, rename.

Exception: public library APIs exposed to external consumers may include docstrings for IDE tooling.

### Boolean parameters: force keyword-only with `, *,`

```python
# bad — caller has no idea what True means
send_email(user, True, False)

# good
def send_email(user: User, *, notify: bool, archive: bool) -> None: ...
send_email(user, notify=True, archive=False)
```
