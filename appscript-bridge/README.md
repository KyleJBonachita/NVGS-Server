# NVGS Apps Script login: complete setup

This creates a small standalone Google Apps Script project that verifies the
active NVIDIA Google Workspace account. It does not store tickets and does not
change the original Apps Script ticketing system.

The bridge is an interim login method, not an official NVIDIA OIDC/SAML
application. Use it only after the project owner and security reviewer approve
the design.

## What the bridge guarantees

- Google must provide `Session.getActiveUser().getEmail()`.
- The deployment must run as the user accessing the web app.
- Access must be limited to the deployer's Google Workspace domain.
- The handoff is signed with HMAC-SHA256 and expires after 60 seconds.
- The login attempt is bound to the browser session that started it.
- New verified users are created only as `agent`.
- First-time users must enter their name and create a separate local NVGS
  password before the authenticated session is activated.
- Existing roles are preserved; disabled accounts remain blocked.
- The bridge never grants `team` or `system_admin` authority.
- The shared signing secret stays out of GitHub and application URLs.

## Part 1: update and prepare Ubuntu

Keep **NVGS Server Control** open and run:

```bash
cd ~/NVGS-Server
./scripts/update-ubuntu-server.sh
```

Stop and reopen the controller when the update finishes. Then run:

```bash
cd ~/NVGS-Server
./scripts/appscript-login-setup.sh prepare
```

The helper prints:

- The exact callback URL for this Ubuntu server
- The four non-secret Script Properties
- The private bridge secret
- The eventual NVGS login address

Do not send, photograph, or paste the secret into chat, email, tickets, or
GitHub. Copy it only from the Ubuntu terminal into the Apps Script project's
Script Properties.

If the helper prints a callback containing `localhost`, the first test must be
performed in a browser on the Ubuntu laptop. Other laptops cannot use another
computer's `localhost`.

## Part 2: create the standalone Apps Script project

1. Open <https://script.google.com/> while signed in with the correct NVIDIA
   Google Workspace account.
2. Select **New project**.
3. Rename it to **NVGS Login Bridge**.
4. In the default `Code.gs`, replace everything with the contents of this
   repository's `appscript-bridge/Code.gs`.
5. Click **+** beside Files, select **Script**, and name it
   `NVGSLoginBridge`.
6. Copy the contents of `appscript-bridge/NVGSLoginBridge.gs` into that file.
7. Select **Project Settings**.
8. Enable **Show "appsscript.json" manifest file in editor**.
9. Return to the editor and replace the manifest with the contents of
   `appscript-bridge/appsscript.json`.
10. Save the project.

There is no `Index.html` file. The standalone `Code.gs` deliberately does not
reference one.

Do not select and run `doGet` from the editor. `doGet(e)` receives its `e`
request object only when Google opens the deployed web app.

## Part 3: add Script Properties

In Apps Script, open **Project Settings**. Under **Script Properties**, select
**Add script property**.

Add the five names and values printed by Ubuntu's `prepare` command:

| Property |
| --- |
| `NVGS_BRIDGE_SECRET` |
| `NVGS_BRIDGE_CALLBACK_URL` |
| `NVGS_BRIDGE_ISSUER` |
| `NVGS_BRIDGE_AUDIENCE` |
| `NVGS_BRIDGE_ALLOWED_DOMAIN` |

Property names are case-sensitive. Do not add quotation marks around values.

Save the properties. To check them without exposing the secret:

1. Return to the editor.
2. Select `checkNvgsBridgeConfiguration` in the function list.
3. Click **Run**.
4. Approve the requested email-identity permission if corporate policy permits
   it.
5. Open **Execution log**.

Every reported value should be `true`. The check logs only success/failure
flags; it does not log the secret or email address.

If Google or corporate policy refuses the authorization, stop. The bridge
cannot safely obtain the user's identity in that configuration.

## Part 4: deploy the web app

1. Select **Deploy** then **New deployment**.
2. Next to **Select type**, choose **Web app**.
3. Enter `NVGS signed login bridge` as the description.
4. Select **Execute as: User accessing the web app**.
5. Select access limited to the NVIDIA Google Workspace domain.
6. Select **Deploy**.
7. Copy the deployed URL ending in `/exec`.

Do not use the test URL ending in `/dev`. If the required execute-as-user or
domain-only options are unavailable, stop: the organization's Google Workspace
policy does not permit this bridge as designed.

## Part 5: enable it on Ubuntu

Paste the `/exec` deployment URL only into this local command:

```bash
cd ~/NVGS-Server
./scripts/appscript-login-setup.sh enable \
  'https://script.google.com/macros/s/DEPLOYMENT_ID/exec'
```

The helper validates the URL, updates `.env`, and applies it if the server is
already running. It does not place the signing secret in `.env`.

Check the configuration at any time:

```bash
./scripts/appscript-login-setup.sh status
```

## Part 6: test the complete login

The `enable` command prints the exact login address. For a local Ubuntu test it
is:

```text
https://localhost/api/auth/appscript/start/
```

Expected flow:

1. NVGS redirects the browser to Google.
2. Google may ask the user to authorize access to their email identity.
3. The bridge displays the verified NVIDIA email.
4. Select **Continue to NVGS** within 60 seconds.
5. On the first login, NVGS asks for first name, last name, and a separate
   local NVGS password.
6. After the profile is saved, NVGS displays the authenticated account
   information from `/api/auth/me/`.

Never enter an NVIDIA or Google password into the NVGS profile form. The local
password is an independent fallback credential stored only by the local Django
server. On later Google logins, users with completed profiles go directly into
NVGS without repeating the profile form.

Test with an approved pilot agent first. In Django administration, confirm the
new account:

- Has role `agent`
- Is not staff or superuser
- Cannot view another agent's tickets
- Cannot open Django administration

Create or edit Tech Team, TL, and Manager accounts manually and assign the
`team` role. Never derive elevated authority only from an email suffix.

## Using other production laptops

`localhost` works only on the Ubuntu laptop. Before other laptops can log in,
the Ubuntu server needs:

1. An approved DHCP reservation or static LAN address
2. Matching `SERVER_BIND_IP`, `SERVER_ADDRESS`, `DJANGO_ALLOWED_HOSTS`, and
   `DJANGO_CSRF_TRUSTED_ORIGINS` values in `.env`
3. The Caddy `nvgs-local-ca.crt` installed as a trusted root on each approved
   client
4. `NVGS_BRIDGE_CALLBACK_URL` updated to that LAN address
5. A new Apps Script deployment version after configuration changes

Do not invent an unused IP address. Use an address assigned for this server.

## Common errors

### `ReferenceError: e is not defined`

Replace `Code.gs` with the tracked standalone version. The first line must be:

```javascript
function doGet(e) {
```

The bridge call must be inside that function.

### `No HTML file named Index was found`

The project still has the old ticketing-app fallback. Replace all of `Code.gs`
with `appscript-bridge/Code.gs`. The standalone bridge has no `Index.html`.

### Google does not provide an email

Confirm the deployment runs as **User accessing the web app** and is restricted
to the correct Workspace domain. Also avoid being signed into several Google
accounts simultaneously; use a private browser window with only the NVIDIA
account when diagnosing.

### NVGS says login is not enabled

Run:

```bash
./scripts/appscript-login-setup.sh status
```

If disabled, repeat the `enable` command with the deployed `/exec` URL.

### `403 CSRF verification failed` after Continue to NVGS

Update the Ubuntu repository and restart **NVGS Server Control**. Current
versions use the signed 60-second assertion and the one-time browser-session
state to protect only the bridge callback. The normal profile form keeps
Django's standard CSRF protection. Local Django bridge pages use
`Referrer-Policy: same-origin`; do not add `null` to
`CSRF_TRUSTED_ORIGINS`.

### Signed response is invalid

- Run `timedatectl status` and ensure Ubuntu's clock synchronization is active.
- Run `prepare` again and confirm the Apps Script secret exactly matches.
- Confirm issuer and audience match the printed values.
- Start again and select **Continue to NVGS** within 60 seconds.

### Browser shows an HTTPS certificate warning

Stop testing with real accounts until the Caddy local root certificate is
trusted on that laptop. See `docs/UBUNTU_DEPLOYMENT.md`.

## Disable and roll back

Run:

```bash
cd ~/NVGS-Server
./scripts/appscript-login-setup.sh disable
```

Local account login remains available. Disabling the bridge does not delete
users, roles, tickets, or the database.

For a complete bridge shutdown, also archive the Apps Script deployment and
remove `NVGS_BRIDGE_SECRET` from its Script Properties.
