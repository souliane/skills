# Admin and DRF Bible (Sections 15, 17)

> Load when working on Django Admin customization or DRF API endpoints.

---

## 15. Admin and ops

Admin docs: <https://docs.djangoproject.com/en/6.0/ref/contrib/admin/>

### 15.1 Admin uses the same domain API

- admin actions call model methods

### 15.2 Admin performance

- use `list_select_related`
- avoid expensive computed changelist columns without indexes

### 15.3 Safety

- constrain destructive actions
- log administrative operations for sensitive entities

### 15.4 Example: ModelAdmin with actions and read-only fields

```py
from django.contrib import admin

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "status", "created_at", "total"]
    list_select_related = ["customer"]
    list_filter = ["status", "created_at"]
    search_fields = ["customer__email", "id"]
    readonly_fields = ["created_at", "paid_at", "total"]
    actions = ["mark_shipped"]

    @admin.action(description="Mark selected orders as shipped")
    def mark_shipped(self, request, queryset):
        eligible = queryset.filter(status="paid")
        for order in eligible:
            order.ship()  # calls domain method, not raw update
        self.message_user(request, f"Shipped {eligible.count()} orders.")
```

### 15.5 Read-only admin for audit models

```py
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "action", "entity"]
    list_select_related = ["user"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

---

## 17. DRF Bible

DRF API Guide: <https://www.django-rest-framework.org/api-guide/>

### 17.1 DRF is a boundary

- serializers validate input and shape output
- viewsets orchestrate auth + queryset shaping
- models/querysets hold domain rules

### 17.2 Serializers (docs-aligned rules)

- always call `is_valid()` before `.save()`
- prefer `is_valid(raise_exception=True)`
- use `validate_<field>()` and `validate()` for input validation
- map to domain calls in `create()`/`update()` (or override `save()` for non-CRUD)

### 17.3 ViewSets and routers

- `get_queryset()` scopes auth + shapes select/prefetch for serializer needs
- keep viewset methods thin; delegate mutation to domain API

### 17.4 Permissions

- define global defaults
- use object-level permissions where needed

### 17.5 Pagination

- paginate list endpoints by default
- use stable ordering

### 17.6 Filtering

- map filtering to QuerySet methods where possible
- keep complex filter logic out of serializers

### 17.7 Throttling

- throttle unauthenticated endpoints
- throttle expensive endpoints

### 17.8 Versioning

- pick a strategy and stick to it
- version only when you must preserve old clients

### 17.9 Schema / OpenAPI

- keep schema consistent with serializers
- treat schema changes as contract changes

### 17.10 No-DRF equivalents

- Serializer -> Form/ModelForm
- `validated_data` -> `cleaned_data`
- `.save()` -> model method or form `.save()`
- renderer -> `JsonResponse`
