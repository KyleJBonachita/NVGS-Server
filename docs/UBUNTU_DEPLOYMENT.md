# Ubuntu deployment

## 1. Prepare the laptop

- Prefer wired Ethernet.
- Use a DHCP reservation when possible. Otherwise use an explicitly assigned
  address inside the correct subnet but outside the dynamic DHCP pool.
- Enable full-disk encryption during installation.
- Install system and firmware updates.
- Secure the laptop physically and keep its cooling vents unobstructed.
- Do not use the NVIDIA GPU for this service; it is not required.

Ubuntu documents the address, route, and DNS values required for a static
configuration:

<https://documentation.ubuntu.com/server/explanation/networking/configuring-networks/>

## 2. Install Docker

Follow Docker's current official Ubuntu installation:

<https://docs.docker.com/engine/install/ubuntu/>

Confirm:

```bash
sudo systemctl status docker
docker compose version
```

Docker access is equivalent to root access. Only designated server
administrators should belong to the `docker` group.

## 3. Configure NVGS Server

```bash
git clone https://github.com/KyleJBonachita/NVGS-Server.git
cd NVGS-Server
chmod +x scripts/*.sh
./scripts/bootstrap-secrets.sh
nano .env
```

Start locally first:

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 app
```

Create the first system administrator:

```bash
docker compose exec app python manage.py createsuperuser \
  --email your.name@nvidia.com
```

Use `/admin/` to provision agent and Tech Team/TL accounts. Self-registration
is intentionally unavailable.

## 4. Trust the HTTPS certificate

Caddy creates an internal certificate authority because a private IP normally
cannot receive a public web certificate.

Export its public root certificate:

```bash
docker compose cp \
  caddy:/data/caddy/pki/authorities/local/root.crt \
  ./nvgs-local-ca.crt
```

The root certificate is public; its private key must remain inside the Caddy
volume. Install `nvgs-local-ca.crt` into the trusted-root store on each approved
client. Do not distribute anything from the `secrets/` directory or Caddy's
private-key directories.

Client browsers will display a certificate error until the root is trusted.
Do not enter real passwords through a page with an unresolved certificate
warning.

Caddy documents this requirement for other devices:

<https://caddyserver.com/docs/running#local-https-with-systemd>

Test from a client that has the root certificate:

```bash
curl --cacert nvgs-local-ca.crt \
  https://SERVER_ADDRESS/api/health/
```

Expected result:

```json
{"status":"ok","database":"available"}
```

## 5. Enable LAN binding

Once the server address is confirmed, update all four `.env` values:

```dotenv
SERVER_BIND_IP=ASSIGNED_IP
SERVER_ADDRESS=ASSIGNED_IP_OR_DNS_NAME
DJANGO_ALLOWED_HOSTS=ASSIGNED_IP_OR_DNS_NAME
DJANGO_CSRF_TRUSTED_ORIGINS=https://ASSIGNED_IP_OR_DNS_NAME
```

Then:

```bash
docker compose up -d
docker compose ps
```

Changing `SERVER_BIND_IP` from `127.0.0.1` is the action that makes the service
reachable from the LAN.

## 6. Firewall limitation

The Compose file publishes only HTTPS 443 and never PostgreSQL 5432. It also
binds HTTPS to one selected host address instead of every host interface.

Docker-published ports can bypass ordinary UFW input rules. Do not assume a UFW
rule limits access to the container. Source-network restrictions must be made
in the upstream network firewall or a reviewed `DOCKER-USER` rule. Docker
documents this behavior:

<https://docs.docker.com/engine/network/packet-filtering-firewalls/#docker-and-ufw>

UFW remains useful for host services such as SSH. Restrict SSH to the
administrator network and use SSH keys.

## 7. Desktop-controlled server mode

Use this mode when NVGS should run only when you deliberately open it:

```bash
sudo ./scripts/install-app-controlled-mode.sh
sudo reboot
```

After reboot, double-click **NVGS Server Control** on the desktop. The launcher:

- Starts PostgreSQL, Django, Caddy, and both alert monitors
- Temporarily blocks sleep and lid-close suspension
- Keeps a terminal window open to show that NVGS is running
- Stops the containers and monitors when you press Enter or close the window

The one-time reboot removes the old permanent lid override safely. Normal
Ubuntu sleep behavior returns whenever the controller is closed.

For a permanent approved deployment that must start at boot instead, use:

```bash
sudo ./scripts/install-ubuntu-host.sh --force-always-on
sudo reboot
```

Keeping the lid physically open with the display switched off is preferable if
the laptop exhausts heat through the hinge or keyboard.

## 8. Routine operation

```bash
docker compose ps
docker compose logs --tail=100
./scripts/backup.sh
```

Apply updates in a scheduled window:

```bash
git pull --ff-only
docker compose pull
docker compose up -d --build
docker compose ps
```

Never run `docker compose down -v` on the production server. The `-v` option
deletes the persistent database volume.

For the normal Windows-to-GitHub-to-Ubuntu workflow, use:

```bash
./scripts/update-ubuntu-server.sh
```

It performs the backup, pull, rebuild, and monitor refresh in order.
In desktop-controlled mode, run the update while **NVGS Server Control** is
open, because the first update step backs up the running database. Keep the
controller window open after the update.
