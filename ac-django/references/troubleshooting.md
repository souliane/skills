# Troubleshooting

> Load when diagnosing common Django errors: migration issues, N+1 queries, on_commit problems.

---

## `makemigrations` Detects No Changes

- **Cause:** Model change not saved, or app not in `INSTALLED_APPS`.
- **Fix:** Verify the app is registered in settings. Check for syntax errors in `models.py`. Run `makemigrations <app_label>` explicitly.

## "Relation Already Exists" During `migrate`

- **Cause:** Database schema is ahead of migration history (common after importing production/dev dumps).
- **Fix:** Use `migrate --fake <app_label> <migration_name>` **only** for the specific migration that matches the existing schema. Never `--fake` blindly.

## N+1 Queries in DRF Serializer

- **Cause:** Serializer accesses related objects without prefetching.
- **Fix:** Add a `for_api()` queryset method with appropriate `select_related()` / `prefetch_related()`. Use it in the viewset's `get_queryset()`. Verify with `assertNumQueries` in tests.

## Removing App from Helper List Also Removes from `INSTALLED_APPS`

- **Cause:** Settings use list unpacking (`INSTALLED_APPS = [... *FIRST_PARTY_APPS ...]`). Removing an app from the helper list also removes it from `INSTALLED_APPS`.
- **Fix:** Before editing any list that feeds into `INSTALLED_APPS`, trace the unpacking chain. If the app must leave the helper list but stay installed, move it to `INSTALLED_APPS` directly.
- **Prevention:** When editing `INSTALLED_APPS`-related lists, always diff the final resolved list before and after: `python -c "from django.conf import settings; print('\n'.join(settings.INSTALLED_APPS))"`.

## `on_commit` Callback Never Fires

- **Cause:** Code is inside a nested `atomic()` block — `on_commit` only fires when the outermost transaction commits.
- **Fix:** Ensure `on_commit` is registered at the right transaction level. See [`transactions-and-migrations.md`](transactions-and-migrations.md) for patterns.
