# Inbox Atelier

A local, single-user email classification dashboard. It includes a tracked synthetic fixture and can switch to an email JSON upload or today's Gmail inbox. Mock classification works without external credentials.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`.

At startup the app loads the synthetic fixture but does not classify it automatically. Click **Classify emails** on the dashboard when you are ready to run the mock rules or configured AI model.

The **Test Ground Truth** tool compares the already saved synthetic predictions with `expected_category` and `expected_subcategory`. It never runs classification again and never changes the expected labels.

## Data modes

- **Synthetic demo:** the tracked `data/synthetic_emails.json` fixture contains 50 AI-generated full-body emails. Raw prediction fields are blank; `expected_category` and `expected_subcategory` provide evaluation ground truth and are not sent to or read by the classifier. The app generates the original fallback fixture automatically only when the file is missing.
- When a raw email has a blank `body_preview`, clicking **Classify emails** derives the preview from `full_body_optional` before running mock or AI classification. The derived preview and predicted labels are saved in local classification state, not written back into the tracked raw fixture.
- **Uploaded email JSON:** accepts a non-empty JSON array with `sender_email` and `subject` on every email object. Other supported fields include `email_id`, `date`, `sender_name`, `body_preview`, and `full_body_optional`. Uploading loads the raw messages; click **Classify emails** to run mock or AI classification.
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
