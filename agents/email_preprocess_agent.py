from datetime import datetime


class EmailPreprocessAgent:
    @staticmethod
    def _build_preview(body, limit=700):
        normalized = " ".join(str(body or "").split())
        if len(normalized) <= limit:
            return normalized
        shortened = normalized[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
        return shortened + "..."

    def process(self, emails):
        normalized = []
        seen = set()
        for index, email in enumerate(emails):
            sender_email = str(email.get("sender_email") or "unknown@example.com").strip().lower()
            subject = " ".join(str(email.get("subject") or "(No subject)").split())
            timestamp = email.get("date") or datetime.now().astimezone().isoformat()
            full_body = str(email.get("full_body_optional") or "")
            body_preview = " ".join(str(email.get("body_preview") or "").split())[:700]
            if not body_preview:
                body_preview = self._build_preview(full_body)
            dedupe_key = email.get("email_id") or f"{sender_email}|{subject}|{timestamp}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(
                {
                    **email,
                    "email_id": str(email.get("email_id") or f"email-{index + 1}"),
                    "date": timestamp,
                    "sender_email": sender_email,
                    "sender_name": str(email.get("sender_name") or "").strip(),
                    "subject": subject,
                    "body_preview": body_preview,
                    "full_body_optional": full_body,
                    "source_type": str(email.get("source_type") or "unknown"),
                }
            )
        return normalized
