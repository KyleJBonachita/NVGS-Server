# Ticketing pilot

The pilot uses fake accounts and clearly marked fake tickets. Do not import
real ticket data yet.

## 1. Pull and open the dashboard

On the Ubuntu server, keep **NVGS Server Control** open, then run:

```bash
cd ~/NVGS-Server
./scripts/update-ubuntu-server.sh
```

Close and reopen **NVGS Server Control** after the update. Open:

```text
https://localhost/
```

Google/Apps Script login should finish at `/tickets/`, not `/api/auth/me/`.

## 2. Create fake pilot data

Choose a temporary password that is used only for these fake NVGS accounts:

```bash
read -rsp "Temporary pilot password: " NVGS_PILOT_PASSWORD
echo
export NVGS_PILOT_PASSWORD
docker compose exec -e NVGS_PILOT_PASSWORD app \
  python manage.py seed_pilot_data --confirm
unset NVGS_PILOT_PASSWORD
```

The command creates:

- Two fake agents
- One fake Tech Team member
- One fake TL
- One fake Manager
- Four tickets prefixed with `[PILOT]`

Tech Team, TL, and Manager use the same `team` authority, as requested. The
fake accounts use local NVGS login because they are not real Google accounts.

## 3. Agent test

Use `nvgs.pilot.agent.one@nvidia.com` and the temporary pilot password.

Confirm:

1. The agent sees only their own tickets.
2. The agent can raise a ticket.
3. The new ticket starts as **Open** and unassigned.
4. The agent can add a public comment.
5. The agent cannot see internal notes, assignment controls, or Team actions.

## 4. Team/TL/Manager test

Sign out and use each of these accounts:

- `nvgs.pilot.tech@nvidia.com`
- `nvgs.pilot.tl@nvidia.com`
- `nvgs.pilot.manager@nvidia.com`

Confirm:

1. Each account can open **Complete queue** and see all fake tickets.
2. Each can assign a ticket to themselves or another Team account.
3. Each can move an assigned ticket to **In Progress**.
4. Each can put an in-progress ticket **On Hold** and resume it.
5. Each can resolve an in-progress ticket only after adding resolution notes.
6. Each can add an internal note that is hidden from agents.
7. Each can escalate a ticket.
8. None of these `team` accounts can enter Django administration.

Only the `system_admin` account should have Django administration access.

## 5. Client-laptop pilot

After an approved LAN address and certificate installation:

1. Open the LAN HTTPS address on one approved laptop.
2. Confirm there is no certificate warning.
3. Complete agent creation/comment testing.
4. Complete Team assignment/resolution testing.
5. Lock the Ubuntu server screen and repeat a client request.
6. Unplug/reconnect the charger and Ethernet one at a time to test local
   warnings and recoveries.
7. Confirm the second-device watcher reports a simulated server outage.

Record the date, participants, address used, certificate fingerprint, test
results, and any issues. Fix failed items before importing real data.
