# Apps Script notification bridge setup

This option reuses the original ticketing system's Google mail delivery:

```text
Django ticket -> signed HTTPS request -> Apps Script GmailApp
-> monitored inbox -> existing Power Automate flow -> Teams
```

It needs no SMTP password. It is separate from both the old Sheets ticketing
project and the NVGS login bridge.

## 1. Update Ubuntu and print the private setup values

```bash
cd ~/Documents/Codes/NVGS-Server
./scripts/update-ubuntu-server.sh
./scripts/appscript-notification-setup.sh prepare
```

Keep that terminal private. Do not paste or photograph the printed secret.

## 2. Create the standalone Apps Script project

1. Open <https://script.google.com/> with the approved NVIDIA Google account.
2. Select **New project**.
3. Rename it **NVGS Notification Bridge**.
4. Replace `Code.gs` with `appscript-notification-bridge/Code.gs`.
5. Open **Project Settings** and enable the manifest file.
6. Replace `appsscript.json` with
   `appscript-notification-bridge/appsscript.json`.
7. Save.

Do not paste the old ticketing database code or `Index.html` into this project.
After the manual setup works, optional updates can use:

```bash
./scripts/appscript-clasp-sync.sh appscript-notification-bridge
```

Link only this standalone project in its ignored `.clasp.json` first.

## 3. Add the three Script Properties

In **Project Settings -> Script Properties**, add:

| Property | Value |
| --- | --- |
| `NVGS_NOTIFICATION_SECRET` | The private value printed by Ubuntu |
| `NVGS_NOTIFICATION_INBOX_EMAIL` | The existing `POWER_AUTOMATE_INBOX_EMAIL` value |
| `NVGS_NOTIFICATION_SENDER_ALIAS` | The existing `FLOW_SENDER_ALIAS` value |

These values remain inside the Apps Script project and are not committed to
GitHub.

## 4. Authorize and test Google email

1. In the function selector, choose
   `checkNvgsNotificationBridgeConfiguration`.
2. Select **Run** and approve the Gmail permission if project policy allows it.
3. Open **Execution log**.
4. Confirm all four values are `true`.
5. Select `sendNvgsNotificationBridgeTestEmail` and run it.
6. Confirm the monitored inbox receives
   `GRTKT_EVENT TICKET_CREATED TEST-00000` and that Power Automate posts the
   test to Teams.

If the sender-alias check is false, verify that the alias is available to the
Google account that owns this bridge. Do not silently substitute somebody's
personal address.

`GmailApp` requires Google Gmail authorization. Read the consent screen before
approving it and stop if corporate policy does not allow this standalone
project to send as the selected account.

## 5. Deploy the bridge

1. Select **Deploy -> New deployment**.
2. Choose **Web app**.
3. Description: `NVGS signed notification bridge`.
4. **Execute as:** Me / the deploying account.
5. **Who has access:** the option that allows access without a Google login.
6. Select **Deploy** and copy the URL ending in `/exec`.

The Ubuntu notification worker has no interactive Google browser session.
Therefore a domain-only or login-required deployment cannot receive its POST.
If corporate policy does not offer anonymous web-app access, stop and use an
approved SMTP relay or Power Automate HTTPS endpoint instead.

Although the endpoint is reachable without Google login, it cannot choose a
recipient or arbitrary email contents. Every request must carry a matching
HMAC signature, be less than five minutes old, use a one-time nonce, contain a
supported ticket event, and use the inbox and sender alias stored in Script
Properties.

## 6. Enable it on Ubuntu

```bash
cd ~/Documents/Codes/NVGS-Server
./scripts/appscript-notification-setup.sh enable \
  'https://script.google.com/macros/s/DEPLOYMENT_ID/exec'
```

Then:

```bash
./scripts/appscript-notification-setup.sh status
docker compose logs --tail=50 notifications
```

Create one clearly marked pilot ticket. Confirm:

1. The ticket saves immediately in Django.
2. The notification worker logs a successful send.
3. The monitored inbox receives the structured email.
4. The existing Power Automate flow posts it to Teams.

## Disable

```bash
./scripts/appscript-notification-setup.sh disable
```

Disabling notification delivery does not delete tickets or stop the website.
