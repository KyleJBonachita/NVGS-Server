# Alerts: simple setup

## Local alerts

In desktop-controlled mode, local alerts start when you choose **NVGS Server**
in **NVGS Server Hub** and stop when you close its control terminal. Install
that mode with:

```bash
sudo ./scripts/install-app-controlled-mode.sh
```

For a permanent server, `sudo ./scripts/install-ubuntu-host.sh
--force-always-on` starts the alerts at boot.

Warnings take over the Ubuntu display with a red full-screen acknowledgement
screen while the NVGS control terminal launched from **NVGS Server Hub** is open. A normal desktop notification and
the journal remain as fallbacks. Recovery events use a normal desktop
notification instead of interrupting the whole screen.

The monitor checks every five seconds. Charger, battery, cable, and lid results
are handled before slower Internet/application requests, so those slow checks
do not hold up an already-detected hardware warning.

The warning requests a sound, but Ubuntu's notification settings may mute it.
Ubuntu does not allow an application to cover its secure lock screen; an alert
raised while locked remains recorded and can appear after unlocking.

Send one harmless local test while the controller is open:

```bash
sudo ./scripts/test-alert.sh
```

Dismiss the full-screen warning with its button, `Enter`, or `Escape`.

If the controller says full-screen alerts could not start, verify that
PyGObject can load matching GDK 3 and GTK 3 namespaces:

```bash
python3 -c 'import gi; gi.require_version("Gdk", "3.0"); gi.require_version("Gtk", "3.0"); from gi.repository import Gdk, Gtk; print("GTK 3 OK")'
```

The command must print `GTK 3 OK`. The overlay explicitly selects both
versions so an installed GDK 4 cannot be chosen accidentally.

Every alert is also recorded in the local journal:

Watch the laptop/application checks:

```bash
journalctl -u nvgs-monitor.service -f
```

Watch rejected Ubuntu login attempts:

```bash
journalctl -u nvgs-auth-monitor.service -f
```

## Remote alerts

Remote alerts require a webhook URL from the chosen approved messaging system.
Until a URL is available, leave the setting blank and alerts remain in the
Ubuntu journal.

Edit:

```bash
sudo nano /etc/nvgs-monitor.env
```

Set the value in quotes:

```dotenv
NVGS_ALERT_WEBHOOK_URL='https://approved-webhook-address'
```

If the desktop controller is open, restart the monitors:

```bash
sudo systemctl restart nvgs-monitor.service nvgs-auth-monitor.service
```

The current JSON message uses a `text` field, which is accepted by many webhook
systems. If the selected system expects a different format, adapt
`host/nvgs_alerts.py` after we know that system's documented format.

The default Internet test uses Ubuntu's connectivity-check address. If that
address is blocked at work, replace `NVGS_CONNECTIVITY_URL` with an approved
HTTPS address, or leave it blank to disable only the Internet test.

## Important limitation

If Ethernet is unplugged and the laptop has no second connection, it cannot
send a remote message through Ethernet. The monitor still records the event
locally and can show it on the Ubuntu desktop. When connectivity returns it
sends a recovery message.

Reliable immediate "server is completely offline" alerts require either:

- Another device checking this laptop
- A Wi-Fi fallback connection
- An approved cellular connection

## Second-device watcher

The repository includes a watcher specifically for a second approved Ubuntu
device. Copy or clone the repository and the public `nvgs-local-ca.crt` onto
that device, then run there:

```bash
sudo ./scripts/install-remote-watch.sh \
  https://ASSIGNED_SERVER_ADDRESS/api/health/ \
  /path/to/nvgs-local-ca.crt
```

Add an approved webhook to `/etc/nvgs-remote-watch.env`, restart the service,
and watch its log:

```bash
sudo systemctl restart nvgs-remote-watch.service
journalctl -u nvgs-remote-watch.service -f
```

It waits for three consecutive failures by default before alerting, then sends
a recovery when the server returns. Installing it on the NVGS server itself
does not provide offline detection; the installer rejects localhost addresses.

## Privacy

Rejected-login monitoring records the attempted username and source IP when
Ubuntu provides them. It does not take photographs or record audio/video.
