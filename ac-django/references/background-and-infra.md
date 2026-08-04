# Background Work, Security, Settings, Observability, Caching, Async (Sections 10–14, 16)

> Load when working on background tasks, deployment, logging, caching, or async views.

---

## 10. Background work

### 10.1 Django 6 tasks

Write against `django.tasks` (`@task`, `.enqueue()`).

> **Note:** Django 6.0 ships `ImmediateBackend` (sync, dev/test) and `DummyBackend` (testing). Production requires a third-party backend — Django's own docs are deliberately backend-agnostic here and point to the [Community Ecosystem page](https://www.djangoproject.com/community/ecosystem/#tasks) rather than recommending one.

### Django 5.2 note

Use Celery/Huey/RQ/etc.

### 10.1a Production backend: `django-tasks-db`

Default to `django-tasks-db`'s `DatabaseBackend` absent a project-specific reason for Celery/RQ/etc. — a DB-backed queue needs no extra broker infrastructure, and it's what real production Django apps land on ([Haki Benita's writeup](https://hakibenita.com/django-reliable-signals) reaches the same choice independently).

```py
# settings.py
INSTALLED_APPS = [
    ...,
    "django_tasks",
    "django_tasks_db",
]

TASKS = {
    "default": {
        "BACKEND": "django_tasks_db.DatabaseBackend",
        # Name additional queues to isolate a heavy/slow lane from a
        # latency-sensitive one — a backlog on one queue never starves another.
        "QUEUES": ["default", "urgent"],
    },
}
```

Route a task to a specific queue:

```py
@task(queue_name="urgent")
def send_password_reset(user_id: int) -> None: ...
```

Run the worker — the production process, one per queue when isolation matters:

```sh
python manage.py db_worker --queue-name default,urgent
# or isolate: one worker process per queue
python manage.py db_worker --queue-name urgent
python manage.py db_worker --queue-name default
```

`db_worker` claims each row inside an exclusive DB transaction before executing it, so multiple workers on the same queue never double-run a task — that locking doesn't need hand-rolling.

### 10.2 Task definition and enqueue

```py
from django.tasks import task
from django.db import transaction

@task
def send_welcome_email(user_id: int) -> None:
    user = User.objects.get(pk=user_id)
    mail.send_mail(
        subject="Welcome",
        message=f"Hello {user.first_name}",
        from_email=None,
        recipient_list=[user.email],
    )

# Enqueue after commit (safe pattern)
def register_user(request):
    user = User.objects.create_user(...)
    transaction.on_commit(lambda: send_welcome_email.enqueue(user.pk))
    return redirect("dashboard")
```

With a DB-backed queue specifically, `.enqueue()` is an ordinary ORM write — calling it directly inside `transaction.atomic()` already commits or rolls back with the rest of the transaction, and other connections (including a worker polling for `READY` rows) only see it after commit, by ordinary transaction isolation. The `transaction.on_commit()` wrap above is Django's generic, backend-agnostic pattern — needed because a broker-based backend (Celery/Redis/RQ) sits *outside* Django's transaction, so a task could otherwise fire before the triggering write is even committed. `django-tasks-db` doesn't have that problem, so plain `atomic()`-block placement is sufficient with it.

### 10.3 Retry and idempotency patterns

```py
@task
def process_payment(payment_id: int) -> None:
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.status == "processed":
        return  # idempotent: already done

    result = payment_gateway.charge(payment.amount, payment.token)
    payment.status = "processed" if result.success else "failed"
    payment.save(update_fields=["status"])
```

### 10.4 Rules

- Tasks accept IDs (not ORM objects) — the object may change between enqueue and execution.
- Tasks are thin orchestration: fetch object, call domain method, done.
- Tasks must be idempotent or safely retryable.
- Enqueue after commit when triggered by writes (`transaction.on_commit`).

---

## 11. Security (docs-mirror checklist)

Baseline: <https://docs.djangoproject.com/en/6.0/topics/security/>

### 11.1 Core protections

- CSRF enabled for session-auth endpoints
- XSS: rely on autoescaping, avoid unsafe marking
- clickjacking protections enabled
- host header validation via `ALLOWED_HOSTS`
- secure cookies in production

### 11.2 CSP

**Django 6:** native CSP config + nonces; avoid `unsafe-inline`.

**Django 5.2 note:** use `django-csp`.

### 11.3 AuthZ is boundary + invariant

- boundary checks permissions early
- critical invariants are still enforced in domain methods (defense in depth)

---

## 12. Settings & deployment (docs-mirror checklist)

Deployment checklist: <https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/>

### 12.1 Settings hygiene

- explicit defaults
- fail fast on missing required config
- keep overrides minimal and documented

### 12.2 Secret management

- secrets come from env/secret manager
- no secrets in repo

### 12.3 Production toggles

- `DEBUG = False`
- correct `ALLOWED_HOSTS`
- secure cookies
- correct proxy/TLS header config when applicable

### 12.4 Environment parity

Use `django-version-checks` to fail fast when prod/test/dev drift (Python, Postgres, etc.).

### 12.5 Image-slimming risk checklist

Slimming a Django image is risky because Django imports modules dynamically (apps, migrations, templatetags) that static analysis can't see.

- **Multi-stage `uv` build first.** A builder stage with full toolchain + a runtime stage copying only `.venv` and the app is the safe default. Reach for a slimming tool (`docker-slim` etc.) only if multi-stage isn't enough.
- **If you slim, run the Django smoke matrix after slimming** — all must pass before any MR:
  - admin renders (`/admin/` returns the login page)
  - locale/i18n loads (translations resolve, no `LANG`/locale errors)
  - `collectstatic --noinput` succeeds
  - `libpq` and native deps import (`import psycopg`, Pillow, etc.)
  - one real management command runs end to end (`migrate --check`, a custom command)
- **Keep `--include-path` lists for Django's dynamic imports** — installed apps, `migrations/`, `templatetags/`, any module loaded by string. Slimming tools prune these because nothing imports them statically.
- **Pin the slimming tool version** and verify the slimmed image actually boots and serves a request before opening the MR — a passing build is not a running image.

---

## 13. Observability (logging, metrics, audit)

### 13.1 Logging

- structured logs in prod
- include request IDs
- include domain identifiers

#### structlog setup example

```py
# settings.py
import structlog

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer() if DEBUG else structlog.processors.JSONRenderer(),
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
```

#### Request-ID middleware example

```py
import uuid
import structlog

class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        structlog.contextvars.unbind_contextvars("request_id")
        return response
```

### 13.2 Metrics

Track:

- endpoint latency + error rates
- queue depth + task failures
- slow DB queries + connection health

### 13.3 Audit trails

Persist audit events for sensitive operations:

- permission changes
- money movement
- account changes
- sensitive data access

---

## 14. Caching and performance

Cache docs: <https://docs.djangoproject.com/en/6.0/topics/cache/>

### 14.1 Cache only after query shaping

Before caching:

- remove N+1
- add necessary indexes
- use annotations/expressions

### 14.2 Cache invalidation discipline

- keys encode relevant parameters
- invalidate on write via domain methods (mutation is centralized)

### 14.3 Per-view vs low-level caching

- prefer per-view caching for stable pages
- low-level caching for expensive computed values

#### Per-view cache example

```py
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)  # 15 minutes
def product_list(request):
    products = Product.objects.for_list()
    return render(request, "products/list.html", {"products": products})
```

#### Low-level cache with invalidation

```py
from django.core.cache import cache

class Product(models.Model):
    def get_stats(self):
        cache_key = f"product_stats_{self.pk}"
        stats = cache.get(cache_key)
        if stats is None:
            stats = self._compute_expensive_stats()
            cache.set(cache_key, stats, timeout=60 * 60)
        return stats

    def save(self, **kwargs):
        super().save(**kwargs)
        cache.delete(f"product_stats_{self.pk}")  # invalidate on write
```

---

## 16. Async & concurrency

Async docs: <https://docs.djangoproject.com/en/6.0/topics/async/>

### 16.1 Async safety rule

- ORM is generally sync; avoid calling sync ORM from async contexts unless using Django's documented patterns.

### 16.2 When to use async views

- use async only when it reduces I/O latency (e.g., concurrent external calls)
- keep domain operations sync unless there is a strong reason

### 16.3 Concurrency correctness

- rely on transactions/locks
- design idempotent tasks and retry-safe operations

### 16.4 Example: async view with concurrent external calls

```py
import asyncio
import httpx
from django.http import JsonResponse

async def dashboard_data(request):
    async with httpx.AsyncClient() as client:
        weather, news = await asyncio.gather(
            client.get("https://api.weather.example.com/current"),
            client.get("https://api.news.example.com/headlines"),
        )
    return JsonResponse({
        "weather": weather.json(),
        "news": news.json(),
    })
```

### 16.5 Example: sync_to_async bridge for ORM access in async views

```py
from asgiref.sync import sync_to_async
from django.http import JsonResponse

async def user_detail(request, pk):
    user = await sync_to_async(User.objects.get)(pk=pk)
    return JsonResponse({"email": user.email, "name": user.get_full_name()})
```
