# Inbox Atelier

A local, single-user email classification dashboard. It starts with 200 deterministic synthetic emails and can switch to a CSV upload or today's Gmail inbox. Mock classification works without external credentials.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`.

## Data modes

- **Synthetic demo:** the tracked `data/synthetic_emails.json` fixture contains 200 records. The app generates it automatically only when the file is missing.
- **Uploaded CSV:** requires at least 200 rows and the columns `sender_email` and `subject`. Other supported columns include `email_id`, `date`, `sender_name`, `body_preview`, and `full_body_optional`.
- **Live Gmail:** fetches only messages whose timestamps fall on the current local calendar day.

## Optional OpenAI setup

Enter an API key in the dashboard setup dialog, or copy `.env.example` to `.env` and set `OPENAI_API_KEY`. Without a key, the app uses deterministic local rules. Local secrets and tokens are excluded by `.gitignore`.

## Optional Gmail setup

1. Create a Google Cloud OAuth client with application type **Desktop app** and enable the Gmail API.
2. Download the credentials as `data/client_secret.json`.
3. Install dependencies and click **Connect Gmail** in Setup.
4. Add `http://127.0.0.1:5000/oauth2/callback` as an authorized redirect URI if your OAuth client requires it.

The app requests read-only Gmail access and stores the OAuth token locally in `data/token.json`.

## Tests

```bash
pytest -q
```
