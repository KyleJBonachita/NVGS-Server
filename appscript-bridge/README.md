# Apps Script login bridge

This bridge reuses the existing Google Workspace domain login only for
identity. Ticket data still belongs to the local Django/PostgreSQL server.

The original local `appscript-ticketing-system/` folder is intentionally not
edited or tracked. Add the reviewed bridge to the deployed Apps Script project
manually.

## Security model

- Google must provide `Session.getActiveUser().getEmail()`.
- The web app must remain `USER_ACCESSING` and `DOMAIN`.
- Apps Script signs email, browser state, issuer, audience, nonce, and a
  60-second expiry with HMAC-SHA256.
- Django verifies every field and accepts only configured email domains.
- New verified users receive only the `agent` role.
- Existing disabled users remain blocked.
- Team and system-administrator roles are never granted from the token.
- The assertion is carried in the URL fragment, which browsers do not send in
  the HTTP request, and is then submitted to Django with CSRF protection.

## 1. Update the local server

With **NVGS Server Control** open:

```bash
cd ~/NVGS-Server
./scripts/update-ubuntu-server.sh
```

Stop and reopen the controller after the update.

## 2. Add the Apps Script code

In the Apps Script editor:

1. Create a script file named `NVGSLoginBridge`.
2. Copy in the contents of `appscript-bridge/NVGSLoginBridge.gs`.
3. Change the existing `doGet` in `Code.js` from:

```javascript
function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
```

to:

```javascript
function doGet(e) {
  var nvgsLogin = maybeHandleNvgsLogin_(e);
  if (nvgsLogin) return nvgsLogin;

  return HtmlService.createHtmlOutputFromFile('Index')
```

Do not change the remaining title/X-Frame lines.

## 3. Configure Script Properties

Open Apps Script **Project Settings** and add:

| Property | Value |
| --- | --- |
| `NVGS_BRIDGE_SECRET` | Exact contents of `secrets/appscript_bridge_secret` |
| `NVGS_BRIDGE_CALLBACK_URL` | `https://SERVER/api/auth/appscript/consume/` |
| `NVGS_BRIDGE_ISSUER` | `nvgs-appscript` |
| `NVGS_BRIDGE_AUDIENCE` | `nvgs-server` |
| `NVGS_BRIDGE_ALLOWED_DOMAIN` | `nvidia.com` |

`SERVER` must be the approved LAN hostname/address that the user's browser can
reach and whose local HTTPS certificate is trusted. `localhost` works only
while testing directly on the Ubuntu server.

To display the bridge secret on the Ubuntu laptop:

```bash
cd ~/NVGS-Server
cat secrets/appscript_bridge_secret
```

Never send that value through chat, email, tickets, screenshots, or GitHub.
Only Apps Script project editors can be trusted with it.

## 4. Redeploy Apps Script

Create a new web-app deployment version. Confirm:

- Execute as: **User accessing the web app**
- Who has access: **Anyone within the NVIDIA domain**

Copy the deployed `/exec` URL.

## 5. Enable the bridge in Django

Edit Ubuntu's `.env`:

```bash
cd ~/NVGS-Server
nano .env
```

Set:

```dotenv
APPSCRIPT_SSO_ENABLED=true
APPSCRIPT_SSO_URL=PASTE_THE_APPS_SCRIPT_EXEC_URL
APPSCRIPT_SSO_ISSUER=nvgs-appscript
APPSCRIPT_SSO_AUDIENCE=nvgs-server
APPSCRIPT_SSO_AUTO_CREATE_USERS=true
APPSCRIPT_SSO_SUCCESS_REDIRECT=/api/auth/me/
```

Apply:

```bash
docker compose up -d --build
```

## 6. Test

Open:

```text
https://SERVER/api/auth/appscript/start/
```

Expected flow:

1. Google opens the domain-restricted Apps Script.
2. The page displays the verified email.
3. Click **Continue to NVGS** within 60 seconds.
4. Django returns `/api/auth/me/` for the signed-in user.

Test first with a fake/pilot agent account. Confirm that it receives `agent`,
cannot view all tickets, and cannot open Django administration.

## Disable immediately

Set this in `.env` and restart the stack:

```dotenv
APPSCRIPT_SSO_ENABLED=false
```

```bash
docker compose up -d
```
