# Django Antipatterns and Patterns (Section 22)

> Load during code review or when avoiding common Django mistakes.
> Paraphrased checklist based on <https://www.django-antipatterns.com/>

---

## 22.1 Antipatterns (avoid)

- **A GET request with side-effects**: Keep GET safe/idempotent. Use `POST`/`PUT`/`PATCH`/`DELETE` for mutations; enforce with `@require_POST` / `@require_http_methods`.

  ```py
  # BAD: GET with side effects
  def delete_item(request, pk):
      Item.objects.filter(pk=pk).delete()
      return redirect("item-list")

  # GOOD: require POST
  @require_POST
  def delete_item(request, pk):
      get_object_or_404(Item, pk=pk).delete()
      return redirect("item-list")
  ```

- **A model with a `Model` suffix**: Name the model after the domain concept (`Car`, not `CarModel`).
- **Calling `.all()` before `.count()` / `.filter()` / etc.**: Don't add redundant `.all()` calls; chain on the base manager/queryset directly.
- **Chaining querysets together**: Combine at the ORM layer (`qs1 | qs2` or `.union(...)`) instead of evaluating in Python. Only `itertools.chain(...)` when you explicitly want a mixed-type sequence.
- **Checking if an object is created with `instance.pk`**: Use `instance._state.adding` to detect "new instance vs loaded from DB". If you need to know whether a row exists, query the DB.
- **Checking ownership through `UserPassesTestMixin`**: Prefer filtering in `get_queryset()` (e.g., `.filter(owner=request.user)`) to avoid leaking object existence and to keep checks DB-side.
- **Checking request method with `if request.POST`**: Use `request.method == "POST"` (or CBV `.post(...)`/`.get(...)`). Consider blocking unexpected methods with `@require_http_methods`.
- **Constructing a new form when validation fails**: Re-render the _bound_ form so user input and `form.errors` are preserved.
- **Data duplication**: Avoid storing derived state twice. Prefer computed properties; if you need writable semantics, write through to the source field(s).
- **Fetching the logged-in user with a query**: Use `request.user`. If you need the latest DB state, call `request.user.refresh_from_db()`.
- **Fill the primary key gaps**: Don't try to "reuse" deleted IDs. Treat primary keys as opaque; let the DB generate them.
- **Filter on arbitrary input like `request.GET`**: Don't pass request query dicts directly to ORM filtering. Whitelist/validate allowed filters (e.g., via `django-filter` / DRF filter backends).
- **Filtering in the template**: Don't do data selection in templates. Filter and prefetch in QuerySets/views; templates should only render.

  ```py
  # BAD: filtering in template (N+1 and logic leak)
  # {% for item in order.items.all %}{% if item.is_active %}...{% endif %}{% endfor %}

  # GOOD: filter in view, pass to template
  context["active_items"] = order.items.filter(is_active=True).select_related("product")
  ```

- **Foreign key with `_id` suffix**: Don't name `ForeignKey` fields `*_id`. Name them by relation (`author`), and use Django's implicit `author_id` attribute when you need the raw ID.

  ```py
  # BAD: redundant _id suffix
  class Article(models.Model):
      author_id = models.ForeignKey(User, on_delete=models.CASCADE)
      # creates DB column author_id_id

  # GOOD: semantic name
  class Article(models.Model):
      author = models.ForeignKey(User, on_delete=models.CASCADE)
      # DB column: author_id (auto), use article.author_id for raw FK
  ```

- **Giving `related_name=...` the same name as the relation**: Make reverse relations descriptive and collision-free (often plural: `posts`, or domain-specific: `authored_posts`), or omit to use the default `*_set`.
- **Imports**: Prefer explicit, readable imports; group them (stdlib / third-party / local) and keep them at the top (use tooling like ruff/isort).
- **Manually constructing a slug**: Use `django.utils.text.slugify` (and make uniqueness/redirect strategy explicit). Consider autoslug tooling if it fits.
- **Modifying slugs and primary keys of model objects**: Keep PKs and public slugs stable. If you must change them, implement permanent redirects and maintain an "old slug -> new slug" mapping.
- **Non-atomic `JSONField`s**: If JSON has a stable structure and you need to query/filter inside it, normalize it into relational models with constraints. Use JSON for genuinely unstructured blobs.
- **(Over)use of `.values()`**: Prefer model instances. Use `.values()` mainly for aggregation/grouping; use `.only()`/`.defer()` for column trimming; use serializers/DTOs for API payloads.
- **Passing function references to `reverse(...)`**: Reverse by URL name (and namespace), not by passing the view callable.
- **Passing parameters directly in the query string of a URL**: URL-encode query values (e.g., `{{ value|urlencode }}`) instead of interpolating raw strings.
- **Plural model class names**: Use singular model class names. Use `db_table` and `verbose_name_plural` when integrating with existing DB naming.
- **Processing request data manually**: Use `Form`/`ModelForm` (or DRF serializers) for parsing, validation, and cleaning; you can still render custom HTML.
- **Refer to the User model directly**: Use `settings.AUTH_USER_MODEL` for relations and `get_user_model()` when you need the class.
- **Rendering content after a successful POST request**: Apply Post/Redirect/Get: after successful POST, return a redirect so refresh doesn't resubmit.
- **Rendering into JavaScript**: Don't interpolate raw values into JS. Use `|json_script` + `JSON.parse(...)`.
- **Return a `JsonResponse` with `safe=False`**: Prefer returning an object/dict (wrap lists in `{"data": [...]}`) rather than `safe=False` list responses.
- **Run `makemigrations` in production**: Generate and commit migrations during development; run `migrate` in deploy with review/backups.
- **Signals**: Avoid signals for core domain flow. Prefer explicit method calls and/or derived values (e.g., `annotate(...)`). Signals are most appropriate for integrating third-party app events; remember they won't run in data migrations.

  ```py
  # BAD: signal for core business logic (hidden, fragile)
  @receiver(post_save, sender=Order)
  def create_invoice_on_order(sender, instance, created, **kwargs):
      if created:
          Invoice.objects.create(order=instance, amount=instance.total)

  # GOOD: explicit call in domain method
  class Order(models.Model):
      def place(self):
          self.status = "placed"
          self.save(update_fields=["status"])
          Invoice.objects.create(order=self, amount=self.total)
  ```

- **Use `datetime.now` as `default=...` for a `created_on` field**: Use `auto_now_add=True` (and `auto_now=True` for updates) or a callable like `timezone.now`.
- **Use `.get(...)` to retrieve the object in a view**: Prefer `get_object_or_404(...)` (and in CBVs, scope via `get_queryset()`).
- **Users controlling a primary key**: Don't let user input choose PKs. Put user-controlled identifiers in dedicated unique fields.
- **Using a `FloatField` for currencies**: Use `DecimalField` for money values; consider money libraries that also store currency codes.

  ```py
  # BAD: floating point rounding errors
  class Product(models.Model):
      price = models.FloatField()  # 0.1 + 0.2 != 0.3

  # GOOD: exact decimal arithmetic
  class Product(models.Model):
      price = models.DecimalField(max_digits=10, decimal_places=2)
  ```

- **Using `commit=False` when altering the instance in a `ModelForm`**: Prefer setting `form.instance` fields before `form.save()`. Use `commit=False` only when you truly need to defer saving.
- **Using `len(...)` on a QuerySet with no further use**: Use `.count()` when you only need a count. If you'll iterate anyway, evaluate once and reuse to avoid double queries.
- **Using multiple forms on the same page without prefixing**: Use unique `prefix=` for each form in both GET and POST branches; use formsets for collections.
- **Using regular HTML comments instead of Django template comments**: Use `{# ... #}` / `{% comment %}{% endcomment %}` so comments don't leak to the client.
- **Using `request.POST or None`**: Branch on `request.method` and pass `request.POST` only for POST requests (POST bodies can be empty).

---

## 22.2 Patterns (use)

- **A default record per entity**: Model the "default" with a boolean flag + conditional `UniqueConstraint` to enforce "only one default". Fetch defaults in bulk with `FilteredRelation(...)` + `select_related(...)` to avoid N+1 queries.
- **A field derived from another field**: If you must persist a denormalized derived column, make it non-editable and populate it automatically (e.g., custom field `pre_save(...)`); ensure migrations work (`deconstruct`) and define bulk behavior.
- **A `SET(...)` delete handler with the object as parameter**: For complex `on_delete` semantics, implement a custom handler (modeled after Django's `SET`) that can compute per-row updates (and optionally cascade specific rows).
- **Annotate a condition as `BooleanField`**: Use `ExpressionWrapper(Q(...), output_field=BooleanField())` to annotate boolean flags computed by the DB (optionally wrap as a helper).
- **Date(Time)Fields that store a week/month**: Normalize dates to a bucket (e.g., "first day of month" or "start of week") via a custom field/mixin so reads and writes are consistently truncated.
- **Dictionary lookups for the database**: For small mappings, use `Case/When` to annotate values from an in-memory dict. If it grows, store mapping data in the DB instead of shipping a big CASE expression.
- **Match multiple strings case-insensitively**: Build an escaped regex and use `__iregex` for case-insensitive multi-match (anchor with `^`/`$` if needed).
- **Querying in the opposite direction**: For advanced "value matches regex stored in a field" cases, use `.alias(Value(...)).filter(val__regex=F('pattern'))` (or explicit lookup objects) instead of pulling rows into Python.
- **Set values on created/updated objects in CBVs**: In CBVs, set derived fields in `form_valid()` via `form.instance` (extract into a mixin when reused). Apply similar ideas in `ModelAdmin.save_model(...)`.

---

## 22.3 Difference between

- **`ForeignKey` vs `OneToOneField`**: A `OneToOneField` is a `ForeignKey(unique=True)`. Use it when the relation must be unique; reverse access returns a single object (or raises) instead of a manager/set.
- **`reverse(...)` vs `redirect(...)`**: `reverse(...)` returns a URL string; `redirect(...)` returns an HTTP redirect response (temporary or permanent). `redirect(...)` also accepts URLs and model instances.

---

## 22.4 Troubleshooting

- **Field missing from migrations/table**: Common causes include a trailing comma (singleton tuple), using `:` (type annotation) instead of `=`, or accidentally importing a form field instead of `models.*`. Prefer explicit `models.<Field>` usage.
- **Can't extract/filter datetimes with time zones (MySQL)**: Load time zone tables into MySQL (e.g., `mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql ... mysql`) so date extraction works with time zones.

---

## 22.5 Q&A

- **How manager/queryset methods work**: Manager methods usually proxy to `get_queryset()` and then call the corresponding QuerySet method. Put reusable query logic on a custom QuerySet and expose it via `as_manager()` / `Manager.from_queryset(...)`.
