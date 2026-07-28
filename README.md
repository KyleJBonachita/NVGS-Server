# NVGS Server

NVGS Server is the on-premises foundation for the Robotics Team ticketing
system. It runs the application API and PostgreSQL on one Ubuntu laptop while
keeping PostgreSQL inaccessible from user laptops.

If the technical names below are unfamiliar, start with the
**[simple guide](docs/SIMPLE_GUIDE.md)**. It explains the system as a filing
cabinet, receptionist, and secure front door.

For the Ubuntu installation commands in one file, use
**[START_HERE.md](START_HERE.md)**.

## How we work

```text
Windows laptop -> push code -> GitHub -> pull code -> Ubuntu server
```

- We write and test code on Windows.
- GitHub stores the versioned source code.
- Ubuntu pulls the code and runs the live server.
- Live tickets, passwords, backups, webhook URLs, and the server's `.env` file
  stay off GitHub.

## Current scope

This repository currently provides the backend/server foundation:

- PostgreSQL 17 with a persistent Docker volume
- Django 5.2 LTS API and administration
- Email-based local accounts restricted to approved domains
- Optional signed standalone Apps Script login bridge
- `agent`, `team`, and `system_admin` roles
- End-user Django ticketing dashboard with local and Apps Script login entry
- Ticket creation, assignment, status, priority, resolution, and comments
- Profile editing, filtered CSV export, bulk Team actions, and analytics
- Apps Script-compatible ticket fields, statuses, escalation, downtime, impact,
  root cause, and reopen tracking
- Private internal notes for Tech Team/TL users
- Per-ticket audit events
- Optional queued ticket-activity webhook notifications
- Repeatable CSV import for Users, Tickets, Comments, and StatusHistory exports
- Caddy HTTPS with a local certificate authority
- Database health checks and permission-restricted Docker secret files
- Backup tooling
- Isolated restore verification and encrypted second-copy helpers
- Ubuntu charger, battery, network, Internet, application, lid, and rejected
  login monitoring
- Full-screen Ubuntu warning acknowledgements, recovery notifications, and an
  optional remote webhook
- A desktop launcher that starts the server, alerts, and temporary anti-sleep
  only while its terminal window is open
- An optional permanent always-on Ubuntu mode
- A safe Ubuntu update command that backs up before pulling

It does not contain approved corporate NVIDIA SSO. Local accounts remain
available. The optional Apps Script bridge can reuse the verified Google
Workspace email through a separate domain-restricted login project until
approved corporate SSO is available.

The existing Apps Script login feels automatic because its manifest restricts
access to the Google Workspace domain, runs as the accessing user, and
`Auth.js` reads Google's verified active-user email. A local Django site does
not receive that Google identity automatically. The standalone bridge applies
the same identity mechanism without changing the original ticketing project.

There are three authentication paths:

1. **Local accounts now:** use the NVIDIA email as the username and a separate
   local password.
2. **Approved corporate SSO:** register this Django application with the
   corporate Google/OIDC/SAML identity provider and receive a client ID,
   secret, issuer information, and approved callback address.
3. **Apps Script bridge (implemented, disabled by default):** a small
   domain-restricted standalone Apps Script issues a short-lived signed login
   token containing its verified active email. This retains an Apps Script
   dependency and should be reviewed before production use. See the
   **[bridge setup guide](appscript-bridge/README.md)**.

Accepting a typed `@nvidia.com` address without a password or signed identity
token is not authentication and must not grant access.

The existing Google Apps Script ticketing system is the reference for the
future browser interface. See
[`docs/MIGRATING_APPS_SCRIPT.md`](docs/MIGRATING_APPS_SCRIPT.md).

## Security boundary

```text
Production laptop -> HTTPS 443 -> Caddy -> Django -> PostgreSQL
                                               |
                                      private Docker network
```

Only Caddy publishes a host port. PostgreSQL has no host port mapping. Users,
browser JavaScript, and Python desktop tools must never receive PostgreSQL
credentials.

The default bind address is `127.0.0.1`. The server is therefore local-only
until an administrator deliberately sets `SERVER_BIND_IP` in `.env`.

## Roles

| Role | Purpose |
| --- | --- |
| `agent` | Raise tickets, view own tickets, and add public comments |
| `team` | Shared Tech Team/TL authority over the complete queue |
| `system_admin` | Manage accounts and server configuration |

Managers who need the same queue authority can be assigned `team`. An
`@nvidia.com` address establishes the allowed email domain; it does not grant
elevated rights automatically.

## Ubuntu quick start

Install Docker Engine and the Docker Compose plugin using Docker's official
Ubuntu instructions:

- <https://docs.docker.com/engine/install/ubuntu/>

Then:

```bash
git clone https://github.com/KyleJBonachita/NVGS-Server.git
cd NVGS-Server
chmod +x scripts/*.sh
./scripts/bootstrap-secrets.sh
nano .env
docker compose up -d --build
docker compose exec app python manage.py createsuperuser \
  --email your.name@nvidia.com
docker compose ps
```

Before LAN deployment, keep these values:

```dotenv
SERVER_BIND_IP=127.0.0.1
SERVER_ADDRESS=localhost
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost
```

Open `https://localhost/admin/` on the server. Export and trust the local
certificate authority as described in
[`docs/UBUNTU_DEPLOYMENT.md`](docs/UBUNTU_DEPLOYMENT.md).

Normal users open `https://localhost/`, which sends them to the login page or
the `/tickets/` dashboard. `/api/auth/me/` is a diagnostic API response, not
the user interface.

After exporting `nvgs-local-ca.crt`, install the app-controlled Ubuntu mode:

```bash
sudo ./scripts/install-app-controlled-mode.sh
sudo reboot
```

Open **NVGS Server Control** from Ubuntu Applications after reboot. Press Enter
or close its terminal window when the server is no longer needed. The database
is stopped cleanly and its ticket data remains stored.

Remote notification setup is explained in
[`docs/ALERTS.md`](docs/ALERTS.md). Without a webhook, alerts are still saved in
Ubuntu's local journal.

Ticket-activity notification setup is separate and explained in
[`docs/TICKET_NOTIFICATIONS.md`](docs/TICKET_NOTIFICATIONS.md).

## Activating LAN access

After the Ethernet interface has an assigned static address or DHCP
reservation, edit `.env`. For example only:

```dotenv
SERVER_BIND_IP=10.20.30.20
SERVER_ADDRESS=10.20.30.20
DJANGO_ALLOWED_HOSTS=10.20.30.20
DJANGO_CSRF_TRUSTED_ORIGINS=https://10.20.30.20
```

Apply it:

```bash
docker compose up -d
```

Do not copy the example address. Use the address assigned for the actual
network. A DNS hostname can be used instead of the IP when one is available.

For an authorized temporary DHCP pilot using the desktop controller, enable
automatic refresh once:

```bash
./scripts/refresh-dynamic-lan.sh enp109s0
```

After that, opening **NVGS Server Control** detects the current IPv4 address on
that Ethernet interface before starting Docker and the alert monitors. This
does not make the DHCP address permanent. Without a stable hostname, an address
change also requires updating the Apps Script callback and client bookmark.

To publish a custom mDNS alias without renaming the Ubuntu laptop:

```bash
./scripts/refresh-dynamic-lan.sh enp109s0 ticketing-system.local
```

The controller adds the alias to Ubuntu's local hosts file, publishes it
through Avahi, and configures Caddy to accept both the friendly name and the
current Ethernet IP before Docker starts. Approved client laptops must support
and be allowed to use mDNS. A hostname does not bypass VLAN, firewall, or
client-isolation rules.

## Important endpoints

| Method | Endpoint | Access |
| --- | --- | --- |
| `GET` | `/` | Login/dashboard entry |
| `GET` | `/login/` | Apps Script and local login choices |
| `GET` | `/tickets/` | End-user ticketing dashboard |
| `GET` | `/api/health/` | Health check |
| `GET` | `/api/system-status/` | Safe Team-visible deployment status |
| `GET` | `/api/auth/csrf/` | Obtain browser CSRF token |
| `POST` | `/api/auth/login/` | Local account login |
| `GET` | `/api/auth/appscript/start/` | Start optional Apps Script login |
| `GET, POST` | `/api/auth/appscript/onboarding/` | First-login profile setup |
| `POST` | `/api/auth/logout/` | Authenticated user |
| `GET, PATCH` | `/api/auth/me/` | Current user/profile |
| `GET, POST` | `/api/tickets/` | Role-filtered ticket queue/create |
| `GET, PUT, PATCH` | `/api/tickets/{id}/` | Role-filtered ticket detail |
| `GET, POST` | `/api/tickets/{id}/comments/` | Ticket comments |
| `GET` | `/api/tickets/configuration/` | Existing workflow choices |
| `GET` | `/api/tickets/summary/` | Role-filtered ticket counts |
| `GET` | `/api/tickets/analytics/` | Team analytics |
| `GET` | `/api/tickets/export/` | Team filtered CSV export |
| `POST` | `/api/tickets/bulk-status/` | Team bulk status update |
| `POST` | `/api/tickets/{id}/assign/` | Team assignment |
| `POST` | `/api/tickets/{id}/transition/` | Validated status change |
| `GET` | `/api/tickets/{id}/history/` | Audit/status history |
| `GET` | `/admin/` | System administrators |

Tickets cannot be deleted through the API because their history is an audit
record.

## Backups

Create a PostgreSQL custom-format backup:

```bash
./scripts/backup.sh
```

The resulting file under `backups/` is only the first copy. Copy it to a second
approved, encrypted device. See [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md).

Verify the latest backup without touching production:

```bash
./scripts/verify-backup-restore.sh
```

## Updating Ubuntu after a Windows push

```bash
cd NVGS-Server
./scripts/update-ubuntu-server.sh
```

This backs up PostgreSQL before pulling, rebuilds the application, and refreshes
the selected Ubuntu run mode. In desktop-controller mode, open **NVGS Server
Control** before updating so the database is available for the backup. Stop and
reopen the controller after an update so launcher changes take effect.

Prepare the optional standalone Apps Script login with:

```bash
./scripts/appscript-login-setup.sh prepare
```

Then follow the
**[complete bridge setup guide](appscript-bridge/README.md)**.

The current completion status and remaining external approvals are listed in
[`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md). Run the
synthetic workflow in [`docs/PILOT.md`](docs/PILOT.md) before importing real
tickets.

## Development and tests

The local development configuration uses SQLite so tests do not require Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DJANGO_ENVIRONMENT=test python manage.py test
```

On PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DJANGO_ENVIRONMENT = "test"
python manage.py test
```
