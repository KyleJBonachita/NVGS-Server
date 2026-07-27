# Moving the existing Apps Script ticketing system

The first Django browser interface is now implemented at `/tickets/`. It keeps
the important agent and Team workflow while using the local API/database:
ticket creation, personal/complete queues, assignment, valid status changes,
resolution, escalation, comments, internal notes, and audit history.

The unbacked `appscript-ticketing-system/` folder remains excluded from Git and
was used only as a read-only interface/workflow reference.

The current Google Apps Script system is useful because it already tells us:

- Which ticket fields agents use
- Which screens Tech Team and TLs need
- What categories and statuses exist
- How the existing workflow behaves

We should reuse that knowledge instead of inventing a second workflow.

## What will change

Today the existing interface probably follows this path:

```text
Browser -> Google Apps Script -> Google Sheet
```

The local version will follow:

```text
Browser -> NVGS HTTPS API -> PostgreSQL
```

The visible HTML, CSS, and JavaScript may be reusable. Calls such as
`google.script.run` will need to become normal web requests using `fetch()`.

## What we found in the existing system

The local source was inspected without changing it. It already has:

- A complete browser interface in `Index.html`
- Agent, Tech Team, and Management roles
- Ticket creation, assignment, transfer, status changes, resolution, close,
  reopen, escalation, comments, internal notes, bulk updates, and export
- Agent and operations dashboards
- Downtime, trend, and workstation-health reports
- Power Automate/Teams notification queues
- Users, Tickets, Comments, StatusHistory, Settings, ShiftLog, and queue sheets

Tech Team and Management have the same ticket authority in its permission
matrix. The local server represents both with the `team` role. System
administrators additionally manage accounts and server settings.

The original folder and the local safety backup are ignored by Git. Do not
remove these ignore rules. A backup on the same Windows laptop is useful for
accidental edits, but it is not a complete disaster-recovery backup; keep
another approved encrypted copy.

See [`APPS_SCRIPT_FIELD_MAP.md`](APPS_SCRIPT_FIELD_MAP.md) for the exact mapping.

## Safe migration order

1. Keep the original Apps Script folder unchanged.
2. Match its fields and status rules in PostgreSQL. **Implemented.**
3. Test CSV import using fake data. **Implemented.**
4. Copy the interface into the NVGS Server only after the original has a second
   approved backup.
5. Replace the single `google.script.run` bridge with HTTPS `fetch()` calls.
6. Test every action using fake users and tickets.
7. Export the real Sheets and perform a dry-run import.
8. Import into a temporary database and compare row counts and sample tickets.
9. Ask a small Tech Team/TL/Manager group to test.
10. Perform the final export, import, and switch users to the local URL.
11. Keep the old Sheet read-only for an agreed period.

Do not make both systems writable for a long period. Two writable databases will
eventually disagree about the correct ticket status.

## Authentication

The server supports administrator-created local accounts. It also has an
optional signed bridge that reuses the verified active-user email from the
standalone domain-restricted Apps Script project. It does not modify the
original ticketing system. See
[`../appscript-bridge/README.md`](../appscript-bridge/README.md).

The bridge is not the same as a corporate NVIDIA SSO registration: it still
depends on Apps Script and a shared secret. Approved corporate OIDC or SAML can
replace it later without changing the ticket database.

Checking only that text ends in `@nvidia.com` is not authentication. The user
must prove ownership through a password managed by this server or through
corporate SSO.

## Importing Sheet exports

Export these tabs as separate CSV files:

- `Users`
- `Tickets`
- `Comments`
- `StatusHistory`

On Ubuntu, place the CSV files in the ignored `imports/` directory:

```bash
mkdir -p imports
```

That directory is mounted read-only inside the application container and is
excluded from Git. First validate the files without saving:

```bash
docker compose exec app python manage.py import_appscript_csv \
  --users /imports/Users.csv \
  --tickets /imports/Tickets.csv \
  --comments /imports/Comments.csv \
  --history /imports/StatusHistory.csv \
  --dry-run
```

Remove `--dry-run` only after validation succeeds and a database backup exists.
The importer is repeatable: rows with the same Apps Script IDs are updated
rather than duplicated.

Imported accounts have no usable local password until a system administrator
sets one. This prevents an imported email address from silently becoming a
login credential. Delete the CSV files from `imports/` after the migration and
verification are complete; they contain production information.
