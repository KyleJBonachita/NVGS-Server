# Backup and restore

## Backup policy

`scripts/backup.sh` creates a PostgreSQL custom-format dump in `backups/`.
The dump is compressed but is not independently encrypted. It contains
sensitive application data and must remain on an encrypted disk or be encrypted
before it is copied elsewhere.

Recommended starting schedule:

- Run a backup every night.
- Copy the successful backup to a second approved encrypted device.
- Retain at least 14 daily copies initially.
- Perform a test restore monthly.
- Record who tested the restore and when.

A backup stored only on the server laptop is not a backup against laptop theft,
SSD failure, or accidental volume deletion.

## Creating a backup

```bash
./scripts/backup.sh
```

Check that the file is non-empty:

```bash
ls -lh backups/
```

## Restore test

A restore replaces or adds database data and must not be tested against the
production database. Use a separate PostgreSQL container or an isolated test
machine.

Example isolated validation:

```bash
docker run --name nvgs-restore-test \
  -e POSTGRES_PASSWORD=temporary-test-password \
  -e POSTGRES_DB=nvgs_restore_test \
  -d postgres:17.10-bookworm
```

Wait for PostgreSQL to become ready, copy the selected dump, and restore it:

```bash
docker cp backups/SELECTED_BACKUP.dump \
  nvgs-restore-test:/tmp/restore.dump

docker exec nvgs-restore-test pg_restore \
  --username postgres \
  --dbname nvgs_restore_test \
  --clean \
  --if-exists \
  /tmp/restore.dump
```

Inspect table counts and representative tickets before declaring the backup
valid. Remove the isolated test container only after the validation is
complete.

Production restoration should be performed during an announced maintenance
window after taking one final backup of the current state.
