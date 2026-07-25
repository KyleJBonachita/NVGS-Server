# NVGS Server: simple guide

## The four main pieces

Think of the system like a small office:

- **PostgreSQL** is the locked filing cabinet containing tickets.
- **Django** is the receptionist. It checks who the user is and what they may
  read or change.
- **Caddy** is the secure front door. Users enter through HTTPS.
- **Docker Compose** is the start/stop control for all three pieces.

User laptops never open the filing cabinet directly. They speak to the
receptionist through the secure front door.

## Where we do each job

### Windows development laptop

This is where we:

1. Edit code.
2. Run automated tests.
3. Commit the change.
4. Push it to GitHub.

### GitHub

GitHub is the shared, versioned copy of the code. It does not hold the live
ticket database, passwords, or server IP configuration.

### Ubuntu server laptop

This is where we:

1. Pull code from GitHub.
2. Build/restart the server.
3. Store live ticket data.
4. Run backups, anti-sleep, and alerts.

Do not edit tracked source files directly on Ubuntu. Otherwise a later pull can
conflict with the Windows version.

## First Ubuntu installation

Follow [`UBUNTU_DEPLOYMENT.md`](UBUNTU_DEPLOYMENT.md). In short:

```bash
git clone https://github.com/KyleJBonachita/NVGS-Server.git
cd NVGS-Server
chmod +x scripts/*.sh
./scripts/bootstrap-secrets.sh
nano .env
docker compose up -d --build
docker compose exec app python manage.py createsuperuser \
  --email your.name@nvidia.com
docker compose cp \
  caddy:/data/caddy/pki/authorities/local/root.crt \
  ./nvgs-local-ca.crt
sudo ./scripts/install-ubuntu-host.sh
```

The first start should use `127.0.0.1`. Change to the assigned LAN address only
after the local test works.

## Normal update after we push from Windows

On Ubuntu:

```bash
cd NVGS-Server
./scripts/update-ubuntu-server.sh
```

That one command:

1. Makes a database backup.
2. Pulls the new GitHub commit.
3. Downloads updated server components.
4. Rebuilds and restarts the application.
5. Refreshes alerts and anti-sleep settings.

It stops before pulling if somebody edited tracked source files on Ubuntu.

## What the monitor checks

- Charger connected
- Battery percentage
- Ethernet or selected network link
- Internet connection
- Ticket application and database health
- Laptop lid open/closed
- Rejected Ubuntu login attempts

View alerts:

```bash
journalctl -u nvgs-monitor.service -f
```

```bash
journalctl -u nvgs-auth-monitor.service -f
```

Without a webhook, alerts are recorded only on the Ubuntu laptop. With an
approved webhook in `/etc/nvgs-monitor.env`, the monitor also attempts to send
them remotely.

See [`ALERTS.md`](ALERTS.md) for the short webhook setup and test commands.

If the laptop loses its only network connection, it cannot send through that
connection. It records the event locally and sends a recovery alert after the
connection returns. Immediate outage notification requires a second connection
or another device monitoring this server.

## Anti-sleep

The Ubuntu setup:

- Ignores lid closure.
- Ignores idle-sleep requests.
- Blocks suspend, hibernate, and hybrid sleep targets.

It does not block a proper shutdown or reboot.

## Things GitHub must never contain

- `.env`
- Database dumps
- PostgreSQL passwords
- Django secret key
- Webhook URLs
- Corporate identity secrets
- Real ticket exports
- Anything in `imports/`, `local-backups/`, or `appscript-ticketing-system/`

The repository ignores the relevant local files, but always inspect
`git status` before committing.
