# Database design

## Access model

PostgreSQL is intentionally available only on the Compose `database` network.
It is not mapped to a host port.

The Django application uses one restricted application login. End users do not
receive database accounts. Agent and Tech Team/TL permissions are enforced by
the application and stored on the user record.

## Initial tables

- `accounts_user`: approved users and application roles
- `tickets_ticket`: ticket state and ownership
- `tickets_ticketcomment`: public replies and internal team notes
- `tickets_ticketevent`: immutable application-generated audit events
- Django authentication, permission, session, and administration tables

Ticket references are presented as:

```text
NVGS-<creation year>-<six digit database ID>
```

For example:

```text
NVGS-2026-000042
```

## Other applications

Do not place unrelated QA or robotics data into the ticket tables. Future
applications should receive separate PostgreSQL databases and separate
credentials, even when they run on this same PostgreSQL server. This limits the
damage from an application bug or leaked credential.

Create additional databases only after their schema, owner, backup, and
retention requirements are known.

