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
- `agent`, `team`, and `system_admin` roles
- Ticket creation, assignment, status, priority, resolution, and comments
- Apps Script-compatible ticket fields, statuses, escalation, downtime, impact,
  root cause, and reopen tracking
- Private internal notes for Tech Team/TL users
- Per-ticket audit events
- Repeatable CSV import for Users, Tickets, Comments, and StatusHistory exports
- Caddy HTTPS with a local certificate authority
- Database health checks and permission-restricted Docker secret files
- Backup tooling
- Ubuntu charger, battery, network, Internet, application, lid, and rejected
  login monitoring
- Ubuntu desktop warning/recovery notifications with optional remote webhook
- A desktop launcher that starts the server, alerts, and temporary anti-sleep
  only while its terminal window is open
- An optional permanent always-on Ubuntu mode
- A safe Ubuntu update command that backs up before pulling

It does not yet contain the end-user browser interface or NVIDIA SSO. Local
accounts are the initial authentication method. Corporate SSO can replace the
login endpoint later without changing the ticket database.

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

## Important endpoints

| Method | Endpoint | Access |
| --- | --- | --- |
| `GET` | `/api/health/` | Health check |
| `GET` | `/api/auth/csrf/` | Obtain browser CSRF token |
| `POST` | `/api/auth/login/` | Local account login |
| `POST` | `/api/auth/logout/` | Authenticated user |
| `GET` | `/api/auth/me/` | Current user |
| `GET, POST` | `/api/tickets/` | Role-filtered ticket queue/create |
| `GET, PUT, PATCH` | `/api/tickets/{id}/` | Role-filtered ticket detail |
| `GET, POST` | `/api/tickets/{id}/comments/` | Ticket comments |
| `GET` | `/api/tickets/configuration/` | Existing workflow choices |
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

## Updating Ubuntu after a Windows push

```bash
cd NVGS-Server
./scripts/update-ubuntu-server.sh
```

This backs up PostgreSQL before pulling, rebuilds the application, and refreshes
the selected Ubuntu run mode. In desktop-controller mode, open **NVGS Server
Control** before updating so the database is available for the backup.

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
