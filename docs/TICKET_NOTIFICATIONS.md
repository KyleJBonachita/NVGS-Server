# Ticket notifications

Ticket notifications are disabled by default. Tickets always save to
PostgreSQL first; a separate `notifications` container sends queued messages
afterward. A webhook outage therefore does not block ticket creation.

Events queued when enabled:

- New ticket
- Assignment
- Status change
- Escalation
- Public comment

Internal notes are deliberately excluded.

## Configure an approved HTTPS webhook

On Ubuntu:

```bash
cd ~/NVGS-Server
sudo nano secrets/ticket_notification_webhook
```

Put the single approved HTTPS webhook URL on the first line. Do not add quotes
or other text. Protect and apply it:

```bash
sudo chmod 600 secrets/ticket_notification_webhook
docker compose up -d --build
docker compose ps
```

The dashboard's **System status** page reports only whether a webhook is
configured and how many messages are queued/failed. It never displays the URL.

Different Teams, Slack, and automation products can require different JSON
formats. NVGS currently sends a plain `text` field plus structured ticket
details. Confirm the selected approved endpoint accepts that payload during
the fake-data pilot. Adapt `tickets/notifications.py` only after obtaining the
endpoint's official format.

Email delivery is not enabled because no approved SMTP relay, sender address,
or authentication details have been supplied. Do not put a personal mailbox
password into NVGS.

## Check the worker

```bash
docker compose logs --tail=100 notifications
```

To process the current queue once for diagnostics:

```bash
docker compose exec notifications \
  python manage.py process_ticket_notifications --once
```

Failed deliveries retry with increasing delays. Messages that reach the retry
limit remain visible in Django administration and the System status page for
review.
