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

## 9. Install alerts and anti-sleep

```bash
cd ~/NVGS-Server
sudo ./scripts/install-ubuntu-host.sh
sudo reboot
```

After logging in again, confirm that Docker works without `sudo`:

```bash
docker ps
```

Check the local alert services:

```bash
systemctl status nvgs-monitor.service --no-pager
systemctl status nvgs-auth-monitor.service --no-pager
```

## 10. Create application users

In `https://localhost/admin/`, open **Users**.

- Keep the first account as `system_admin`.
- Use `team` for Tech Team, TL, and Manager accounts.
- Use `agent` for Robotics Team agent accounts.
- Leave `is_staff` and `is_superuser` disabled for `team` and `agent`.
- Use a separate local password. Never enter an NVIDIA corporate password into
  this local server.

Local accounts are temporary until approved NVIDIA SSO is available.

## 11. Create the first backup

```bash
cd ~/NVGS-Server
./scripts/backup.sh
```

The command prints the new backup filename under `backups/`. A real deployment
also needs a copy on a second approved encrypted device.

## 12. Stop before LAN deployment

At this point the database, administration, HTTPS, monitoring, anti-sleep,
accounts, and backups are ready.

These items are still development/deployment work:

- Copy and connect the normal ticketing interface
- Test with fake tickets
- Obtain an approved DHCP reservation, static address, or internal DNS name
- Install `nvgs-local-ca.crt` on every approved client
- Enable LAN binding in `.env`
- Import real ticket data
- Configure NVIDIA SSO after identity-administrator approval

Do not configure a random static IP or expose the server to the LAN yet.

## Getting future updates

From the Ubuntu project folder:

```bash
cd ~/NVGS-Server
./scripts/update-ubuntu-server.sh
```

This update command creates a database backup before pulling new code.
