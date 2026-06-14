import json
import time


class OpenAIService:
    def __init__(self, api_key="", model="gpt-4.1-mini"):
        self.api_key = api_key
        self.model = model

    @property
    def is_configured(self):
        return bool(self.api_key)

    def classify(self, emails, prompt):
        if not self.api_key:
            raise RuntimeError("OpenAI API key is missing. Add it in Setup or enable mock mode.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is not installed. Run pip install -r requirements.txt.") from exc

        client = OpenAI(api_key=self.api_key)
        results = []
        for start in range(0, len(emails), 20):
            batch = emails[start : start + 20]
            payload = [
                {
                    "email_id": email["email_id"],
                    "sender_email": email["sender_email"],
                    "sender_name": email.get("sender_name", ""),
                    "subject": email["subject"],
                    "body_preview": email.get("body_preview", ""),
                    "full_body_optional": email.get("full_body_optional", "")[:5000],
                }
                for email in batch
            ]
            last_error = None
            for attempt in range(3):
                try:
                    response = client.responses.create(
                        model=self.model,
                        input=[
                            {"role": "system", "content": prompt},
                            {
                                "role": "user",
                                "content": "Classify these emails. Preserve email_id in every result:\n" + json.dumps(payload),
                            },
                        ],
                        temperature=0.1,
                    )
                    parsed = json.loads(response.output_text)
                    parsed = parsed if isinstance(parsed, list) else [parsed]
                    by_id = {item.get("email_id"): item for item in parsed}
                    for email in batch:
                        classification = by_id.get(email["email_id"])
                        if not classification:
                            raise ValueError(f"Model omitted email_id {email['email_id']}.")
                        results.append(
                            {
                                **email,
                                **classification,
                                "primary_category": classification.get("category"),
                                "summary": classification.get("one_sentence_summary", ""),
                                "classification_reason": classification.get("reason", ""),
                            }
                        )
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(2**attempt)
            else:
                raise RuntimeError(f"OpenAI classification failed after retries: {last_error}")
        return results

    def generate_daily_brief(self, emails):
        if not self.api_key:
            raise RuntimeError("OpenAI API key is missing.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is not installed. Run pip install -r requirements.txt.") from exc

        payload = [
            {
                "category": email.get("category", ""),
                "subcategory": email.get("subcategory", ""),
                "urgency_level": email.get("urgency_level", ""),
                "subject": email.get("subject", "")[:180],
                "summary": (email.get("summary") or email.get("one_sentence_summary") or "")[:300],
            }
            for email in emails
        ]
        response = OpenAI(api_key=self.api_key).responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Write a concise daily inbox briefing as two or three short topic paragraphs. "
                        "Put one blank line between every paragraph so a reader can scan it quickly. "
                        "Use the first paragraph for the inbox overview, the next for urgent or important themes, "
                        "and an optional final paragraph for the suggested next focus. "
                        "Use a witty, warm, easy-to-read style without being silly. "
                        "Stay under 110 words. Do not use headings, bullets, markdown, or invented facts."
                    ),
                },
                {"role": "user", "content": "Summarize these classified emails:\n" + json.dumps(payload)},
            ],
            temperature=0.7,
        )
        text = response.output_text.strip()
        if not text:
            raise ValueError("OpenAI returned an empty daily brief.")
        return text

    def generate_email_response(self, email):
        if not self.api_key:
            raise RuntimeError("OpenAI API key is missing.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is not installed. Run pip install -r requirements.txt.") from exc

        payload = {
            "sender_name": email.get("sender_name", ""),
            "sender_email": email.get("sender_email", ""),
            "subject": email.get("subject", ""),
            "body": email.get("full_body_optional") or email.get("body_preview", ""),
            "category": email.get("category", ""),
            "subcategory": email.get("subcategory", ""),
            "urgency_level": email.get("urgency_level", ""),
        }
        response = OpenAI(api_key=self.api_key).responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Draft a clear, concise email reply for the user. Match the sender's tone and the message's urgency. "
                        "Be warm and professional, directly address the request, and avoid inventing commitments, dates, "
                        "facts, attachments, or personal details. If essential information is missing, use a short bracketed "
                        "placeholder. Return only the email body with short readable paragraphs; no subject line or markdown."
                    ),
                },
                {"role": "user", "content": "Draft a response to this email:\n" + json.dumps(payload)},
            ],
            temperature=0.5,
        )
        text = response.output_text.strip()
        if not text:
            raise ValueError("OpenAI returned an empty response draft.")
        return text
