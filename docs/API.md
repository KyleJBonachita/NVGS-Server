# API notes

The initial API uses secure Django session cookies. It is suitable for a
same-origin browser interface served through Caddy.

## Browser login flow

1. `GET /api/auth/csrf/`
2. Read the `csrftoken` cookie or returned `csrf_token`.
3. `POST /api/auth/login/` with the `X-CSRFToken` header.
4. Keep the returned session cookie.
5. Include `X-CSRFToken` on subsequent state-changing requests.

Example login body:

```json
{
  "email": "person@nvidia.com",
  "password": "user-entered-password"
}
```

The login endpoint is rate-limited. Self-registration and automatic elevated
rights based only on email domain are intentionally unavailable.

## Optional Apps Script login

When the signed bridge is enabled, begin at:

```text
GET /api/auth/appscript/start/
```

The browser visits the standalone domain-restricted Apps Script bridge, which
reads Google's active-user email and returns a 60-second signed assertion.
Django checks the signature, browser-bound state, expiry, issuer, audience, and
email domain before creating a session.

New verified accounts are created only as `agent`. Existing roles are
preserved, and disabled accounts remain blocked. Team and administrator access
must still be assigned by a system administrator. See
[`../appscript-bridge/README.md`](../appscript-bridge/README.md).

First-time verified users are redirected to
`/api/auth/appscript/onboarding/`. They must enter their name and create a
separate local NVGS password before Django activates the authenticated session.
The signed callback uses its HMAC signature and one-time browser state as its
login-CSRF protection; the onboarding form retains normal Django CSRF
protection.

## Ticket visibility

- Agents receive only tickets where they are the requester or creator.
- Tech Team/TL/Manager users receive the complete queue.
- Object lookup uses the same filtered query, so an agent receives `404` for a
  different agent's ticket.
- Agents may select ticket priority, type, impact, workstation, and location
  while creating a ticket. They cannot set assignee, status, resolution,
  escalation, or server-calculated counters.
- Only Tech Team/TL/Manager and system-administrator roles can update tickets.
- Internal comments are omitted from agent responses.
- Ticket deletion is disabled.

## Ticket workflow endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/tickets/configuration/` | Existing priorities, types, statuses, and transitions |
| `GET` | `/api/auth/users/assignable/` | Active team assignees |
| `GET` | `/api/auth/users/` | Active users for team-created tickets |
| `POST` | `/api/tickets/{id}/assign/` | Assign to a team account |
| `POST` | `/api/tickets/{id}/assign-to-me/` | Team member self-assignment |
| `POST` | `/api/tickets/{id}/transition/` | Validated status change |
| `POST` | `/api/tickets/{id}/escalate/` | Record escalation |
| `GET` | `/api/tickets/{id}/history/` | Audit/status history |
| `GET, POST` | `/api/tickets/{id}/comments/` | Comments and internal notes |
| `POST` | `/api/tickets/bulk-status/` | Update up to 50 tickets |

Imported tickets return their original `GRTKT-` value as `ticket_id`. New
tickets use an `NVGS-` reference.

## Desktop Python clients

Do not embed a user's password or PostgreSQL password in a packaged executable.
The future desktop-client authentication mechanism should be corporate OIDC
with short-lived tokens. Until that is available, use the browser application
or a reviewed session-login implementation over trusted HTTPS.
