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

The included command creates an isolated PostgreSQL container with no published
port, restores the latest backup, checks user/ticket/comment counts, writes a
PASS report, and removes the temporary container:

```bash
./scripts/verify-backup-restore.sh
```

Select a specific backup when needed:

```bash
./scripts/verify-backup-restore.sh backups/SELECTED_BACKUP.dump
```

Reports are saved under `backups/restore-verifications/`.

## Encrypted second copy

Attach an approved second storage device and use its mounted folder:

```bash
./scripts/copy-backup-encrypted.sh /media/YOUR_APPROVED_DEVICE/NVGS
```

The helper uses GnuPG symmetric AES-256 encryption. Use a unique passphrase
stored in the approved password manager. The helper refuses to call a folder
inside this project a second backup.

## Google Drive on Ubuntu

Google does not provide Drive for desktop on Linux. Its official guidance is
to use Drive in the browser:

<https://support.google.com/drive/answer/2375082>

Third-party tools can mount or copy to Drive, but a work account and production
ticket data require approval before authorizing one. If an approved Drive
upload is later added, upload only completed encrypted `.dump.gpg` backup
files. Never sync PostgreSQL's live Docker volume or active database files.
Deletion/conflict synchronization is not a replacement for tested backup
retention.

Production restoration should be performed during an announced maintenance
window after taking one final backup of the current state.
