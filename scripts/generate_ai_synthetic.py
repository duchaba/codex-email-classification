import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.constants import CATEGORIES  # noqa: E402
from config import Config  # noqa: E402


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "data" / "synthetic_emails.json"
ALLOWED_SUBCATEGORIES = {
    "",
    "Work",
    "News & Releases",
    "Sales & Marketing",
    "Invitations & Events",
    "Bills & Utilities",
    "Personal Projects",
    "Banking",
    "Friends",
}

SYSTEM_PROMPT = """Create realistic synthetic personal inbox emails for classifier evaluation.
Return strict JSON as an array only, with no Markdown.

Each object must contain:
sender_email, sender_name, subject, full_body_optional, expected_category, expected_subcategory.

Rules:
- Write the complete realistic email content in full_body_optional. Length may vary naturally by email type.
- Do not include real secrets, account numbers, phone numbers, or sensitive personal data.
- Primary categories are exactly: Urgent Priority, Work, Personal, Social Media, Spam.
- Precedence is Urgent Priority > Work > Personal > Social Media > Spam.
- Urgent Priority is only time-sensitive Work or Personal email and must use Work or the best Personal subcategory.
- Social Media subcategories: News & Releases, Sales & Marketing, Invitations & Events, or empty.
- Personal subcategories: Bills & Utilities, Personal Projects, Banking, Friends, or empty.
- Work and Spam normally use an empty subcategory.
- Make category evidence clear enough to serve as reliable ground truth while varying tone, sender, and topic.
- Include a balanced mixture of categories and subcategories across the requested batch.
"""


def parse_json(text):
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json") :]
    if cleaned.endswith("```"):
        cleaned = cleaned[: -len("```")]
    result = json.loads(cleaned.strip())
    if not isinstance(result, list):
        raise ValueError("AI output must be a JSON array.")
    return result


def validate(item):
    required = {
        "sender_email",
        "sender_name",
        "subject",
        "full_body_optional",
        "expected_category",
        "expected_subcategory",
    }
    missing = required - set(item)
    if missing:
        raise ValueError("AI record is missing: " + ", ".join(sorted(missing)))
    if item["expected_category"] not in CATEGORIES:
        raise ValueError(f"Invalid expected category: {item['expected_category']}")
    if item["expected_subcategory"] not in ALLOWED_SUBCATEGORIES:
        raise ValueError(f"Invalid expected subcategory: {item['expected_subcategory']}")
    valid_pairs = {
        "Urgent Priority": {"Work", "Bills & Utilities", "Personal Projects", "Banking", "Friends"},
        "Work": {""},
        "Personal": {"", "Bills & Utilities", "Personal Projects", "Banking", "Friends"},
        "Social Media": {"", "News & Releases", "Sales & Marketing", "Invitations & Events"},
        "Spam": {""},
    }
    if item["expected_subcategory"] not in valid_pairs[item["expected_category"]]:
        raise ValueError(
            f"Invalid category/subcategory pair: {item['expected_category']} / {item['expected_subcategory']}"
        )
    if len(str(item["full_body_optional"]).strip()) < 80:
        raise ValueError("AI email body is too short to be substantive.")


def generate_batch(client, model, count, batch_number):
    request = (
        f"Generate {count} new emails for batch {batch_number}. Include varied examples across all primary "
        "categories and requested subcategories. Avoid repeating common examples such as generic utility bills, "
        "LinkedIn search notices, or obvious lottery spam."
    )
    last_error = None
    for attempt in range(3):
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": request},
                ],
                temperature=0.8,
            )
            records = parse_json(response.output_text)
            if len(records) != count:
                raise ValueError(f"Expected {count} AI records, received {len(records)}.")
            for record in records:
                validate(record)
            return records
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    raise RuntimeError(f"Synthetic generation failed after retries: {last_error}")


def main():
    if not Config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured locally.")
    existing = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if len(existing) != 200:
        raise RuntimeError(f"Expected 200 existing records before append; found {len(existing)}.")

    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    generated = []
    for batch_number in range(1, 6):
        generated.extend(generate_batch(client, Config.OPENAI_MODEL, 10, batch_number))

    existing_subjects = {str(record.get("subject", "")).casefold() for record in existing}
    new_subjects = set()
    base_time = datetime.now().astimezone().replace(hour=7, minute=0, second=0, microsecond=0)
    records = []
    for offset, item in enumerate(generated, start=1):
        subject_key = str(item["subject"]).casefold()
        if subject_key in existing_subjects or subject_key in new_subjects:
            raise RuntimeError(f"Duplicate generated subject: {item['subject']}")
        new_subjects.add(subject_key)
        records.append(
            {
                "email_id": f"demo-{200 + offset:04d}",
                "date": (base_time + timedelta(minutes=offset * 11)).isoformat(),
                "sender_email": str(item["sender_email"]).strip().lower(),
                "sender_name": str(item["sender_name"]).strip(),
                "subject": str(item["subject"]).strip(),
                "body_preview": "",
                "full_body_optional": str(item["full_body_optional"]).strip(),
                "category": "",
                "subcategory": "",
                "expected_category": item["expected_category"],
                "expected_subcategory": item["expected_subcategory"],
                "summary": "",
                "confidence_score": "",
                "source_type": "synthetic-ai",
            }
        )

    DATA_FILE.write_text(json.dumps(existing + records, indent=2), encoding="utf-8")
    print(f"Appended {len(records)} AI-generated emails to {DATA_FILE}")


if __name__ == "__main__":
    main()
