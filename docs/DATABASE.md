# Database design

## Access model

PostgreSQL is intentionally available only on the Compose `database` network.
It is not mapped to a host port.

The Django application uses one restricted application login. End users do not
receive database accounts. Agent and Tech Team/TL/Manager permissions are
enforced by the application and stored on the user record.

Real elevated email accounts are provisioned in Django administration, not
hard-coded in the repository. Tech Team, TL, and Manager users all use the
`team` role; system maintainers use `system_admin`. New Google-verified users
start as `agent`, while an existing role is preserved on later logins.

The Ubuntu Server Hub opens database administration on
`https://localhost:8443/admin/`. Docker binds that maintenance listener only to
the server laptop. The normal LAN site blocks `/admin/`, and the maintenance
page still requires a Django system-administrator password.

## Ticketing tables

- `accounts_user`: approved users and application roles
- `tickets_ticket`: the existing Apps Script ticket fields, state, ownership,
  downtime measurements, resolution, escalation, and impact
- `tickets_ticketcomment`: public replies and internal team notes
- `tickets_ticketevent`: immutable application-generated audit events
- Django authentication, permission, session, and administration tables

Imported tickets retain their original ID, such as:

```text
GRTKT-00042
```

Tickets created only in the new system receive:

```text
NVGS-<creation year>-<six digit database ID>
```

The database stores the exact workflow values used by the existing interface:

- Statuses: Open, Assigned, In Progress, On Hold, Resolved, Closed, Reopened
- Priorities: Urgent, High, Moderate, Low
- Ticket types: Hardware, Software, Network, Environment, Calibration, Data
  Quality, and Others

The server validates allowed status changes. For example, an Open ticket cannot
skip directly to Resolved.

## Other applications

Do not place unrelated QA or robotics data into the ticket tables. Future
applications should receive separate PostgreSQL databases and separate
credentials, even when they run on this same PostgreSQL server. This limits the
damage from an application bug or leaked credential.

Create additional databases only after their schema, owner, backup, and
retention requirements are known.
