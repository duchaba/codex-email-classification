import base64
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urlparse


class GmailService:
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ]

    def __init__(self, client_secret_file, token_file):
        self.client_secret_file = Path(client_secret_file)
        self.token_file = Path(token_file)

    @property
    def is_configured(self):
        return self.client_secret_file.exists()

    @property
    def is_connected(self):
        return self.token_file.exists()

    @staticmethod
    def _allow_local_oauth_redirect(redirect_uri):
        parsed = urlparse(redirect_uri)
        if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}:
            os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    def get_authorization_url(self, redirect_uri):
        if not self.client_secret_file.exists():
            raise RuntimeError("Google OAuth client_secret.json is missing from the data directory.")
        try:
            from google_auth_oauthlib.flow import Flow
        except ImportError as exc:
            raise RuntimeError("Google API packages are not installed. Run pip install -r requirements.txt.") from exc
        self._allow_local_oauth_redirect(redirect_uri)
        flow = Flow.from_client_secrets_file(str(self.client_secret_file), scopes=self.SCOPES)
        flow.redirect_uri = redirect_uri
        authorization_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return authorization_url, state, flow.code_verifier

    def complete_authorization(self, authorization_response, redirect_uri, state, code_verifier=None):
        from google_auth_oauthlib.flow import Flow

        self._allow_local_oauth_redirect(redirect_uri)
        flow = Flow.from_client_secrets_file(
            str(self.client_secret_file),
            scopes=self.SCOPES,
            state=state,
            code_verifier=code_verifier,
        )
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
        candidates = [payload]
        while candidates:
            part = candidates.pop(0)
            if part.get("mimeType") not in {"text/plain", None}:
                candidates.extend(part.get("parts", []))
                continue
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
            candidates.extend(part.get("parts", []))
        return ""

    @staticmethod
    def _headers(message):
        return {header["name"].lower(): header["value"] for header in message.get("payload", {}).get("headers", [])}

    def _record_from_message(self, message, include_body=False):
        sent_at = datetime.fromtimestamp(int(message["internalDate"]) / 1000).astimezone()
        headers = self._headers(message)
        sender_name, sender_email = parseaddr(headers.get("from", ""))
        body = self._decode_body(message["payload"]) if include_body else ""
        return {
            "email_id": message["id"],
            "date": sent_at.isoformat(),
            "sender_email": sender_email,
            "sender_name": sender_name,
            "subject": headers.get("subject", "(No subject)"),
            "body_preview": message.get("snippet", ""),
            "full_body_optional": body[:5000],
            "source_type": "gmail",
        }

    @staticmethod
    def is_today(timestamp, now=None):
        local_now = now or datetime.now().astimezone()
        return timestamp.astimezone(local_now.tzinfo).date() == local_now.date()

    def fetch_today(self):
        service = self._service()
        local_now = datetime.now().astimezone()
        query = "newer_than:2d"
        records = []
        page_token = None
        while True:
            request = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=500,
                pageToken=page_token,
                includeSpamTrash=True,
            )
            response = request.execute()
            for item in response.get("messages", []):
                records.append(item)
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        today_records = []
        seen = set()
        for item in records:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            message = (
                service.users()
                .messages()
                .get(userId="me", id=item["id"], format="metadata", metadataHeaders=["From", "Subject"])
                .execute()
            )
            sent_at = datetime.fromtimestamp(int(message["internalDate"]) / 1000).astimezone()
            if not self.is_today(sent_at, local_now):
                continue
            today_records.append(self._record_from_message(message, include_body=False))
        return sorted(today_records, key=lambda email: email["date"], reverse=True)

    def fetch_message(self, email_id):
        message = self._service().users().messages().get(userId="me", id=email_id, format="full").execute()
        return self._record_from_message(message, include_body=True)

    def send_email(self, recipient, subject, body):
        recipient = str(recipient or "").strip()
        body = str(body or "").strip()
        if not recipient or "@" not in recipient:
            raise ValueError("A valid recipient email address is required.")
        if not body:
            raise ValueError("The response body cannot be empty.")
        message = MIMEText(body, "plain", "utf-8")
        message["To"] = recipient
        message["Subject"] = subject if str(subject).lower().startswith("re:") else f"Re: {subject}"
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        return self._service().users().messages().send(userId="me", body={"raw": encoded}).execute()
