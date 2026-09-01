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

### Exception handling

Catch the narrowest exception the operation can actually raise. A broad `except Exception` swallows the bugs you most need to see.

Never catch bug-exceptions — `NameError`, `AttributeError`, or a `TypeError` from a wrong call signature. These signal a defect in your own code; catching them turns a loud crash into silent wrong behaviour. Let them propagate.

```python
# bad — a typo'd attribute is now invisible
try:
    total = order.subttl * rate
except Exception:
    total = 0
```

Prefer preemptive validation over `try`/except when the check is cheap:

```python
# bad
try:
    value = config["timeout"]
except KeyError:
    value = DEFAULT_TIMEOUT

# good
value = config.get("timeout", DEFAULT_TIMEOUT)
```

Broad `except Exception` is justified only at a **fail-soft seam** — a daemon loop that must survive one bad iteration, a plugin boundary that must not let one plugin crash the host. There, always log and either re-raise or record; never swallow silently:

```python
for job in queue:
    try:
        run(job)
    except Exception:
        logger.exception("job failed: %s", job.id)
        job.mark_failed()
```

`except BaseException` is reserved for cleanup-then-raise (it also catches `KeyboardInterrupt`/`SystemExit`); always re-raise after the cleanup.

Multiple exception types need no brackets when there is no `as` clause (PEP 758):

```python
try:
    connect_to_server()
except TimeoutError, ConnectionRefusedError:
    reconnect()

try:
    connect_to_server()
except (TimeoutError, ConnectionRefusedError) as exc:  # `as` still needs the brackets
    logger.warning("connect failed: %s", exc)
```

Never leave a `finally` block with `return`, `break`, or `continue`. The compiler emits a
`SyntaxWarning` for it (PEP 765):

```python
# bad — the return discards whatever the try raised
def load(path: Path) -> str:
    try:
        return path.read_text()
    finally:
        return ""
```

### Exception groups for concurrent/batch failures

When an operation can fail in multiple independent ways at once — fanning out over `asyncio.TaskGroup`, a thread pool, or validating a batch where every error matters, not just the first — raise an `ExceptionGroup` instead of surfacing one exception and discarding the rest:

```python
# bad — only the first validation error surfaces, the rest are silently lost
def validate(items: list[Item]) -> None:
    for item in items:
        item.validate()  # raises on the first bad item; later items never checked

# good — collect every failure, report them all
def validate(items: list[Item]) -> None:
    errors = [e for item in items if (e := _validate_one(item)) is not None]
    if errors:
        raise ExceptionGroup("validation failed", errors)
```

Catch with `except*`, which pulls out only the matching subset by type — unmatched exceptions keep propagating in a new group:

```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(fetch(url_a))
        tg.create_task(fetch(url_b))
except* TimeoutError as eg:
    for e in eg.exceptions:
        logger.warning("timed out: %s", e)
except* ValueError as eg:
    for e in eg.exceptions:
        logger.error("bad response: %s", e)
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

### `dict.get(key, default)` does not defend against an explicit `None`

The default is substituted only when the key is **absent**, not when it is present with a `None` (e.g. JSON `null`) value. Chaining `.get()` on the result then crashes:

```python
# bad — crashes with AttributeError when payload is {"author": None}
username = note.get("author", {}).get("username")

# good — coerce a missing OR null value to the empty container
username = (note.get("author") or {}).get("username")
```

Any time a value may legitimately be `null` from an external source (API payloads, parsed JSON), use `... or <default>` rather than relying on the `.get` default.

---

## Typing: Full Modern Annotations

### Use built-in generics

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

### `type` statement for recurring complex types

```python
type Matrix = list[list[float]]
type Headers = dict[str, str]

def apply(m: Matrix, headers: Headers) -> Matrix: ...
```

### `NewType` for non-interchangeable primitives

A `type X = ...` alias is **transparent**: `UserId = int` and a bare `int` are interchangeable, so the checker won't catch you passing an `OrderId` where a `UserId` is expected. Use `NewType` when two values share a primitive but must never cross — it creates a **distinct, opaque** type the checker enforces:

```python
from typing import NewType

UserId = NewType("UserId", int)
OrderId = NewType("OrderId", int)

def cancel_order(order: OrderId) -> None: ...

uid = UserId(42)
cancel_order(uid)  # type error — UserId is not OrderId
```

Rule of thumb: `type` alias for readability of a structurally-complex type; `NewType` when the danger is mixing up two same-primitive values (ids, tokens, raw vs. sanitized strings).

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

Import a type that appears only in annotations under a `TYPE_CHECKING` guard, so the
import never runs at runtime and cannot close a cycle.

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
```

PEP 649 makes annotation evaluation lazy, so a forward reference in a signature resolves
without quoting and `from __future__ import annotations` is not needed for the annotations
themselves.

**Lazy is not the same as never evaluated.** Anything that *materializes* annotations
evaluates them for real, and a name imported only under `TYPE_CHECKING` is not bound at
runtime — so it raises `NameError` at the point of materialization, not at import. The
eager readers to watch for:

- `typing.get_type_hints()` and anything built on it
- `dataclasses.dataclass` field resolution, and Pydantic model construction
- Django's `as_view()` and system checks, which walk annotations during startup

So the `TYPE_CHECKING` guard still earns its place: it keeps the import cost out of the
runtime path. If a type is read back at runtime by any of the above, import it normally
rather than under the guard.

Read deferred annotations back with `annotationlib.get_annotations(obj, format=...)`.
`Format.VALUE` evaluates them, `Format.FORWARDREF` substitutes a `ForwardRef` proxy for a
name that cannot be resolved, and `Format.STRING` returns the annotation's source text.

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
