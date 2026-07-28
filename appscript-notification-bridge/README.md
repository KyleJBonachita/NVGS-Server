# NVGS Apps Script notification bridge

This is a separate, signed mail relay for the local Django server. It reuses
Google Apps Script `GmailApp` to send the existing `GRTKT_EVENT` email to the
Power Automate-monitored inbox. It does not store tickets in Google Sheets.

Do not merge it into the login bridge. The login bridge runs as each user and
is domain-only; this notification bridge runs as its deployer so a server POST
can send through one reviewed mailbox.

The complete setup is in `docs/APPSCRIPT_NOTIFICATION_BRIDGE.md`.
