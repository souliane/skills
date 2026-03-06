# Background Work, Security, Settings, Observability, Caching, Async (Sections 10–14, 16)

> Load when working on background tasks, deployment, logging, caching, or async views.

---

## 10. Background work

### 10.1 Django 6 tasks

Write against `django.tasks` (`@task`, `.enqueue()`).

> **Note:** Django 6.0 ships `ImmediateBackend` (sync, dev/test) and `DummyBackend` (testing). Production requires a third-party backend that provides an actual worker process.

### Django 5.2 note

Use Celery/Huey/RQ/etc.

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
