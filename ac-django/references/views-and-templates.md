# Views, Forms, Templates, and More (Sections 8–9, 16a–16e)

> Load when working on views, templates, form handling, HTMX, file uploads, i18n, middleware, management commands, or connection pooling.

---

## 8. Views, forms, and templates (HTML boundary)

### 8.1 Views are orchestration

Views:

- authenticate/authorize early
- validate input (form)
- shape QuerySets (select/prefetch)
- call a domain method
- return response

### 8.2 Forms are boundary validation

- forms validate request payload
- forms normalize values
- domain mutation happens through model methods

### 8.3 Templates are presentation

Rules:

- no DB access
- minimal logic
- co-locate fragments (partials) to avoid template sprawl

### 8.4 Example: CBV with form_valid

```py
from django.views.generic import CreateView
from .models import Article
from .forms import ArticleForm

class ArticleCreateView(CreateView):
    model = Article
    form_class = ArticleForm

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)
```

### 8.5 Example: DRF ViewSet with queryset shaping

```py
from rest_framework import viewsets, permissions
from .models import Article
from .serializers import ArticleSerializer

class ArticleViewSet(viewsets.ModelViewSet):
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Article.objects
            .filter(author=self.request.user)
            .select_related("author", "category")
            .prefetch_related("tags")
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
```

---

## 9. Templates, partials, HTMX ergonomics

### 9.1 Django 6 native partials

- `{% partialdef name %} ... {% endpartialdef %}`
- render fragments via `template.html#partial_name`

### Django 5.2 note

Use `django-template-partials` and plan removal on upgrade.

### 9.2 Partial definition and rendering

```html
<!-- video.html -->
<h1>{{ video.title }}</h1>

{% partialdef view_count %}
  <span id="view-count">{{ video.view_count }} views</span>
{% endpartialdef %}

<div>{{ video.description }}</div>
```

Render the full page or just the partial:

```py
# Full page
render(request, "video.html", {"video": video})

# Just the partial (for HTMX swap)
render(request, "video.html#view_count", {"video": video})
```

### 9.3 HTMX pattern: inline partial swap

```html
<!-- list.html -->
{% for item in items %}
  {% partialdef item_row %}
  <tr id="item-{{ item.pk }}" hx-target="this" hx-swap="outerHTML">
    <td>{{ item.name }}</td>
    <td>
      <button hx-post="{% url 'item-archive' item.pk %}"
              hx-confirm="Archive this item?">
        Archive
      </button>
    </td>
  </tr>
  {% endpartialdef %}
{% endfor %}
```

```py
# views.py — return only the updated row
def archive_item(request, pk):
    item = get_object_or_404(Item, pk=pk)
    item.archive()
    return render(request, "list.html#item_row", {"item": item})
```

### 9.4 Rules for HTMX + partials

- Keep partials **inside** the template that uses them (locality of behavior).
- Partial views return the same template with `#partial_name` — never create separate template files for fragments.
- Always set `hx-target` and `hx-swap` explicitly; avoid relying on defaults.
- Use `hx-confirm` for destructive actions.

---

## 16a. File uploads and media handling

### 16a.1 Model fields

```py
class Document(models.Model):
    file = models.FileField(upload_to="documents/%Y/%m/")
    image = models.ImageField(upload_to="avatars/", blank=True)  # requires Pillow
```

- Use `upload_to` with date-based subdirectories to avoid flat directories with thousands of files.
- Never serve `MEDIA_ROOT` directly in production; use a storage backend (S3, GCS) or a reverse-proxy.

### 16a.2 Upload validation

```py
from django.core.validators import FileExtensionValidator

class Document(models.Model):
    file = models.FileField(
        upload_to="documents/%Y/%m/",
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "docx", "xlsx"])],
    )
```

- Validate file type server-side (don't trust client `Content-Type`).
- Set `FILE_UPLOAD_MAX_MEMORY_SIZE` and `DATA_UPLOAD_MAX_MEMORY_SIZE` to limit upload sizes.
- For DRF, validate in the serializer's `validate_file()` method.

### 16a.3 Storage backends

- Use `django-storages` for S3/GCS/Azure.
- Configure `STORAGES["default"]` (Django 4.2+). The legacy `DEFAULT_FILE_STORAGE` setting is deprecated.
- Use signed URLs for private file access instead of serving files through Django.

---

## 16b. Internationalization and localization (i18n/l10n)

### 16b.1 Setup

```py
# settings.py
USE_I18N = True
USE_L10N = True
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("de", "German"), ("fr", "French")]
LOCALE_PATHS = [BASE_DIR / "locale"]
```

### 16b.2 Marking strings for translation

```py
from django.utils.translation import gettext_lazy as _

class Order(models.Model):
    status = models.CharField(
        max_length=20,
        verbose_name=_("status"),
    )

    class Meta:
        verbose_name = _("order")
        verbose_name_plural = _("orders")
```

In templates:

```html
{% load i18n %}
<h1>{% trans "Welcome" %}</h1>
<p>{% blocktrans with name=user.first_name %}Hello, {{ name }}!{% endblocktrans %}</p>
```

### 16b.3 Rules

- Use `gettext_lazy` (`_`) for model field labels, form labels, and anything evaluated at import time.
- Use `gettext` for strings in view/function bodies (evaluated at request time).
- Run `django-admin makemessages -l <locale>` to extract strings; `compilemessages` to compile `.po` -> `.mo`.

---

## 16c. Middleware conventions

### 16c.1 Middleware structure

```py
class TimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time
        start = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - start
        response["X-Request-Duration"] = f"{duration:.3f}s"
        return response
```

### 16c.2 Rules

- Keep middleware small and focused on a single cross-cutting concern.
- Order matters: security middleware first, then auth, then application-specific.
- Avoid DB queries in middleware unless absolutely necessary (runs on every request).
- Use `process_exception` sparingly; prefer Django's exception handling.

---

## 16d. Management commands

### 16d.1 Command structure

```py
# myapp/management/commands/backfill_slugs.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Backfill slugs for articles missing them"

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        total = Article.objects.filter(slug="").count()
        self.stdout.write(f"Found {total} articles without slugs")

        processed = 0
        while True:
            batch = list(Article.objects.filter(slug="")[:batch_size])
            if not batch:
                break
            for article in batch:
                article.slug = slugify(article.title)
            if not options["dry_run"]:
                Article.objects.bulk_update(batch, ["slug"])
            processed += len(batch)
            self.stdout.write(f"Processed {processed}/{total}")
```

### 16d.2 Rules

- Always add `--dry-run` for data-modifying commands.
- Process in batches to limit memory and lock duration.
- Use `self.stdout.write` (not `print`) for output.
- Management commands are the right place for one-off data backfills, not data migrations (when the backfill is large or external).

---

## 16e. Connection pooling

### 16e.1 Django 5.1+ built-in pooling

```py
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "OPTIONS": {
            "pool": True,  # enables built-in connection pooling (Django 5.1+)
        },
    }
}
```

### 16e.2 Rules

- Enable connection pooling in production to avoid per-request connection overhead.
- For Django < 5.1 or advanced needs, use `django-db-connection-pool` or PgBouncer.
- Set `CONN_MAX_AGE` to a reasonable value (e.g., 600 seconds) if not using pooling.
- Monitor connection counts; pool size should match expected concurrency.

---

## Django 6 Reference Snippets

### Partial rendering endpoint pattern

```py
from django.shortcuts import render

def page(request):
    ...
    return render(request, "video.html", {...})

def fragment(request):
    ...
    return render(request, "video.html#view_count", {...})
```

### Django 6 tasks pattern

```py
from django.tasks import task

@task
def resize_video(video_id: int) -> None:
    ...

def upload_video(request):
    ...
    resize_video.enqueue(video.id)
    ...
