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
sudo ./scripts/install-app-controlled-mode.sh
sudo reboot
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
5. Refreshes the selected server mode.

It stops before pulling if somebody edited tracked source files on Ubuntu.
When using the desktop controller, open it before running the update so the
database is available for the backup.

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

Alerts appear as Ubuntu desktop notifications and are recorded in the local
journal. With an approved webhook in `/etc/nvgs-monitor.env`, the monitor also
attempts to send them remotely.

See [`ALERTS.md`](ALERTS.md) for the short webhook setup and test commands.

If the laptop loses its only network connection, it cannot send through that
connection. It records the event locally and sends a recovery alert after the
connection returns. Immediate outage notification requires a second connection
or another device monitoring this server.

## Starting and stopping NVGS

Open Ubuntu Applications, select **NVGS Server Hub**, and choose **NVGS
Server**. While its control terminal remains open:

- The ticket website and database are running.
- Charger, network, application, lid, and rejected-login alerts are running.
- A warning opens a red full-screen acknowledgement on the server laptop.
- Sleep, hibernate, idle sleep, and lid-close suspension are blocked.

Press Enter or close that window to stop NVGS. The database closes cleanly,
ticket data remains stored, and Ubuntu returns to its normal sleep behavior.

Locking the screen with `Super+L` leaves the controller, server, alerts, and
anti-sleep running. Do not log out while NVGS is running. Ubuntu may hide
notification details while locked, but the journal and webhook continue.

To share files instead, choose **Download Server** in the same Hub. Add files
through the Hub's **Download Library**, or sign in with a Team/TL/Manager account
and open `https://ticketing-system.local/downloads/manage/` from another
reachable laptop. Files are stored under `download-server/downloads`. Share
`http://download-system.local:8080/`. The Hub also shows the current Ethernet
and Wi-Fi IP links as fallbacks. Press Enter or close that terminal to stop
DownloadServer without affecting NVGS.

For server maintenance, select **Open database admin** in the Ubuntu Server Hub.
Enter the Django system-administrator password. This administration listener is
available only on the Ubuntu laptop, not through the LAN website.

The Hub checks Ethernet before starting either service. It can turn
NetworkManager networking back on and reconnect a saved profile. **Repair /
prefer Ethernet** runs a strict wired check and says whether Ethernet was
actually restored instead of treating an existing Wi-Fi address as success.
This can recover a disabled/disconnected adapter or a lost DHCP address. If the
Ethernet device vanishes from Ubuntu completely, the cause may instead be its
driver, kernel, firmware, cable/dock, or hardware; the repair window prints
diagnostics but does not guess which kernel module to reload.

The installed Ethernet watchdog continues checking in the background. It keeps
the NIC out of runtime power-save, turns off EEE when supported, cycles a lost
link, and reconnects the existing NetworkManager profile. For the detected
Realtek card it can reload only the verified `r8169` driver, at most once per
continuous outage. It never automatically reboots, edits GRUB, or turns off
Wi-Fi.

When the Ubuntu server is on Wi-Fi and another laptop is wired, both can only
communicate if the modem/router bridges those clients onto the same LAN. A
guest Wi-Fi, client isolation, separate VLANs, or blocked routing cannot be
fixed by Server Hub. Test a direct IP link from the Hub first; `.local` mDNS
names may not cross separated network segments even when routed IP traffic can.

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
