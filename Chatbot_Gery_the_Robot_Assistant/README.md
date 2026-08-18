# Gery Robot Assistant

Gery is an optional local Chatbot Server for NVGS. It provides:

- A floating bottom-right assistant in the NVGS ticketing dashboard and
  DownloadServer
- A standalone chat page on port `3000`
- A token-gated knowledge manager for `.md`, `.txt`, and `.pdf` files
- A persistent file-backed knowledge index
- Token-free answers for normal matched questions
- Optional AI processing when knowledge is uploaded or reprocessed
- An optional live-AI fallback, disabled by default

The existing logo is served from `frontend/assets/gerry-logo.jpg`.

## How it avoids everyday AI-token use

```text
Approved document uploaded
        |
        v
Text/PDF extraction and sectioning
        |
        +--> deterministic index (always available)
        |
        +--> optional AI cleanup + likely questions (once at processing time)
        |
        v
Saved reusable answers in data/knowledge-index.json
        |
        v
Everyday question --> local matching --> saved answer (no model call)
        |
        +--> no confident match --> safe fallback
                                or optional live AI when explicitly enabled
```

AI is not required. With both AI settings left `false`, Gery extracts and
indexes documents locally and never calls a model.

## Start and stop on Ubuntu

Run the normal one-time setup after pulling this version:

```bash
./scripts/bootstrap-secrets.sh
sudo ./scripts/install-app-controlled-mode.sh
```

Then open **NVGS Server Hub** and choose **Gery Chatbot Server**. Keep its
control terminal open. Closing the terminal stops only Gery and removes the
floating widget after a page refresh.

Direct Compose commands are also available:

```bash
docker compose --profile chatbot up -d --build gerry
docker compose --profile chatbot stop gerry
```

Addresses:

- Standalone chat on Ubuntu: `http://localhost:3000/`
- Standalone chat on the LAN: `http://UBUNTU_IP:3000/`
- Secure manager through NVGS: `https://NVGS_ADDRESS/gerry/admin/`
- Local Ubuntu manager: `http://localhost:3000/admin/`

The manager asks for the value in `secrets/gery_admin_token`. From the NVGS
Server folder on Ubuntu, display it with:

```bash
sudo cat secrets/gery_admin_token
```

If the file is missing, run `./scripts/bootstrap-secrets.sh` once. Remote
knowledge administration is rejected over plain HTTP by default. Ordinary chat
does not need the administrator token.

The public health indicator can report (for example) `4 docs` before the
manager is unlocked. This means the files are indexed; their names and controls
remain hidden until the administrator token is accepted.

## Knowledge storage

Bundled starter documents live in `knowledge/` and are included in the image.
Documents uploaded through the manager live in:

```text
data/uploads/
```

The reusable processed index is:

```text
data/knowledge-index.json
```

The entire `data/` content except `.gitkeep` is ignored by Git. Rebuilding or
stopping the container does not remove it.

## Optional upload-time AI processing

Gery accepts any OpenAI-compatible chat-completions endpoint. LM Studio is the
default local option. Configure the `.env` file in the NVGS Server root (beside
`compose.yaml`):

```dotenv
GERY_INGESTION_AI_ENABLED=true
GERY_AI_BASE_URL=http://host.docker.internal:1234
GERY_AI_MODEL=meta-llama-3.1-8b-instruct
GERY_ALLOW_LIVE_AI=false
```

If the endpoint requires a key, place only the key in:

```text
secrets/gery_ai_api_key
```

For a model running on the Ubuntu host, it must listen on an address reachable
from Docker. Keep access limited to the server/private network and follow the
model server's security guidance.

When upload-time AI is enabled, Gery asks the model to create a concise reusable
answer, likely user questions, and keywords for each section. Those results are
saved. Normal matched chats still do not call the model.

Use **Reprocess all** in the manager after changing the AI-processing setting.
If the model is unavailable, Gery safely falls back to deterministic indexing.

Restart Gery after changing `.env`:

```bash
docker compose --profile chatbot up -d --build gerry
```

## Optional live-AI fallback

`GERY_ALLOW_LIVE_AI=false` is the default and recommended setting for strict
cost control. An unknown question returns a standard “not in current internal
documentation” response.

Setting it to `true` permits only unmatched questions to call the configured
model with the nearest stored context. Responses report whether AI was used.

## Widget availability behavior

Both host applications load a very small local boot script. It checks Gery's
`/health` endpoint with a short timeout. Only a successful health response loads
the actual widget.

- Gery running: floating logo and chat panel appear.
- Gery stopped/unhealthy: no floating button is created.
- Gery stops after the page loaded: the next question reports that the service
  became unavailable; refreshing removes the widget.

NVGS reaches Gery through the same HTTPS origin at `/gerry/`. DownloadServer
uses a same-origin local proxy at `/gerry/`, so the browser does not need to
make cross-origin requests.

## Security defaults

- Knowledge writes require a random bearer token stored as a Docker secret.
- Remote administration requires NVGS HTTPS unless
  `GERY_ALLOW_INSECURE_ADMIN=true` is deliberately set.
- Supported uploads are limited to Markdown, text, and PDF.
- Uploaded filenames cannot contain path separators or hidden-file prefixes.
- The container runs as the unprivileged Node user with a read-only root
  filesystem; only `data/` is writable.
- Answers identify their knowledge source and whether a model was called.

## Development

```bash
cd Chatbot_Gery_the_Robot_Assistant/backend
npm install
npm test
npm start
```

Useful endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service and index health |
| `POST` | `/chat` | Ask a question |
| `GET` | `/admin/` | Knowledge-manager page |
| `GET` | `/admin/knowledge` | List documents; admin token required |
| `POST` | `/admin/knowledge/upload` | Upload/process a document |
| `POST` | `/admin/knowledge/reprocess` | Rebuild all saved answers |
| `DELETE` | `/admin/knowledge/{filename}` | Remove an uploaded document |
