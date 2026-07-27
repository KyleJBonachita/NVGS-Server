# Alerts: simple setup

## Local alerts

In desktop-controlled mode, local alerts start when you open **NVGS Server
Control** and stop when you close it. Install that mode with:

```bash
sudo ./scripts/install-app-controlled-mode.sh
```

For a permanent server, `sudo ./scripts/install-ubuntu-host.sh
--force-always-on` starts the alerts at boot.

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

Send one harmless test:

```bash
sudo ./scripts/test-alert.sh
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
locally. When connectivity returns it sends a recovery message.

Reliable immediate "server is completely offline" alerts require either:

- Another device checking this laptop
- A Wi-Fi fallback connection
- An approved cellular connection

## Privacy

Rejected-login monitoring records the attempted username and source IP when
Ubuntu provides them. It does not take photographs or record audio/video.
