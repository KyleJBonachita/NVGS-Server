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

## Ticket visibility

- Agents receive only tickets where they are the reporter.
- Tech Team/TL users receive the complete queue.
- Object lookup uses the same filtered query, so an agent receives `404` for a
  different agent's ticket.
- Agents cannot set assignee, priority, status, or resolution during creation.
- Only Tech Team/TL and system-administrator roles can update tickets.
- Internal comments are omitted from agent responses.
- Ticket deletion is disabled.

## Desktop Python clients

Do not embed a user's password or PostgreSQL password in a packaged executable.
The future desktop-client authentication mechanism should be corporate OIDC
with short-lived tokens. Until that is available, use the browser application
or a reviewed session-login implementation over trusted HTTPS.

