# NVGS Server: Start Here

This is the only setup file you need to follow. Do not edit the other project
files unless the development copy on Windows is being changed.

Run one section at a time. If a command fails, stop and save the complete error.

## 1. Download the project

```bash
cd ~
git clone https://github.com/KyleJBonachita/NVGS-Server.git
cd NVGS-Server
git status
```

Expected result:

```text
nothing to commit, working tree clean
```

## 2. Check Docker

```bash
docker --version
docker compose version
sudo docker run --rm hello-world
```

Look for `Hello from Docker!`.

## 3. Create private passwords

```bash
cd ~/NVGS-Server
chmod +x scripts/*.sh
./scripts/bootstrap-secrets.sh
```

Do not display or send anything inside `secrets/`.

## 4. Start locally

```bash
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
```

The initial configuration listens only on `127.0.0.1`. It is not yet exposed
to the production LAN.

Expected services:

- `db`
- `app`
- `caddy`

## 5. If the database fails

Do not delete anything. Collect these diagnostics:

```bash
sudo docker compose ps -a
sudo docker inspect nvgs-server-db-1 \
  --format='Status={{.State.Status}} Exit={{.State.ExitCode}} Error={{.State.Error}}'
sudo docker logs nvgs-server-db-1
```

Save or photograph the complete output, including the line immediately before
`operation not permitted`.

## 6. After all services are healthy

Create the first system-administrator account:

```bash
sudo docker compose exec app python manage.py createsuperuser \
  --email YOUR-NVIDIA-EMAIL@nvidia.com
```

Replace `YOUR-NVIDIA-EMAIL` with your actual email. Do not share the password.

Then open this page on the Ubuntu laptop:

```text
https://localhost/admin/
```

The command automatically gives this account the `system_admin` application
role.

## 7. Trust the local HTTPS certificate

Export Caddy's public root certificate:

```bash
cd ~/NVGS-Server
sudo docker compose cp \
  caddy:/data/caddy/pki/authorities/local/root.crt \
  ./nvgs-local-ca.crt
sudo cp ./nvgs-local-ca.crt \
  /usr/local/share/ca-certificates/nvgs-local-ca.crt
sudo update-ca-certificates
```

Close and reopen the browser. Test:

```bash
curl https://localhost/api/health/
```

Expected result:

```json
{"status":"ok","database":"available"}
```

Do not enter real passwords through a browser that still displays a certificate
warning.

## 8. Give the designated server administrator Docker access

The update and backup scripts need Docker access. Docker access is equivalent
to root access, so do this only for the designated server administrator:

```bash
sudo usermod -aG docker "$USER"
```

The permission takes effect after signing out or rebooting.

## 9. Choose how the server runs

For this laptop, use the simple desktop-controller mode:

```bash
cd ~/NVGS-Server
sudo ./scripts/install-app-controlled-mode.sh
sudo reboot
```

After logging in again, open Ubuntu Applications, search for **NVGS Server
Control**, and enter your Ubuntu password.

- Keep its terminal window open while people need the server.
- Full-screen warning alerts and anti-sleep are active while that window is
  open.
- Press Enter or close the window to stop the website, database, and alerts.
- Closing it restores normal sleep behavior. Ticket data is not deleted.

Test the popup:

```bash
cd ~/NVGS-Server
sudo ./scripts/test-alert.sh
```

The red warning screen can be dismissed with its button, `Enter`, or `Escape`.
Hardware checks run about every five seconds, although an event can occur
between checks.

Using **Lock** or pressing `Super+L` does not stop NVGS and does not let the
laptop sleep. Do not choose **Log Out** or **Sign Out** while NVGS is running,
because that closes the graphical session containing the controller. Ubuntu
may hide popup details on the lock screen, but journal and webhook alerts
continue.

The reboot is needed only the first time you switch away from the old
always-on installation.

If this laptop later becomes a permanent, approved server that must start at
boot, switch back with:

```bash
sudo ./scripts/install-ubuntu-host.sh --force-always-on
sudo reboot
```

## 10. Create application users

In `https://localhost/admin/`, open **Users**.

- Keep the first account as `system_admin`.
- Use `team` for Tech Team, TL, and Manager accounts.
- Use `agent` for Robotics Team agent accounts.
- Leave `is_staff` and `is_superuser` disabled for `team` and `agent`.
- Use a separate local password. Never enter an NVIDIA corporate password into
  this local server.

Local accounts can remain as a fallback. To reuse the existing Google
Workspace login, follow
[`appscript-bridge/README.md`](appscript-bridge/README.md) after the server is
reachable through its approved LAN HTTPS address.

## 11. Create the first backup

```bash
cd ~/NVGS-Server
./scripts/backup.sh
```

The command prints the new backup filename under `backups/`. A real deployment
also needs a copy on a second approved encrypted device.

## 12. Remaining work before team use

At this point the database, administration, HTTPS, optional monitoring and
anti-sleep, accounts, and backups are ready.

Complete these in order:

1. Copy and connect the normal ticketing interface.
2. Test ticket creation, assignment, comments, status changes, and permissions
   with fake users and fake tickets.
3. Obtain an approved DHCP reservation/static address and, preferably, an
   internal DNS name. Do not select an unassigned address yourself.
4. Enable the approved LAN address in `.env`, limit network access, and test
   from one approved client.
5. Install `nvgs-local-ca.crt` on each approved client so HTTPS has no warning.
6. Create local `agent` and `team` accounts, enable the reviewed Apps Script
   login bridge, or obtain identity-administrator approval and registration
   details for corporate NVIDIA SSO.
7. Test a database restore and keep a second backup on an approved encrypted
   device.
8. Configure an approved remote webhook or another approved device to detect
   a fully offline server.
9. Import real ticket data only after the pilot succeeds.

Do not configure a random static IP or expose the server to the LAN yet.

## Getting future updates

From the Ubuntu project folder:

```bash
cd ~/NVGS-Server
./scripts/update-ubuntu-server.sh
```

This update command creates a database backup before pulling new code.
In desktop-controller mode, open **NVGS Server Control** before running the
update so the database is available for that backup. When the update finishes,
stop and reopen the controller so launcher/overlay changes take effect.
