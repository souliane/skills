# Squashing Migrations on Live Databases (Section 7.9)

> Load when an app's migration history has grown long enough to cost you something and databases that already ran it have to keep working.

What follows is what worked for us when we squashed one app's long linear history while several deployed databases were already at its leaf. Django's own guide is the starting point: [Squashing migrations](https://docs.djangoproject.com/en/6.1/topics/migrations/#migration-squashing).

---

## 7.9 Squashing an app's migrations

### 7.9.1 When it is worth it

- Django handles hundreds of migrations without much slowdown, and its docs encourage making them freely. Squash when the history costs something you can measure: test-database setup time, `migrate` time on a fresh install, or old `RunPython` code that imports modules that have since changed or gone.
- Squash one app at a time.

### 7.9.2 Two approaches

| | A: `squashmigrations` with `replaces` | B: a fresh initial migration under a new name |
| --- | --- | --- |
| Releases | Two: the squash next to the old files, then the deletion | One |
| Existing databases | Nothing manual: `migrate` records the squash | A one-time `django_migrations` rewrite on each database, with everything stopped |
| Fits when | You do not control every installation (a reusable app, customer-run deployments) | You control every installation and can stop each one for a short window |
| Result | Django's optimiser output; `RunPython` / `RunSQL` block it unless marked `elidable` | Exactly what `makemigrations` writes for today's models |

#### A. `squashmigrations` with `replaces`

1. `manage.py squashmigrations <app> <leaf>` ([command](https://docs.djangoproject.com/en/6.1/ref/django-admin/#squashmigrations); `--squashed-name` picks the name). If it prints "Manual porting required", copy the listed `RunPython` functions into the new file before the old files can go.
2. Release it with the old files still in place. Each installation's next `migrate` records the squash as applied once all the migrations it replaces are applied; one still part-way through the old chain keeps using the old files.
3. Only after **every** installation has run that `migrate`, in a later release: delete the replaced files, point migrations that depended on them at the squash, and remove `replaces` from it.
4. `manage.py migrate <app> --prune` then deletes the rows of the removed files ([`--prune`](https://docs.djangoproject.com/en/6.1/ref/django-admin/#cmdoption-migrate-prune)). Django refuses to prune while a squash still carries `replaces` for those rows.

Deleting the old files early strands any installation that has not recorded the squash yet: it then tries to apply the squash from the start, over tables that already exist.

#### B. A fresh initial migration under a new name

Generating it:

1. Delete the app's migration files, and any helper module only they import.
2. Search every app, including apps in other repositories, for a dependency on any deleted name (not only the old leaf: a dependency can target an intermediate migration), and remove those dependencies for now. The graph refuses to load with a dependency on a node that has no file (`NodeNotFoundError`), and that includes the new name until its file exists.
3. `manage.py makemigrations <app> --name squashed` writes `0001_squashed.py` with `initial = True` and no `replaces`. If this app and another app have foreign keys to each other, that one file cycles with the other app's migration (`CircularDependencyError`). Generate it in two passes instead, first without the foreign keys to the other app and then with them, which gives `0001_squashed` and `0002_squashed`. The rewrite below then inserts every new name.
4. Point those dependencies at the new migration that creates what they need, e.g. `("<app>", "0001_squashed")`. Dependent apps in other repositories need the same change in the release that picks up the squash.
5. `makemigrations` writes schema only. If old data migrations seeded rows that a fresh database needs, add them back as a `RunPython` with literal values (no imports of app code) and a reverse function.
6. Update `max_migration.txt` if you use `django-linear-migrations`, and delete or rewrite tests that import numbered migration modules or migrate to nodes that no longer exist.

**Use a new name, never `0001_initial`.** Old code meeting a rewritten database looks for its own migration names. With a new name it finds none recorded and stops: at `InconsistentMigrationHistory` when another app's applied migration depends on the old files, otherwise at its first `CreateModel` on an existing table. With `0001_initial` it would read the new row as its own first migration and apply its `0002` onwards on top of the squashed schema. Also check that no new name is an old migration's name; Django's docs raise the same concern about reusing a deleted migration's name (the pruning note under [Squashing migrations](https://docs.djangoproject.com/en/6.1/topics/migrations/#migration-squashing)).

Before touching any existing database, check the migration itself:

- Build one fresh database from the old history and one from the new migration, then compare the schema (tables, columns, constraints, indexes, foreign keys) and the seeded rows. Expect 0 differences, and prove the comparison can fail by making one deliberate change (a default, a dropped index) and watching it report it.
- Compare columns by name and ignore their order. A column added by a later `AddField` sits at the end of a table built from history, while the fresh `CreateModel` follows the model's field order.
- `makemigrations --check` is clean, `migrate <app> zero` followed by `migrate` gives the same database back, and generating the migration twice gives the same file.

### 7.9.3 Rewriting `django_migrations` on an existing database (approach B)

Django's own commands do not fit here. Once another app's applied migration depends on the new name, [`migrate --prune`](https://docs.djangoproject.com/en/6.1/ref/django-admin/#cmdoption-migrate-prune) and [`migrate --fake`](https://docs.djangoproject.com/en/6.1/ref/django-admin/#cmdoption-migrate-fake) both stop with `InconsistentMigrationHistory` against the unrewritten database ([history consistency](https://docs.djangoproject.com/en/6.1/topics/migrations/#history-consistency)). Without such a dependency they work, but as separate writes with no checks in between. So the rewrite is a small script: delete the app's rows and insert the new names as applied, in one transaction.

When the database file lives in a container volume, run the backup, the rewrite and the checks in a one-off container that mounts the volume, as the app's user, rather than copying the file out. The host's `sqlite3` and Python can differ from the image's.

1. **Stop every process that opens the database**: web, workers, schedulers, admin shells, cron jobs, and one-off CLI or management-command processes started by tools or other sessions. Stop supervisors and watchdogs that restart services on their own (restart-always) first, before the services they restart, and hold anything that redeploys.
2. **Back it up online and check the copy.** For SQLite, use the [online backup](https://www.sqlite.org/backup.html) (`sqlite3 db ".backup copy"`) and run [`PRAGMA integrity_check`](https://www.sqlite.org/pragma.html#pragma_integrity_check) and `PRAGMA foreign_key_check` on the copy. For PostgreSQL, [`pg_dump -Fc`](https://www.postgresql.org/docs/current/app-pgdump.html) and a test restore. Keep it outside any backup rotation.
3. **Count the rows and refuse a mismatch.** Pass the expected count explicitly (`expect_rows` below), read it from the backup in this window rather than from an earlier note, and pass the full set of old names (`expect_names`) so a missing name, or one newer than the old leaf, is refused too. An installation with its own local migrations of the app beyond the shared leaf is refused, and rightly: the squash has to cover every migration any installation applied. Merge those migrations into the shared history first, rebuild the squash, and start again.
4. **Diff the live schema against the schema the new migration produces**, as in 7.9.2: columns, indexes and constraints, 0 differences, column order ignored. On a difference, stop. Fix the drift with an ordinary migration on the old history and rebuild the squash, rather than editing the squash to match one database.
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

### 7.9.4 Several installations

- Each installation rewrites its own database, and the rewrite and the switch to the new code happen in the same stopped window for that installation.
- The new code must not reach a database that has not been rewritten, and the old code must not start on one that has. Hold the deploy lock or freeze deploys (including any automatic deploy on merge, or self-update) until that installation's rewrite is done and checked. The new code's `migrate` against an unrewritten database stops at `InconsistentMigrationHistory` or "table already exists": safe, but down.
- The release that carries the squash can merge once every installation's deploy is held. After that, each installation runs 7.9.3 at its own pace.
- When all of them run the new code, compare them: the same migration leaf for the app, and the same schema.

### 7.9.5 Side effects to expect

- Deleting many files can reshuffle duration-based test sharding.
