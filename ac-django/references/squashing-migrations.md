# Squashing Migrations on Live Databases (Section 7.9)

> Load when an app's migration history has grown long enough to cost you something and databases that already ran it have to keep working.

What follows is what worked for us when we squashed one app's long linear history while several deployed databases were already at its leaf, plus what a few large projects have published about doing the same. Django's own guide is the starting point: [Squashing migrations](https://docs.djangoproject.com/en/6.1/topics/migrations/#migration-squashing).

---

## 7.9 Squashing an app's migrations

### 7.9.1 When it is worth it

- Django copes with long histories, and its docs encourage making migrations freely, but the cost grows with them: one large project measured about 2,500 migrations taking about 20 minutes to build a fresh database, about 90% of it spent rebuilding migration state ([PostHog #91646](https://github.com/PostHog/posthog/pull/91646)). Squash when the history costs something you can measure: test-database setup, `migrate` on a fresh install, or old `RunPython` code that imports modules that have since changed or gone.
- If only test setup hurts, try the cheaper options first: [`TEST["MIGRATE"] = False`](https://docs.djangoproject.com/en/6.1/ref/settings/#migrate), `MIGRATION_MODULES = {"<app>": None}` for one app, or `test --keepdb`. Either way, keep one CI job that runs every migration from an empty database.
- Squash one app at a time, up to an older point that every installation has already passed rather than today's leaf. GitLab squashes up to two required stops back ([migration squashing](https://docs.gitlab.com/development/database/migration_squashing/)). Rebase open branches that add migrations to the app once the squash lands.
- Finish any in-flight two-step delete first (a field already removed from the models, waiting for the migration that drops its column). Regenerating from the models loses the pending step ([Sentry #121291](https://github.com/getsentry/sentry/pull/121291)).

### 7.9.2 Three approaches

| | Hybrid: regenerate, keep `replaces` (default) | A: `squashmigrations` | B: no `replaces` (fallback) |
| --- | --- | --- | --- |
| Releases | Two: the squash with the old files deleted, then dropping `replaces` | Two: the squash next to the old files, then the deletion | One |
| Existing databases | `migrate` records the squash once every replaced row is there. A database part-way through them must upgrade through the last release with the old files first, and you enforce that (7.9.3) | The same, but a part-way database keeps using the old files until the deletion | A one-time `django_migrations` rewrite on each database, with everything stopped (7.9.5) |
| Back to the old code | No database work: its rows are still there | No database work | Restore the backup or reverse the rewrite |
| Result | What `makemigrations` writes for the models at the cut point | Django's optimiser output; `RunPython` / `RunSQL` block it unless marked `elidable` | What `makemigrations` writes for today's models |
| Fits when | By default | Part-way installations you do not control (a reusable app) have to upgrade straight through | `replaces` cannot be used, e.g. a squash that already shipped without it |

#### Hybrid: regenerate, then add `replaces`

1. In a checkout of the cut point (the current tree if you cut at today's leaf), delete the app's migration files and any helper module only they import. Temporarily drop other apps' dependencies on them, or the graph refuses to load (`NodeNotFoundError`).
2. `manage.py makemigrations <app> --name squashed_<NNNN>`, where `<NNNN>` is the number of the last replaced migration. It writes `0001_squashed_<NNNN>.py` with `initial = True`. If this app and another app have foreign keys to each other, that one file cycles with the other app's migration (`CircularDependencyError`); generate it in two passes, first without the foreign keys to the other app and then with them.
3. Copy the file into the current tree, delete the replaced files there, and add `replaces = [("<app>", "<old name>"), ...]` listing every one of them.
4. Point dependencies on the replaced names at the new file, in every app and repository. While `replaces` lists a name, a dependency on it still resolves to the squash, so another repository can follow in its own release, as long as it does so before step 7.
5. Carry forward what `makemigrations` leaves out and check the result (7.9.4). Ship it with the gate (7.9.3).
6. Wait until every database, on every alias, has a row for the squash.
7. In a later release, drop `replaces` and run `manage.py migrate <app> --prune` to delete the old rows ([`--prune`](https://docs.djangoproject.com/en/6.1/ref/django-admin/#cmdoption-migrate-prune)). Django refuses `--prune` while `replaces` is still there.

Django matches `replaces` against the rows in `django_migrations`, not against files on disk ([Sentry #121207](https://github.com/getsentry/sentry/pull/121207), [`django-nextgensquash`](https://github.com/PostHog/django-nextgensquash)). In `MigrationLoader.build_graph`, a squash whose replaced rows are all recorded counts as applied; `MigrationExecutor.check_replacements` then records its row on the next plain `migrate`, and the history check accepts migrations that depend on it. A fresh database applies the squash and records the old names too. The old code, after a rollback, finds its own rows and nothing to do.

A database part-way through the replaced range is the case to stop. Django removes the squash from the graph (`MigrationGraph.remove_replacement_node`) and falls back on the replaced files, which are gone: the app shows "(no migrations)" and migrations that depended on the squash lose that parent. On a toy project nothing was written, but how loudly it failed varied:

- With no other app depending on it, `migrate` exited 0 with "No migrations to apply", and `migrate --check` and `makemigrations --check` were clean, while a column was missing.
- With a dependent migration pointed at the squash and already applied, `migrate` failed (`ValueError` while rendering the state), yet `migrate --check` exited 0.
- With a dependent still pointing at an old name, loading the graph failed with a `NodeNotFoundError` that names the squash.

So deleting the old files early is safe only with `replaces` kept and the gate in place. Once `replaces` is gone too, a database without the squash row stops at `InconsistentMigrationHistory`, or applies the squash from the start over tables that already exist.

**Naming.** `makemigrations` numbers the next migration from the app's leaf with `MigrationAutodetector.parse_number`, which takes the number after `_squashed_` when there is one and the leading number otherwise. `0001_squashed_0127` gives 127, so the next migration is `0128_...` and cannot take an old name. `0001_squashed` gives 1, so numbering restarts at `0002` among the old names. A later migration that takes a replaced name exactly makes the graph cyclic (`CircularDependencyError`) for as long as `replaces` lists it. `squashmigrations --squashed-name squashed_<NNNN>` gives the same `0001_squashed_<NNNN>`.

#### A. `squashmigrations`

1. `manage.py squashmigrations <app> <leaf> --squashed-name squashed_<NNNN>` ([command](https://docs.djangoproject.com/en/6.1/ref/django-admin/#squashmigrations)). If it prints "Manual porting required", copy the listed `RunPython` functions into the new file before the old files can go. It does not carry `atomic = False` over, so an operation that needs it (PostgreSQL `CONCURRENTLY`) goes into a migration of its own.
2. Release it with the old files still in place. Each installation's next `migrate` records the squash once all the migrations it replaces are applied; one still part-way through the old chain keeps using the old files.
3. Only after **every** installation has a row for the squash, in a later release: delete the replaced files, point migrations that depended on them at the squash, and remove `replaces` from it. Then `migrate <app> --prune`.

Mark one-off data migrations `elidable=True` when you write them, so a later squash can drop them. A squash can itself be squashed before its `replaces` is removed ([release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/#migrations)).

#### B. No `replaces` (fallback)

Generate it as in the hybrid's steps 1 and 2, delete the old files, and skip `replaces`. Dependencies on the old names then have to move to the new file in the same release, since nothing resolves them any more.

**Use a new name, never `0001_initial`.** Old code meeting a rewritten database looks for its own migration names. With a new name it finds none recorded and stops: at `InconsistentMigrationHistory` when another app's applied migration depends on the old files, otherwise at its first `CreateModel` on an existing table. With `0001_initial` it would read the new row as its own first migration and apply its `0002` onwards on top of the squashed schema. Also check that no new name is an old migration's name; Django's docs raise the same concern about reusing a deleted migration's name (the pruning note under [Squashing migrations](https://docs.djangoproject.com/en/6.1/topics/migrations/#migration-squashing)).

### 7.9.3 Refusing a part-way database before `migrate`

- Before `migrate` runs, compare each database's rows with the squash. Refuse one that has some but not all of the replaced names (once `replaces` is gone: rows for the app but none for the squash), and print the release to upgrade through first. `migrate --check` does not catch this (7.9.2).
- Put the check where every deploy passes, such as a wrapper or an override of the `migrate` command. GitLab raises before `db:migrate` and names the version to upgrade to ([`schema_check.rake`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/tasks/migrate/schema_check.rake), [required stops](https://docs.gitlab.com/development/database/required_stops/)). PostHog proposes the same check in its `migrate` command, with exit code 78 so that its deploy script does not retry ([PostHog #110128](https://github.com/PostHog/posthog/pull/110128)). Self-hosted Sentry publishes its [hard stops](https://develop.sentry.dev/self-hosted/releases/#hard-stops).

### 7.9.4 What `makemigrations` leaves out, and checking the result

- `makemigrations` writes model state only. List every `RunSQL`, `RunPython`, `SeparateDatabaseAndState` and `django.contrib.postgres.operations` operation in the replaced files, and carry forward what a fresh database needs: extensions, triggers, functions, views, raw-SQL indexes, role or database settings, and the database side of each `SeparateDatabaseAndState`. Seed data goes back as a `RunPython` with literal values (no imports of app code) and a reverse function.
- Update `max_migration.txt` if you use `django-linear-migrations`, and delete or rewrite tests that import numbered migration modules or migrate to nodes that no longer exist.
- Build one fresh database from the old history and one from the new tree, then compare the schema (tables, columns, constraints, indexes, foreign keys) and the seeded rows. Expect 0 differences, and prove the comparison can fail by making one deliberate change (a default, a dropped index) and watching it report it.
- Compare columns by name and ignore their order. A column added by a later `AddField` sits at the end of a table built from history, while the fresh `CreateModel` follows the model's field order. On PostgreSQL, diff a normalised `pg_dump --schema-only`: drop comments and `SET` lines, and normalise auto-generated constraint and index names, which can differ between the two builds.
- `makemigrations --check` is clean, `migrate <app> zero` followed by `migrate` gives the same database back, and generating the migration twice gives the same file.

### 7.9.5 Rewriting `django_migrations` on an existing database (approach B)

Without `replaces`, Django's own commands do not fit here. Once another app's applied migration depends on the new name, [`migrate --prune`](https://docs.djangoproject.com/en/6.1/ref/django-admin/#cmdoption-migrate-prune) and [`migrate --fake`](https://docs.djangoproject.com/en/6.1/ref/django-admin/#cmdoption-migrate-fake) both stop with `InconsistentMigrationHistory` against the unrewritten database ([history consistency](https://docs.djangoproject.com/en/6.1/topics/migrations/#history-consistency)). Without such a dependency they work, but as separate writes with no checks in between. So the rewrite is a small script: delete the app's rows and insert the new names as applied, in one transaction.

When the database file lives in a container volume, run the backup, the rewrite and the checks in a one-off container that mounts the volume, as the app's user, rather than copying the file out. The host's `sqlite3` and Python can differ from the image's.

1. **Stop every process that opens the database**: web, workers, schedulers, admin shells, cron jobs, and one-off CLI or management-command processes started by tools or other sessions. Stop supervisors and watchdogs that restart services on their own (restart-always) first, before the services they restart, and hold anything that redeploys.
2. **Back it up online and check the copy.** For SQLite, use the [online backup](https://www.sqlite.org/backup.html) (`sqlite3 db ".backup copy"`) and run [`PRAGMA integrity_check`](https://www.sqlite.org/pragma.html#pragma_integrity_check) and `PRAGMA foreign_key_check` on the copy. For PostgreSQL, [`pg_dump -Fc`](https://www.postgresql.org/docs/current/app-pgdump.html) and a test restore. Keep it outside any backup rotation.
3. **Count the rows and refuse a mismatch.** Pass the expected count explicitly (`expect_rows` below), read it from the backup in this window rather than from an earlier note, and pass the full set of old names (`expect_names`) so a missing name, or one newer than the old leaf, is refused too. An installation with its own local migrations of the app beyond the shared leaf is refused, and rightly: the squash has to cover every migration any installation applied. Merge those migrations into the shared history first, rebuild the squash, and start again.
4. **Diff the live schema against the schema the new migration produces**, as in 7.9.4: columns, indexes and constraints, 0 differences, column order ignored. On a difference, stop. Fix the drift with an ordinary migration on the old history and rebuild the squash, rather than editing the squash to match one database. On a large PostgreSQL table, do not fix a type drift with a plain `AlterField`: changing a column's type usually rewrites the whole table under an `ACCESS EXCLUSIVE` lock ([`ALTER TABLE`](https://www.postgresql.org/docs/current/sql-altertable.html)).
5. **Rehearse the whole procedure on a copy of the backup**: the rewrite, the checks with the new code, and the rollback.
6. **Rewrite in one transaction**, writing the rows to a rollback file before deleting them:

   ```python
   import os
   import sqlite3
   from pathlib import Path


   class RewriteRefused(Exception):
       pass


   def rewrite_migration_rows(
       db: Path, app: str, new_names: list[str], *, expect_rows: int, expect_names: set[str], rollback_file: Path
   ) -> None:
       conn = sqlite3.connect(db, autocommit=True)
       try:
           conn.execute("BEGIN IMMEDIATE")
           rows = conn.execute(
               "SELECT id, app, name, applied FROM django_migrations WHERE app = ? ORDER BY id", (app,)
           ).fetchall()
           names = {name for _, _, name, _ in rows}
           if present := names & set(new_names):
               raise RewriteRefused(f"{sorted(present)} already present for {app!r}")
           if len(rows) != expect_rows or names != expect_names:
               raise RewriteRefused(
                   f"{len(rows)} rows for {app!r}, expected {expect_rows}; "
                   f"missing {sorted(expect_names - names)}, unexpected {sorted(names - expect_names)}"
               )

           with os.fdopen(os.open(rollback_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as fh:
               fh.writelines("\t".join(map(str, row)) + "\n" for row in rows)
               fh.flush()
               os.fsync(fh.fileno())

           deleted = conn.execute("DELETE FROM django_migrations WHERE app = ?", (app,)).rowcount
           conn.executemany(
               "INSERT INTO django_migrations (app, name, applied) VALUES (?, ?, CURRENT_TIMESTAMP)",
               [(app, name) for name in new_names],
           )
           after = sorted(name for (name,) in conn.execute("SELECT name FROM django_migrations WHERE app = ?", (app,)))
           if deleted != expect_rows or after != sorted(new_names):
               raise RewriteRefused(f"unexpected result: deleted {deleted}, now {after}")
           conn.execute("COMMIT")
       finally:
           if conn.in_transaction:
               conn.execute("ROLLBACK")
           conn.close()
   ```

   `autocommit=` needs Python 3.12+; on older versions pass `isolation_level=None` instead. On PostgreSQL the same shape is `BEGIN; LOCK TABLE django_migrations IN EXCLUSIVE MODE; ... COMMIT;`. Rows of other apps are never touched.
7. **Check with the new code before starting it**: `migrate --plan` prints "No planned migration operations.", [`migrate --check`](https://docs.djangoproject.com/en/6.1/ref/django-admin/#cmdoption-migrate-check) exits 0, and [`makemigrations --check`](https://docs.djangoproject.com/en/6.1/ref/django-admin/#cmdoption-makemigrations-check) is clean. Then start it.
8. **Never run the old code's `migrate` against a rewritten database.** Plain `migrate` stopped before changing anything in our tests (`InconsistentMigrationHistory`, or "table already exists"), but that is luck, not a guarantee. On SQLite, the old code's `migrate --fake-initial` faked its first migration, re-ran its `AddField` migrations, and the table rebuild reset the existing values of those columns to their defaults.
9. **Rollback**: stop everything again, then either restore the backup (anything written since is lost) or, right after a failed start, delete the new rows and re-insert the saved rows with their original ids in one transaction. Then go back to the old code. With SQLite, remove any leftover `-journal`, `-wal` or `-shm` file before putting the backup in place.

### 7.9.6 Several installations and database aliases

- With several database aliases, each alias has its own `django_migrations` rows for every app, even where a router keeps the app's tables off that alias. Run the gate, the counts and any rewrite once per alias.
- Approach B only: each installation rewrites its own database, and the rewrite and the switch to the new code happen in the same stopped window for that installation. The new code must not reach a database that has not been rewritten, and the old code must not start on one that has. Hold the deploy lock or freeze deploys (including any automatic deploy on merge, or self-update) until that installation's rewrite is done and checked. The new code's `migrate` against an unrewritten database stops at `InconsistentMigrationHistory` or "table already exists": safe, but down. The release that carries the squash can merge once every installation's deploy is held; after that, each installation runs 7.9.5 at its own pace.
- When all of them run the new code, compare them: the same migration leaf for the app, and the same schema.

### 7.9.7 Afterwards

- Keep a CI job that checks the squash still matches the history: on every pull request that touches migrations, regenerate the squash and compare the schema it builds with the one the migrations build. Sentry runs one ([Sentry #121207](https://github.com/getsentry/sentry/pull/121207)).
- Deleting many files can reshuffle duration-based test sharding.
