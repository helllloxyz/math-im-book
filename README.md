# math-im-book

Milestone A backend prototype for the interactive math knowledge system.

## Setup

```bash
python3.10 -m venv .venv
source .venv/bin/activate
env -u ALL_PROXY -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy .venv/bin/pip install -e '.[dev]'
```

## Run tests

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

## Run the API

```bash
.venv/bin/uvicorn math_im_book.api.app:create_app --factory --reload
```

Open `http://127.0.0.1:8000/` for the minimal chat page. It can submit to `/api/ask`, load history from `/api/sessions/{id}`, and show the current knowledge outline, answer references, active symbols, and node detail panel.
The page also keeps a small local recent-sessions list so you can switch between visited chats without waiting for a backend list endpoint.

## Workspace Flow

The refreshed workspace is conversation-led and branch-first:

- ask in the center conversation
- fork from an answer when needed
- browse chapter/node accumulation on the right
- use the left rail to switch branches or inspect chapter placement
- only switch sessions intentionally from the branch tree or related-chat links

## Credentials

Use the frontend settings panel to create credentials, or create `data/credentials/credentials.json` manually with entries like:

```json
{
  "credentials": [
    {
      "credential_id": "gemini-main",
      "api_key": "YOUR_GEMINI_KEY"
    },
    {
      "credential_id": "openai-local",
      "api_key": "YOUR_OPENAI_COMPATIBLE_KEY",
      "headers": {
        "X-Custom-Header": "value"
      }
    }
  ]
}
```

Then send `/api/ask` with a session-scoped provider profile:

```json
{
  "session_id": "chat-1",
  "question": "What is a linear map?",
  "provider_profile": {
    "provider_type": "gemini",
    "model": "gemini-3-flash-preview",
    "credential_id": "gemini-main"
  }
}
```

Supported `provider_type` values:

- `gemini`
- `openai_compatible`

Use `GET /api/credentials` to inspect configured credential IDs without exposing secrets.

Use `POST /api/credentials` to create a credential and `PUT /api/credentials/{credential_id}` to update one. Both endpoints accept `credential_id`, `api_key`, optional `provider_type`, and optional `headers`, and neither returns the secret.

Use `GET /api/provider-options` to inspect the provider/model dropdown configuration served to the frontend. The default config is stored in `data/config/provider_options.json`.

## Available endpoints

- `GET /health`
- `GET /api/credentials`
- `GET /api/provider-options`
- `POST /api/credentials`
- `PUT /api/credentials/{credential_id}`
- `POST /api/ask`
- `GET /api/outline`
- `GET /api/nodes/{node_id}`
