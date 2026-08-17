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
sudo apt install ethtool
sudo ./scripts/install-app-controlled-mode.sh
sudo reboot
```

After logging in again, open Ubuntu Applications and select **NVGS Server
Hub**. Choose **NVGS Server** for ticketing and alerts, or **Download Server**
for local file sharing, or **Gery Chatbot Server** for the optional floating
knowledge assistant, then enter your Ubuntu password.

- The Download Server's stable link is
  `http://download-system.local:8080/`; its IP-address fallbacks are also shown.
- The Hub shows network health and live service status. **Copy link** copies the
  preferred address, while **Open site** becomes available when a service is
  running.
- Starting any service checks Ethernet first and safely reconnects its
  existing NetworkManager profile if necessary. Use **Repair / prefer
  Ethernet** for a strict wired recovery check. It performs a privileged,
  rate-limited `r8169` hardware reset if ordinary recovery fails; Wi-Fi remains
  connected as a fallback.
- An automatic Ethernet watchdog runs in the background, including when only
  DownloadServer is used. It prevents NIC runtime power-down, disables EEE when
  supported, and attempts recovery without rebooting the laptop.
- Keep the selected service's control terminal open while people need it.
- NVGS enables its full-screen warnings and monitoring; both services prevent
  sleep while their control terminal is open.
- Press Enter or close that terminal to stop only the selected service.
- Closing all control terminals restores normal sleep behavior. Ticket and
  download data are not deleted.

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

If **Repair / prefer Ethernet** reports that the Ethernet device is completely absent,
the problem is below the server application. Save the device/driver diagnostics
shown in that window. Do not guess a `modprobe` command: the correct driver
depends on the laptop's actual Ethernet controller, kernel, and firmware.

Inspect automatic recovery at any time:

```bash
systemctl status nvgs-ethernet-watchdog.service
sudo journalctl -u nvgs-ethernet-watchdog.service -n 100 --no-pager
```

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

Local accounts can remain as a fallback. To reuse the verified NVIDIA Google
Workspace identity through the standalone login bridge, follow
[`appscript-bridge/README.md`](appscript-bridge/README.md) after the server is
reachable through its approved LAN HTTPS address.

The bridge setup begins with:

```bash
cd ~/NVGS-Server
./scripts/appscript-login-setup.sh prepare
```

## 11. Create the first backup

```bash
cd ~/NVGS-Server
./scripts/backup.sh
```

The command prints the new backup filename under `backups/`. A real deployment
also needs a copy on a second approved encrypted device.

## 12. Open the normal ticketing page

The end-user dashboard is now included. Open:

```text
https://localhost/
```

After Google/Apps Script login, the browser should end at `/tickets/`. The
`/api/auth/me/` page is only a developer diagnostic response.

Create the fake pilot users/tickets and follow every check in
[`docs/PILOT.md`](docs/PILOT.md).

## 13. Finish the external deployment items

These items need a real address, real client laptops, a real second storage
device, or a real second monitoring device. Code cannot truthfully complete
them by itself.

After the network administrator supplies the address and Ubuntu is using it:

```bash
./scripts/configure-approved-lan.sh ASSIGNED_IPV4
```

Export the public client certificate:

```bash
./scripts/export-client-ca.sh
```

Verify a real backup restore without changing production:

```bash
./scripts/verify-backup-restore.sh
```

Copy the latest backup to an approved second device with encryption:

```bash
./scripts/copy-backup-encrypted.sh /media/YOUR_APPROVED_DEVICE/BACKUPS
```

The second-device outage watcher and certificate installers are explained in
[`docs/UBUNTU_DEPLOYMENT.md`](docs/UBUNTU_DEPLOYMENT.md) and
[`docs/ALERTS.md`](docs/ALERTS.md).

See the exact completion status in
[`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md). Do not import
real tickets until the pilot succeeds.

## Getting future updates

From the Ubuntu project folder:

```bash
cd ~/NVGS-Server
./scripts/update-ubuntu-server.sh
```

This update command creates a database backup before pulling new code.
In desktop-controller mode, open **NVGS Server Hub** and choose **NVGS Server**
before running the update so the database is available for that backup. When
the update finishes, stop the NVGS control terminal and reopen the Hub so
launcher/overlay changes take effect.
