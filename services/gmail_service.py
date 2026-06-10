import base64
from datetime import datetime, timedelta
from email.utils import parseaddr
from pathlib import Path


class GmailService:
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self, client_secret_file, token_file):
        self.client_secret_file = Path(client_secret_file)
        self.token_file = Path(token_file)

    @property
    def is_configured(self):
        return self.client_secret_file.exists()

    @property
    def is_connected(self):
        return self.token_file.exists()

    def get_authorization_url(self, redirect_uri):
        if not self.client_secret_file.exists():
            raise RuntimeError("Google OAuth client_secret.json is missing from the data directory.")
        try:
            from google_auth_oauthlib.flow import Flow
        except ImportError as exc:
            raise RuntimeError("Google API packages are not installed. Run pip install -r requirements.txt.") from exc
        flow = Flow.from_client_secrets_file(str(self.client_secret_file), scopes=self.SCOPES)
        flow.redirect_uri = redirect_uri
        authorization_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return authorization_url, state

    def complete_authorization(self, authorization_response, redirect_uri, state):
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_secrets_file(str(self.client_secret_file), scopes=self.SCOPES, state=state)
        flow.redirect_uri = redirect_uri
        flow.fetch_token(authorization_response=authorization_response)
        self.token_file.write_text(flow.credentials.to_json(), encoding="utf-8")

    def _service(self):
        if not self.token_file.exists():
            raise RuntimeError("Gmail is not connected. Complete OAuth setup first.")
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError("Google API packages are not installed. Run pip install -r requirements.txt.") from exc
        credentials = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        return build("gmail", "v1", credentials=credentials, cache_discovery=False)

    @staticmethod
    def _decode_body(payload):
        parts = payload.get("parts", [])
        candidates = [payload] + parts
        for part in candidates:
            if part.get("mimeType") not in {"text/plain", None}:
                continue
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
        return ""

    @staticmethod
    def is_today(timestamp, now=None):
        local_now = now or datetime.now().astimezone()
        return timestamp.astimezone(local_now.tzinfo).date() == local_now.date()

    def fetch_today(self):
        service = self._service()
        local_now = datetime.now().astimezone()
        today = local_now.date()
        tomorrow = today + timedelta(days=1)
        query = f"after:{today.strftime('%Y/%m/%d')} before:{tomorrow.strftime('%Y/%m/%d')}"
        response = service.users().messages().list(userId="me", q=query, maxResults=500).execute()
        records = []
        for item in response.get("messages", []):
            message = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
            sent_at = datetime.fromtimestamp(int(message["internalDate"]) / 1000).astimezone()
            if not self.is_today(sent_at, local_now):
                continue
            headers = {header["name"].lower(): header["value"] for header in message["payload"].get("headers", [])}
            sender_name, sender_email = parseaddr(headers.get("from", ""))
            body = self._decode_body(message["payload"])
            records.append(
                {
                    "email_id": item["id"],
                    "date": sent_at.isoformat(),
                    "sender_email": sender_email,
                    "sender_name": sender_name,
                    "subject": headers.get("subject", "(No subject)"),
                    "body_preview": message.get("snippet", ""),
                    "full_body_optional": body[:5000],
                    "source_type": "gmail",
                }
            )
        return records
