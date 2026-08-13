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

The `secrets/` directory remains accessible only to the Ubuntu server account.
Its individual files are readable through Docker's read-only bind mounts so
the Django containers can stay unprivileged instead of running as root.

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

The Caddy configuration uses `SERVER_ADDRESS` as its default TLS server name.
This is required for IP-address clients that omit SNI during the TLS handshake.

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

First collect a safe read-only report:

```bash
./scripts/lan-readiness.sh
```

The report shows Ubuntu's current interface/address and NVGS binding. It does
not treat a temporary DHCP address as approved.

Once the server address is confirmed and Ubuntu is already using it, run:

```bash
./scripts/configure-approved-lan.sh ASSIGNED_IPV4
```

If an approved internal DNS name exists:

```bash
./scripts/configure-approved-lan.sh ASSIGNED_IPV4 APPROVED_DNS_NAME
```

The helper does not choose an address or change NetworkManager. Without an
assigned/reserved address already present on Ubuntu, it stops.

The equivalent manual `.env` values are:

```dotenv
SERVER_BIND_IP=ASSIGNED_IP
SERVER_LISTEN_IP=ASSIGNED_IP
SERVER_ADDRESS=ASSIGNED_IP_OR_DNS_NAME
DJANGO_ALLOWED_HOSTS=ASSIGNED_IP_OR_DNS_NAME
DJANGO_CSRF_TRUSTED_ORIGINS=https://ASSIGNED_IP_OR_DNS_NAME
```

Then:

```bash
docker compose up -d
docker compose ps
```

`SERVER_LISTEN_IP` controls where Docker publishes HTTPS. The approved manual
helper sets it to the assigned address. Dynamic mode uses `0.0.0.0` while
Caddy and Django accept only the detected physical LAN addresses and name.

### Temporary dynamic-DHCP pilot

When the network owner permits a temporary pilot but has not provided a DHCP
reservation, the desktop controller can refresh the selected interface's IPv4
address every time it opens. Enable this once with the actual interface name:

```bash
./scripts/refresh-dynamic-lan.sh enp109s0
```

Close the NVGS control terminal and reopen it from **NVGS Server Hub**. Before Docker starts, the controller
updates Caddy's preferred address, all active physical Ethernet/Wi-Fi
addresses, Django's allowed hosts and CSRF origins, and the local monitor
target. Docker bridge and VPN addresses are excluded. The saved adapter remains
preferred while usable. If it has no address, startup follows another usable
adapter temporarily without forgetting the explicit choice. It never changes Ubuntu's DHCP or
NetworkManager configuration. If no usable IPv4 address exists, startup stops
safely.

To keep the visible link stable, provide a custom `.local` mDNS name:

```bash
./scripts/refresh-dynamic-lan.sh enp109s0 ticketing-system.local
```

The controller resolves the alias locally through `/etc/hosts`, publishes it
through Avahi with the preferred address, and configures Caddy to accept the
alias and every active physical LAN IP before Docker starts. It does not rename the
Ubuntu laptop. If Avahi is not installed, startup stops with the exact approved
package command. Test the same name from every approved client because mDNS can
be blocked by network policy.

For an isolated Wi-Fi segment, first connect Ubuntu to the same approved SSID,
then select the actual wireless interface:

```bash
./scripts/refresh-dynamic-lan.sh wlp110s0f0 ticketing-system.local
```

Ethernet may remain connected for normal host traffic. NVGS and DownloadServer
listen on both physical addresses. The client installer maps the friendly name
to whichever address is reachable from that laptop. This does not bridge or
route the two networks and cannot bypass guest/client isolation within the
SSID.

For approved clients where mDNS name resolution is unavailable, use the
standalone client setup package. The controller rebuilds it after Caddy starts;
it can also be built manually:

```bash
./scripts/build-client-setup.sh
```

Distribute `client-setup-output/NVGS-Client-Setup.zip` through an approved
method. Its Windows and Ubuntu installers verify the public certificate, test
all current NVGS LAN addresses, map the friendly name to the reachable one,
install the CA, and create a ticketing shortcut.
The package contains no private key or server secret and must not be committed.
The Windows installer verifies both its hosts-file mapping and port 443, and
creates an IP fallback shortcut when company name-resolution policy still
overrides `.local`. Reinstall the newly rebuilt package whenever an unreserved
DHCP address changes.

Without a stable name, a DHCP change also changes client bookmarks. Whenever
the visible server link changes, the Apps Script bridge callback is
intentionally not modified remotely; run `./scripts/appscript-login-setup.sh
prepare` and update its Script Property. A reservation or approved internal
DNS name remains the production solution.

## 5a. Install the public CA on approved clients

Export and print the fingerprint:

```bash
./scripts/export-client-ca.sh
```

On an approved Ubuntu client, after verifying the fingerprint:

```bash
sudo ./scripts/install-ca-ubuntu-client.sh \
  /path/to/nvgs-local-ca.crt \
  --install
```

On an approved Windows client, first inspect without changing trust:

```powershell
.\scripts\install-ca-windows-client.ps1 `
  -CertificatePath .\nvgs-local-ca.crt
```

After approval and fingerprint verification, open PowerShell as Administrator
and add `-Install`. Corporate policy may prevent this; do not bypass that
policy.

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

After reboot, open **NVGS Server Hub** from Ubuntu Applications and choose
**NVGS Server**. The NVGS control terminal:

- Starts PostgreSQL, Django, Caddy, and both alert monitors
- Shows a red full-screen acknowledgement for warnings and a normal desktop
  notification for recoveries
- Temporarily blocks sleep and lid-close suspension
- Keeps a terminal window open to show that NVGS is running
- Stops the containers and monitors when you press Enter or close the window

The Hub is catalog-driven so future servers can be added as another card. Its
network panel shows the active Ethernet/Wi-Fi addresses and provides
**Repair / prefer Ethernet**. Every server start runs the same conservative
selection first: use working Ethernet, try its best existing saved
NetworkManager connection, and only then allow working Wi-Fi as a fallback.
The manual repair action is stricter and succeeds only when Ethernet has an
IPv4 address. It does not create profiles, change static/DHCP settings, disable
Wi-Fi, or reload an unverified kernel driver.

Choose **Download Server** for the optional file portal. It publishes
`http://download-system.local:8080/` and direct-IP fallback links. This is a
separate Avahi host alias from NVGS's `ticketing-system.local`; both point to the
same Ubuntu LAN address and add no second DNS daemon.

### Ethernet disappears from Ubuntu

Use **Repair / prefer Ethernet** first. It handles NetworkManager networking
being disabled, a disconnected saved profile, and a missing IPv4 lease. If it
cannot recover, it prints `ip`, routes, `nmcli`, and PCI driver information.

The installer enables `nvgs-ethernet-watchdog.service` for recovery between
manual checks. Install `ethtool` so the watchdog can also disable EEE:

```bash
sudo apt install ethtool
sudo ./scripts/install-app-controlled-mode.sh --refresh
```

The watchdog applies targeted recovery in this order:

1. Force the Ethernet PCI device's runtime power policy to `on`.
2. Disable EEE when the installed driver reports that control is supported.
3. Cycle only the Ethernet interface and reconnect its saved profile.
4. If carrier remains absent, reload the dynamically verified `r8169` module.

The driver reload is limited to one attempt per continuous outage with a
ten-minute cooldown, is refused for any unknown driver, and is skipped if that
module controls another live interface. The service does not automatically
reboot, disable Wi-Fi, mask sleep, or change global PCIe ASPM/GRUB settings.

Monitor it with:

```bash
systemctl status nvgs-ethernet-watchdog.service
sudo journalctl -u nvgs-ethernet-watchdog.service -f
```

If the service reports that `r8169` reloaded but the PCI device did not return,
a full shutdown/power-on cycle, BIOS/firmware update, different cable/port, or
hardware service may still be required. Automatic rebooting is intentionally
not used because it would abruptly interrupt tickets and downloads.

If a Wi-Fi-hosted server cannot be reached from an Ethernet client, try the
Wi-Fi IP address displayed by the Hub, not only the `.local` name. If the IP is
also unreachable, compare both laptops' IP/subnet and check the modem/router
for guest Wi-Fi, AP/client isolation, VLAN separation, or wired-to-wireless
firewall rules. Those network policies are outside the Ubuntu server process.

If the Ethernet interface is absent from both `ip -brief link` and the PCI/USB
device report, or repeatedly disappears from the kernel, investigate the exact
laptop NIC/dock model, installed kernel, firmware, cable, and power-management
behavior. A server launcher cannot safely choose a driver module without that
hardware evidence. Collect the current-boot kernel log with:

```bash
sudo journalctl -k -b --no-pager | \
  grep -Ei 'ethernet|network|link|firmware|r816|e1000|igc|tg3'
```

The one-time reboot removes the old permanent lid override safely. Normal
Ubuntu sleep behavior returns whenever the controller is closed.

Locking the screen does not close the controller or release its sleep
inhibitor. Logging out closes the graphical session and is not supported while
NVGS is running. Notification details can be hidden by Ubuntu while locked;
the journal and configured webhook still receive the event.

Full-screen alerts use GTK 3. If the installer reports that GTK Python support
is missing, install the Ubuntu packages and refresh the controller:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0
sudo ./scripts/install-app-controlled-mode.sh
```

The overlay explicitly selects both GDK 3 and GTK 3 before importing either
library. This prevents PyGObject from accidentally pairing GDK 4 with GTK 3.

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
In desktop-controlled mode, run the update while the **NVGS Server** control
terminal is open, because the first update step backs up the running database.
Keep that terminal open during the update, then stop and reopen it so launcher
changes take effect.
