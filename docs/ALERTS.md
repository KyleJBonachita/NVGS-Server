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

Warnings use one coordinated full-screen acknowledgement screen while the NVGS
control terminal launched from **NVGS Server Hub** is open. It is a normal
borderless full-screen surface rather than a dialog, so Ubuntu does not reduce
it to a small centered window. Its default background is an animated red
warning field. The screen requests keyboard focus when it maps, focuses the
dismissal button, and retries that focus request briefly to handle GTK/Wayland
timing. Press `Enter`/`Escape` or click the button to dismiss it.

The overlay is the primary warning UI. Ubuntu's top notification is created
only when the overlay is unavailable, so a single event no longer leaves two
independent things to close. That fallback is transient, expires, and uses a
synchronous replacement tag so new events replace its banner instead of
flooding the notification center. Recovery and rejected-login events remain
brief desktop notifications. Every event is still written to the journal.

Warnings arriving together are grouped into the same screen. One dismissal
clears that group, and duplicate reminders for dismissed conditions pause for
five minutes. A physical link outage also groups/suppresses its dependent
Internet and application warnings until the link returns.

The monitor checks every five seconds. Charger, battery, cable, and lid results
are handled before slower Internet/application requests, so those slow checks
do not hold up an already-detected hardware warning.

The overlay loops Ubuntu's warning sound while it is open. Click **Mute sound**
or press `M` to stop it without dismissing the warning. If the system has no
supported sound player, the button says **Sound unavailable** and the visual
alert continues normally.

For a custom background and sound, create `host/assets` on the Ubuntu copy and
place these machine-specific files there:

- `nvgs-alert-background.gif`
- one of `nvgs-alert-sound.oga`, `.ogg`, `.wav`, or `.mp3`

The GIF is looped, scaled, and center-cropped to fill the display. A 1920x1080
GIF is a good choice for a 1920x1080 screen. These media files are ignored by
Git, so `git pull` will not overwrite them. Full details are in
`host/assets/README.md`.

Ubuntu does not allow an application to cover its secure lock screen; an alert
raised while locked remains recorded and can appear after unlocking.

Send one harmless local test while the controller is open:

```bash
sudo ./scripts/test-alert.sh
```

After installing this update, clear any old Ubuntu notifications once. Old
critical banners were created by the previous version and cannot be assigned
the new replacement behavior retroactively.

Dismiss the warning with its button, `Enter`, or `Escape`. Ubuntu/GNOME may
refuse focus stealing while its secure lock screen or another protected system
surface is active; after unlocking, click the warning once if keyboard focus
was intentionally withheld by the desktop.

If the controller says full-screen alerts could not start, verify that
PyGObject can load matching GDK 3 and GTK 3 namespaces:

```bash
python3 -c 'import gi; gi.require_version("Gdk", "3.0"); gi.require_version("GdkPixbuf", "2.0"); gi.require_version("Gtk", "3.0"); from gi.repository import Gdk, GdkPixbuf, Gtk; print("GTK 3 OK")'
```

The command must print `GTK 3 OK`. The overlay explicitly selects the GTK 3,
GDK 3, and GdkPixbuf 2 namespaces so incompatible versions cannot be chosen
accidentally.

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
