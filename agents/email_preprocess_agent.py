from datetime import datetime


class EmailPreprocessAgent:
    def process(self, emails):
        normalized = []
        seen = set()
        for index, email in enumerate(emails):
            sender_email = str(email.get("sender_email") or "unknown@example.com").strip().lower()
            subject = " ".join(str(email.get("subject") or "(No subject)").split())
            timestamp = email.get("date") or datetime.now().astimezone().isoformat()
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
                    "body_preview": " ".join(str(email.get("body_preview") or "").split())[:700],
                    "full_body_optional": str(email.get("full_body_optional") or ""),
                    "source_type": str(email.get("source_type") or "unknown"),
                }
            )
        return normalized

