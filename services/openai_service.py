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

