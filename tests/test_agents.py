import csv
import json
from datetime import datetime, timedelta, timezone

import pytest

from agents.category_regroup_agent import CategoryRegroupAgent
from agents.email_classifier_agent import EmailClassifierAgent
from agents.email_fetch_agent import EmailFetchAgent
from agents.prompt_manager_agent import DEFAULT_PROMPT, PromptManagerAgent
from services.gmail_service import GmailService


def sample_email(**overrides):
    email = {
        "email_id": "one",
        "date": datetime.now().astimezone().isoformat(),
        "sender_email": "person@example.com",
        "sender_name": "Person",
        "subject": "Hello",
        "body_preview": "A normal message.",
        "source_type": "test",
    }
    email.update(overrides)
    return email


def test_urgent_work_and_social_marketing_rules():
    classifier = EmailClassifierAgent(mock_mode=True)
    priority = classifier.classify(
        [sample_email(sender_email="coach@elvtr.com", subject="Launch review needed today")], DEFAULT_PROMPT
    )[0]
    marketing = classifier.classify(
        [sample_email(subject="Save 25% today", body_preview="Upgrade now for this discount offer.")], DEFAULT_PROMPT
    )[0]
    assert priority["category"] == "Urgent Priority"
    assert priority["subcategory"] == "Work"
    assert priority["urgency_level"] == "high"
    assert marketing["category"] == "Social Media"
    assert marketing["subcategory"] == "Sales & Marketing"


def test_legacy_categories_become_primary_and_subcategory():
    regrouped = CategoryRegroupAgent().process(
        [
            {"category": "Bills & Utilities", "urgency_level": "low"},
            {"category": "News & Releases", "urgency_level": "low"},
            {"category": "Friends", "urgency_level": "high"},
        ]
    )
    assert regrouped[0]["category"] == "Personal"
    assert regrouped[0]["subcategory"] == "Bills & Utilities"
    assert regrouped[1]["category"] == "Social Media"
    assert regrouped[1]["subcategory"] == "News & Releases"
    assert regrouped[2]["category"] == "Urgent Priority"
    assert regrouped[2]["subcategory"] == "Friends"


def test_prompt_load_edit_and_reset(tmp_path):
    manager = PromptManagerAgent(tmp_path / "prompts.json")
    assert manager.get()["version"] == 1
    assert "Urgent Priority" in manager.get()["prompt"]
    assert "subcategory" in manager.get()["prompt"]
    edited = DEFAULT_PROMPT + "\nBe concise in every reason."
    assert manager.save(edited)["version"] == 2
    reset = manager.reset()
    assert reset["version"] == 3
    assert reset["prompt"] == DEFAULT_PROMPT.strip()
    with pytest.raises(ValueError):
        manager.save("Classify this")


def test_csv_parsing_and_validation(tmp_path):
    path = tmp_path / "emails.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sender_email", "subject", "body_preview"])
        writer.writeheader()
        writer.writerow({"sender_email": "a@example.com", "subject": "Hi", "body_preview": "Hello"})
    rows = EmailFetchAgent(tmp_path / "synthetic.json").load_csv(path)
    assert rows[0]["source_type"] == "upload"
    assert rows[0]["email_id"].startswith("upload-")

    malformed = tmp_path / "bad.csv"
    malformed.write_text("name,body\nA,Hello\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        EmailFetchAgent(tmp_path / "synthetic.json").load_csv(malformed)


def test_synthetic_email_creation_is_deterministic(tmp_path):
    agent = EmailFetchAgent(tmp_path / "synthetic.json")
    records = agent.create_synthetic(200)
    assert len(records) == 200
    assert len({record["email_id"] for record in records}) == 200
    assert {record["source_type"] for record in records} == {"synthetic"}
    assert {record["category"] for record in records} == {""}
    assert {record["subcategory"] for record in records} == {""}
    assert all(record["expected_category"] for record in records)
    assert agent.load_synthetic()[0] == records[0]


def test_expected_labels_do_not_influence_classification():
    classifier = EmailClassifierAgent(mock_mode=True)
    email = sample_email(
        subject="Save 25% on your annual plan",
        body_preview="Upgrade now to receive this discount offer.",
        category="",
        subcategory="",
        expected_category="Spam",
        expected_subcategory="",
    )
    classified = classifier.classify([email], DEFAULT_PROMPT)[0]
    assert classified["category"] == "Social Media"
    assert classified["subcategory"] == "Sales & Marketing"


def test_synthetic_file_is_only_generated_when_missing(tmp_path):
    path = tmp_path / "synthetic.json"
    agent = EmailFetchAgent(path)
    generated = agent.load_synthetic()
    assert len(generated) == 200

    custom = [{"email_id": "kept", "sender_email": "test@example.com", "subject": "Keep me"}]
    path.write_text(json.dumps(custom), encoding="utf-8")
    assert agent.load_synthetic() == custom


def test_today_only_filter_respects_local_day():
    local_tz = timezone(timedelta(hours=-7))
    now = datetime(2026, 6, 9, 23, 30, tzinfo=local_tz)
    same_local_day_utc = datetime(2026, 6, 10, 4, 0, tzinfo=timezone.utc)
    next_local_day = datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc)
    assert GmailService.is_today(same_local_day_utc, now)
    assert not GmailService.is_today(next_local_day, now)
