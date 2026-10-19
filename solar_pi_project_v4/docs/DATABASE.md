# Database

## Location
Default: `solar_measurements.db` next to the working directory. Overridable via
the `db_location` setting.

## Format
SQLite, WAL mode, `synchronous=NORMAL`, `foreign_keys=ON`. Schema version in
`PRAGMA user_version`. Parameterized SQL only.

## Tables
`sessions`, `measurements`, `integration_state`, `settings`.

## Backup / restore
`database.backup.backup` / `restore` — never overwrite silently; restore verifies
the result is a valid SQLite database.