import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path


class EmailFetchAgent:
    REQUIRED_CSV_FIELDS = {"sender_email", "subject"}

    TEMPLATES = [
        ("Urgent Priority", "Work", "Maya Chen", "maya@elvtr.com", "Course launch review needed", "Please review the launch checklist and reply before 3 PM today."),
        ("Urgent Priority", "Work", "Alex Rivera", "alex@genai-incubator.com", "Mentor session action items", "Two decisions need your approval before tomorrow's mentor session."),
        ("Social Media", "", "LinkedIn", "messages-noreply@linkedin.com", "You appeared in 8 searches", "Your weekly profile activity and network highlights are ready."),
        ("Social Media", "News & Releases", "AI Brief", "daily@aibrief.news", "Open model releases this week", "A concise roundup of new AI models, papers, and product releases."),
        ("Social Media", "Sales & Marketing", "Notion", "team@mail.notion.so", "Save 25% on Notion AI", "Upgrade this week to receive an annual plan discount."),
        ("Urgent Priority", "Bills & Utilities", "City Power", "billing@citypower.example", "Your electric bill is due", "A payment of $84.27 is due in five days."),
        ("Social Media", "Invitations & Events", "Events Team", "invite@lu.ma", "Invitation: Practical Agents Meetup", "You are invited to an evening meetup next Thursday."),
        ("Personal", "Personal Projects", "Kickstarter", "no-reply@kickstarter.com", "A project you backed posted an update", "The creator shared manufacturing progress and a new ship date."),
        ("Personal", "Personal Projects", "UNO Alumni", "alumni@uno.edu", "Alumni author spotlight", "Submit your recent book or creative project for the alumni newsletter."),
        ("Personal", "Banking", "Harbor Bank", "alerts@harborbank.example", "Card purchase notification", "A $42.10 card purchase was posted to your account."),
        ("Personal", "Friends", "Jordan", "jordan@example.net", "Dinner this weekend?", "Are you free Saturday for dinner with the old group?"),
        ("Personal", "", "Family Calendar", "calendar@example.org", "Family appointment reminder", "Reminder that the dental appointment is at 10 AM Friday."),
        ("Spam", "", "Prize Desk", "winner@claim-now.example", "URGENT: Claim your cash reward", "You were selected. Send your bank details now to claim funds."),
        ("Personal", "", "Unknown Sender", "contact@misc-example.com", "Quick question", "Hello, I wanted to connect about an unspecified opportunity."),
    ]

    def __init__(self, synthetic_path, gmail_service=None):
        self.synthetic_path = Path(synthetic_path)
        self.gmail_service = gmail_service

    def create_synthetic(self, count=200):
        randomizer = random.Random(20260609)
        now = datetime.now().astimezone()
        records = []
        for index in range(count):
            category, subcategory, name, sender, subject, preview = self.TEMPLATES[index % len(self.TEMPLATES)]
            minute_offset = randomizer.randint(0, 16 * 60)
            sent_at = now.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(minutes=minute_offset)
            records.append(
                {
                    "email_id": f"demo-{index + 1:04d}",
                    "date": sent_at.isoformat(),
                    "sender_email": sender,
                    "sender_name": name,
                    "subject": f"{subject}{' #' + str(index + 1) if index >= len(self.TEMPLATES) else ''}",
                    "body_preview": preview,
                    "full_body_optional": "",
                    "category": "",
                    "subcategory": "",
                    "expected_category": category,
                    "expected_subcategory": subcategory,
                    "summary": "",
                    "confidence_score": "",
                    "source_type": "synthetic",
                }
            )
        self.synthetic_path.parent.mkdir(parents=True, exist_ok=True)
        self.synthetic_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        return records

    def load_synthetic(self):
        if not self.synthetic_path.exists():
            return self.create_synthetic()
        try:
            records = json.loads(self.synthetic_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Synthetic email file contains invalid JSON: {exc}") from exc
        if not isinstance(records, list) or not records:
            raise ValueError("Synthetic email file must contain a non-empty JSON array.")
        return records

    def load_csv(self, file_path):
        with Path(file_path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("CSV has no header row.")
            missing = self.REQUIRED_CSV_FIELDS - set(reader.fieldnames)
            if missing:
                raise ValueError("CSV is missing required columns: " + ", ".join(sorted(missing)))
            rows = [dict(row) for row in reader if any(str(value).strip() for value in row.values())]
        if not rows:
            raise ValueError("CSV contains no email rows.")
        for index, row in enumerate(rows):
            row.setdefault("email_id", f"upload-{index + 1:04d}")
            row.setdefault("date", datetime.now().astimezone().isoformat())
            row["source_type"] = "upload"
        return rows

    def load_gmail_today(self):
        if not self.gmail_service:
            raise RuntimeError("Gmail service is not configured.")
        return self.gmail_service.fetch_today()
