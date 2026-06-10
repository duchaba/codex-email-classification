import json
from datetime import datetime
from pathlib import Path

from .constants import CATEGORIES


DEFAULT_PROMPT = """You are a careful personal email triage assistant for one person.

Classify every email into exactly one primary category from this five-category list:
{categories}

Primary category rules:
- Urgent Priority: work or personal email requiring immediate or time-sensitive action. Use only when urgency_level is high.
- Work: professional, employment, client, course, or business email that is not highly urgent. Relevant ELVTR.com and genai-incubator.com messages are Work unless highly urgent.
- Personal: personal life, family, finances, projects, bills, banking, and friends unless highly urgent.
- Social Media: social platforms, newsletters, releases, promotions, marketing, invitations, and events.
- Spam: suspicious, deceptive, malicious, or clearly unwanted email.

Subcategory rules:
- Under Social Media, use News & Releases, Sales & Marketing, or Invitations & Events when applicable.
- Under Personal, use Bills & Utilities, Personal Projects, Banking, or Friends when applicable.
- For Urgent Priority, preserve the best underlying Work or Personal subcategory.
- Use an empty string when no listed subcategory applies.
- Detect overlap and preserve any additional useful labels in secondary_categories.
- Do not create any primary category outside the five-category list.
- Return strict JSON only. Do not use Markdown fences.

Return either one object or an array of objects with these exact fields:
category, subcategory, secondary_categories, one_sentence_summary, confidence_score, reason, urgency_level.
confidence_score must be a number from 0.00 to 1.00. urgency_level must be low, medium, or high.
""".format(categories=", ".join(CATEGORIES))


class PromptManagerAgent:
    REQUIRED_FIELDS = {
        "category",
        "subcategory",
        "secondary_categories",
        "one_sentence_summary",
        "confidence_score",
        "reason",
        "urgency_level",
    }

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_versions([])
            self.save(DEFAULT_PROMPT, source="default")
        else:
            versions = self._read_versions()
            current = versions[-1].get("prompt", "") if versions else ""
            if "subcategory" not in current or "Urgent Priority" not in current:
                self.save(DEFAULT_PROMPT, source="taxonomy-migration")

    def _read_versions(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def _write_versions(self, versions):
        self.path.write_text(json.dumps(versions, indent=2), encoding="utf-8")

    def get(self):
        versions = self._read_versions()
        return versions[-1] if versions else self.save(DEFAULT_PROMPT, source="recovered")

    def validate(self, prompt):
        if not prompt or len(prompt.strip()) < 80:
            raise ValueError("Prompt is too short to preserve reliable classification instructions.")
        missing = sorted(field for field in self.REQUIRED_FIELDS if field not in prompt)
        if missing:
            raise ValueError("Prompt must mention required JSON fields: " + ", ".join(missing))

    def save(self, prompt, source="user"):
        self.validate(prompt)
        versions = self._read_versions()
        record = {
            "version": len(versions) + 1,
            "prompt": prompt.strip(),
            "source": source,
            "created_at": datetime.now().astimezone().isoformat(),
        }
        versions.append(record)
        self._write_versions(versions)
        return record

    def reset(self):
        return self.save(DEFAULT_PROMPT, source="reset")
