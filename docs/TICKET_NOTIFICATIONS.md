# Ticket notifications and Power Automate

Ticket notifications are disabled by default. Tickets save to PostgreSQL
first; the separate `notifications` container sends queued alerts afterward.
An email, Power Automate, Teams, or internet outage never blocks ticket
creation.

Queued events:

- New ticket
- Assignment
- Status change
- Resolution or reopen
- Escalation
- Public comment

Internal notes are never sent.

## Recommended setup helper

On Ubuntu, choose **NVGS Server** in **NVGS Server Hub**, keep its terminal open, and run:

```bash
cd ~/NVGS-Server
./scripts/configure-ticket-notifications.sh
```

Choose:

1. Disabled
2. Approved HTTPS webhook
3. Email to the existing Power Automate-monitored inbox
4. Signed Apps Script Gmail bridge to that existing inbox

Option 4 is the closest match to the old ticketing application and needs no
SMTP password. Follow `docs/APPSCRIPT_NOTIFICATION_BRIDGE.md`.

The direct email choice asks for an approved SMTP relay/service account. Never use a
personal NVIDIA, Google, or Microsoft password. The password is entered hidden
and stored only in the ignored `secrets/smtp_password` file.

Apply the configuration:

```bash
docker compose up -d --build
docker compose logs --tail=50 notifications
```

## Existing email -> Power Automate -> Teams flow

Email mode preserves the original Apps Script convention:

```text
Subject: GRTKT_EVENT TICKET_CREATED NVGS-2026-000123
Body: structured JSON
```

The JSON includes `app`, `eventType`, `ticket`, `actor`, `teams`,
`idempotencyKey`, and `sentAt`. This means the existing Power Automate flow can
continue filtering subjects beginning with `GRTKT_EVENT` and parsing the body.

The original sender was Apps Script. Django still needs an approved way to send
mail. Ask the project owner/security reviewer for one of:

- A restricted internal SMTP relay
- A dedicated SMTP service account
- A Power Automate HTTPS trigger approved for this project
- The signed Apps Script notification bridge described above

Do not bypass MFA or corporate mail policy. If no approved sender is available,
keep delivery disabled; queued ticket operations remain fully functional.

In Power Automate, the existing flow should:

1. Trigger when a new email reaches the monitored inbox.
2. Filter subjects beginning with `GRTKT_EVENT`.
3. Parse the JSON body.
4. Use `eventType` for the notification case.
5. Post the formatted message to the approved Teams chat or channel.
6. Use `idempotencyKey` to avoid duplicate posts after retries.

Microsoft's Teams action cannot mark an automated message as Urgent or
Important, so represent urgency in the card/message text instead.

## HTTPS webhook mode

Run the setup helper and paste only the approved HTTPS URL. It is stored in
`secrets/ticket_notification_webhook`, never displayed in the dashboard, and
never committed to Git.

NVGS sends a plain `text` field plus structured ticket details. Confirm the
chosen flow accepts that payload during the fake-data pilot.

## Check or retry the worker

```bash
docker compose logs --tail=100 notifications
docker compose exec notifications \
  python manage.py process_ticket_notifications --once
```

Failed deliveries retry with increasing delays. Items that reach the retry
limit remain visible in Django administration and on **System status** for
review.
