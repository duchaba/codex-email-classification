import json
from datetime import datetime
from pathlib import Path

from .constants import CATEGORIES


DEFAULT_PROMPT = """You are a careful personal email triage assistant for one person.

Classify every email into exactly one primary category from this five-category list:
{categories}

Primary category precedence, from highest to lowest, is:
Urgent Priority > Work > Personal > Social Media > Spam.
When an email could match more than one primary category, assign only the highest-priority best-fit category. Never return multiple primary categories and never repeat a primary category in secondary_categories.

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
- secondary_categories may contain only descriptive tags or listed subcategories, never any of the five primary category names.
- Do not create any primary category outside the five-category list.
- Return exactly one classification object for each input email_id, with no duplicate or omitted email_id values.
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
        self.decision_path = self.path.with_name("prompt_migration_decision.json")
        self.selection_path = self.path.with_name("prompt_selection.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_versions([])
            self.save(DEFAULT_PROMPT, source="default")

    def _read_versions(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def _write_versions(self, versions):
        self.path.write_text(json.dumps(versions, indent=2), encoding="utf-8")

    def _read_decision(self):
        try:
            return json.loads(self.decision_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_decision(self, decision):
        self.decision_path.write_text(json.dumps(decision, indent=2), encoding="utf-8")

    def _read_selection(self):
        try:
            return json.loads(self.selection_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_selection(self, selection):
        self.selection_path.write_text(json.dumps(selection, indent=2), encoding="utf-8")

    def list_versions(self):
        return self._read_versions()

    def latest(self):
        versions = self._read_versions()
        return versions[-1] if versions else self.save(DEFAULT_PROMPT, source="recovered")

    def _needs_taxonomy_migration(self):
        versions = self._read_versions()
        current = versions[-1].get("prompt", "") if versions else ""
        return "Primary category precedence" not in current or "exactly one classification object" not in current

    def pending_taxonomy_migration(self):
        decision = self._read_decision()
        pending = self._needs_taxonomy_migration() and decision.get("taxonomy_migration") != "rejected"
        return {
            "pending": pending,
            "source": "taxonomy-migration",
            "prompt": DEFAULT_PROMPT if pending else "",
            "message": "A taxonomy prompt update is available. Accept it to create a new taxonomy-migration prompt version, or reject it to keep your current prompt.",
        }

    def accept_taxonomy_migration(self):
        if not self._needs_taxonomy_migration():
            self._write_decision({"taxonomy_migration": "accepted", "decided_at": datetime.now().astimezone().isoformat()})
            return self.get()
        record = self.save(DEFAULT_PROMPT, source="taxonomy-migration")
        self._write_decision({"taxonomy_migration": "accepted", "decided_at": datetime.now().astimezone().isoformat()})
        return record

    def reject_taxonomy_migration(self):
        self._write_decision({"taxonomy_migration": "rejected", "decided_at": datetime.now().astimezone().isoformat()})
        return {"pending": False, "decision": "rejected"}

    def get(self):
        versions = self._read_versions()
        if not versions:
            return self.save(DEFAULT_PROMPT, source="recovered")
        selected_version = self._read_selection().get("version")
        for version in versions:
            if version.get("version") == selected_version:
                return version
        return versions[-1]

    def select_version(self, version):
        versions = self._read_versions()
        for record in versions:
            if record.get("version") == version:
                self._write_selection({"version": version, "selected_at": datetime.now().astimezone().isoformat()})
                return record
        raise ValueError(f"Prompt version {version} was not found.")

    def validate(self, prompt):
        if not prompt or len(prompt.strip()) < 80:
            raise ValueError("Prompt is too short to preserve reliable classification instructions.")
        missing = sorted(field for field in self.REQUIRED_FIELDS if field not in prompt)
        if missing:
            raise ValueError("Prompt must mention required JSON fields: " + ", ".join(missing))

    def save(self, prompt, source="user", activate=False):
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
        if activate:
            self._write_selection({"version": record["version"], "selected_at": datetime.now().astimezone().isoformat()})
        return record

    def reset(self):
        return self.save(DEFAULT_PROMPT, source="reset")
