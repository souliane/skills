# Testing Bible and Tooling (Sections 18–19)

> Load when writing tests, setting up CI, or configuring linting.

---

## 18. Testing Bible

### 18.1 House defaults

- DB tests: `django.test.TestCase`
- Shared setup: `setUpTestData()`
- Time mocking: `time_machine`
- Parametrization: `unittest_parametrize`

### 18.2 Factory Boy: explicitness + traits

Non-negotiables:

- don't rely on factory defaults in tests
- default output includes only required fields
- nullable/optional fields are behind traits
- prefer `build()` unless persistence is required

Trait pattern:

```py
import factory
from factory.django import DjangoModelFactory

class UserFactory(DjangoModelFactory):
    class Meta:
        model = "accounts.User"

    email = factory.Sequence(lambda n: f"user{n}@example.com")

    class Params:
        is_admin = factory.Trait(is_staff=True, is_superuser=True)
        with_phone = factory.Trait(phone_number=factory.Faker("phone_number"))
```

### 18.3 Query-count regression tests

When performance matters:

- pick a hot endpoint
- assert query counts don't regress into N+1

### 18.4 DRF tests

- permissions
- response shapes
- pagination contracts
- query shaping correctness

---

## 19. Tooling & DX enforcement

### 19.1 `pyproject.toml` only

- package manager: **uv**
- lint: **ruff**
- formatting: **ruff format**
- pre-commit includes `django-upgrade`

### 19.2 CI safety rails

- run tests
- enforce migration rules (linear + pending migrations)
- enforce formatting/lint
