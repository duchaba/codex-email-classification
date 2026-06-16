import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from agents.category_regroup_agent import CategoryRegroupAgent
from agents.daily_brief_agent import DailyBriefAgent
from agents.ai_email_classifier_agent import AIEmailClassifierAgent
from agents.email_fetch_agent import EmailFetchAgent
from agents.email_preprocess_agent import EmailPreprocessAgent
from agents.email_response_agent import EmailResponseAgent
from agents.ground_truth_test_agent import GroundTruthTestAgent
from agents.mock_email_classifier_agent import MockEmailClassifierAgent
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
    classifier = MockEmailClassifierAgent()
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


def test_primary_category_ties_follow_declared_priority_order():
    classifier = MockEmailClassifierAgent()
    work_over_personal = classifier.classify(
        [sample_email(subject="Client family update")], DEFAULT_PROMPT
    )[0]
    personal_over_social = classifier.classify(
        [sample_email(subject="Family digest")], DEFAULT_PROMPT
    )[0]
    social_over_spam = classifier.classify(
        [sample_email(subject="Digest cash reward")], DEFAULT_PROMPT
    )[0]
    assert work_over_personal["category"] == "Work"
    assert personal_over_social["category"] == "Personal"
    assert social_over_spam["category"] == "Social Media"


def test_daily_brief_uses_ai_and_falls_back_locally():
    class BriefService:
        is_configured = True

        def generate_daily_brief(self, _emails):
            return "Work brought the plot today. One urgent note deserves the first cup of coffee."

    emails = [{"category": "Work"}, {"category": "Urgent Priority"}]
    ai_result = DailyBriefAgent(BriefService()).build(emails, use_ai=True)
    assert ai_result["generated_by"] == "ai"
    assert "first cup of coffee" in ai_result["text"]

    class BrokenBriefService:
        is_configured = True

        def generate_daily_brief(self, _emails):
            raise RuntimeError("brief unavailable")

    fallback = DailyBriefAgent(BrokenBriefService()).build(emails, use_ai=True)
    assert fallback["generated_by"] == "local-fallback"
    assert "2 messages" in fallback["text"]


def test_daily_brief_adds_topic_breaks_when_ai_returns_one_block():
    text = "Work leads the inbox today. One urgent approval needs attention. Start there, then enjoy the quieter messages."
    formatted = DailyBriefAgent._format_for_quick_read(text)
    paragraphs = formatted.split("\n\n")
    assert len(paragraphs) == 2
    assert "Work leads" in paragraphs[0]
    assert "Start there" in paragraphs[1]


def test_email_response_agent_allows_only_actionable_categories():
    class ResponseService:
        is_configured = True

        def generate_email_response(self, email):
            return f"Thanks for your note about {email['subject']}."

    agent = EmailResponseAgent(ResponseService())
    assert "Project update" in agent.draft({"category": "Work", "subject": "Project update"})
    with pytest.raises(ValueError, match="available only"):
        agent.draft({"category": "Social Media", "subject": "Newsletter"})


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


def test_prompt_version_selection_defaults_to_latest(tmp_path):
    manager = PromptManagerAgent(tmp_path / "prompts.json")
    version_two = manager.save(DEFAULT_PROMPT + "\nSecond version.")
    version_three = manager.save(DEFAULT_PROMPT + "\nThird version.")

    assert manager.get()["version"] == version_three["version"]
    assert manager.latest()["version"] == version_three["version"]
    assert [item["version"] for item in manager.list_versions()] == [1, 2, 3]

    selected = manager.select_version(version_two["version"])
    assert selected["version"] == version_two["version"]
    assert manager.get()["version"] == version_two["version"]
    with pytest.raises(ValueError, match="was not found"):
        manager.select_version(999)

    version_four = manager.save(DEFAULT_PROMPT + "\nFourth version.")
    assert manager.get()["version"] == version_two["version"]
    activated = manager.save(DEFAULT_PROMPT + "\nFifth version.", activate=True)
    assert activated["version"] == version_four["version"] + 1
    assert manager.get()["version"] == activated["version"]


def test_taxonomy_migration_requires_manual_accept_or_reject(tmp_path):
    path = tmp_path / "prompts.json"
    path.write_text(
        json.dumps(
            [
                {
                    "version": 1,
                    "prompt": DEFAULT_PROMPT.replace("Primary category precedence", "Primary category order"),
                    "source": "user",
                    "created_at": "2026-06-16T00:00:00-07:00",
                }
            ]
        ),
        encoding="utf-8",
    )

    manager = PromptManagerAgent(path)
    versions = json.loads(path.read_text(encoding="utf-8"))
    assert len(versions) == 1
    assert manager.pending_taxonomy_migration()["pending"] is True

    assert manager.reject_taxonomy_migration()["decision"] == "rejected"
    manager = PromptManagerAgent(path)
    assert manager.pending_taxonomy_migration()["pending"] is False
    assert len(json.loads(path.read_text(encoding="utf-8"))) == 1

    manager.decision_path.unlink()
    accepted = manager.accept_taxonomy_migration()
    assert accepted["source"] == "taxonomy-migration"
    versions = json.loads(path.read_text(encoding="utf-8"))
    assert len(versions) == 2
    assert versions[-1]["source"] == "taxonomy-migration"


def test_email_json_parsing_and_validation(tmp_path):
    path = tmp_path / "emails.json"
    path.write_text(json.dumps([{"sender_email": "a@example.com", "subject": "Hi"}]), encoding="utf-8")
    rows = EmailFetchAgent(tmp_path / "synthetic.json").load_email_json(path, source_type="upload")
    assert rows[0]["source_type"] == "upload"
    assert rows[0]["email_id"].startswith("upload-")

    malformed = tmp_path / "bad.json"
    malformed.write_text(json.dumps([{"sender_name": "A"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required fields"):
        EmailFetchAgent(tmp_path / "synthetic.json").load_email_json(malformed)


def test_preprocess_derives_preview_from_full_body_without_changing_ground_truth():
    source = sample_email(
        body_preview="",
        full_body_optional="Hello there. This is the complete email content for classification.",
        category="",
        subcategory="",
        expected_category="Personal",
        expected_subcategory="Friends",
    )
    result = EmailPreprocessAgent().process([source])[0]
    assert result["body_preview"] == source["full_body_optional"]
    assert result["category"] == ""
    assert result["subcategory"] == ""
    assert result["expected_category"] == "Personal"
    assert result["expected_subcategory"] == "Friends"


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
    classifier = MockEmailClassifierAgent()
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


def test_classifier_cannot_overwrite_ground_truth_fields():
    class FakeOpenAIService:
        is_configured = True

        def classify(self, emails, _prompt):
            return [
                {
                    **emails[0],
                    "category": "Work",
                    "subcategory": "",
                    "body_preview": "Changed by model",
                    "full_body_optional": "Changed by model",
                    "expected_category": "Changed by model",
                    "expected_subcategory": "Changed by model",
                }
            ]

    source = sample_email(
        body_preview="Derived preview",
        full_body_optional="Complete original body",
        expected_category="Personal",
        expected_subcategory="Banking",
    )
    result = AIEmailClassifierAgent(FakeOpenAIService()).classify([source], DEFAULT_PROMPT)[0]
    assert result["expected_category"] == "Personal"
    assert result["expected_subcategory"] == "Banking"
    assert result["body_preview"] == "Derived preview"
    assert result["full_body_optional"] == "Complete original body"


def test_classifier_rejects_multiple_categories_and_duplicate_results():
    class MultipleCategoryService:
        is_configured = True

        def classify(self, emails, _prompt):
            return [{**emails[0], "category": ["Work", "Personal"], "subcategory": ""}]

    with pytest.raises(ValueError, match="one valid primary category"):
        AIEmailClassifierAgent(MultipleCategoryService()).classify(
            [sample_email()], DEFAULT_PROMPT
        )

    class DuplicateService:
        is_configured = True

        def classify(self, emails, _prompt):
            prediction = {**emails[0], "category": "Work", "subcategory": ""}
            return [prediction, dict(prediction)]

    with pytest.raises(ValueError, match="duplicate email_id"):
        AIEmailClassifierAgent(DuplicateService()).classify(
            [sample_email(), sample_email(email_id="two")], DEFAULT_PROMPT
        )


def test_regroup_removes_primary_categories_from_secondary_tags():
    result = CategoryRegroupAgent().process(
        [
            {
                "category": "Personal",
                "subcategory": "Banking",
                "secondary_categories": ["Work", "Banking", "Account Alert"],
                "urgency_level": "low",
            }
        ]
    )[0]
    assert result["category"] == "Personal"
    assert result["secondary_categories"] == ["Account Alert"]


def test_ground_truth_agent_scores_and_builds_comparison_chart():
    source = [
        {"email_id": "1", "subject": "One", "expected_category": "Work", "expected_subcategory": ""},
        {"email_id": "2", "subject": "Two", "expected_category": "Personal", "expected_subcategory": "Banking"},
    ]
    predictions = [
        {"email_id": "1", "category": "Work", "subcategory": ""},
        {"email_id": "2", "category": "Personal", "subcategory": "Friends"},
    ]
    result = GroundTruthTestAgent().evaluate(source, predictions)
    assert result["category_accuracy"] == 1.0
    assert result["subcategory_accuracy"] == 0.5
    assert result["exact_accuracy"] == 0.5
    assert result["chart"]["expected"] == result["chart"]["predicted"]
    assert result["mismatches"][0]["email_id"] == "2"


def test_synthetic_file_is_only_generated_when_missing(tmp_path):
    path = tmp_path / "synthetic.json"
    agent = EmailFetchAgent(path)
    generated = agent.load_synthetic()
    assert len(generated) == 200

    custom = [{"email_id": "kept", "sender_email": "test@example.com", "subject": "Keep me"}]
    path.write_text(json.dumps(custom), encoding="utf-8")
    loaded = agent.load_synthetic()
    assert loaded[0]["email_id"] == "kept"
    assert loaded[0]["sender_email"] == "test@example.com"
    assert loaded[0]["subject"] == "Keep me"
    assert loaded[0]["source_type"] == "synthetic"
    assert loaded[0]["date"]


def test_today_only_filter_respects_local_day():
    local_tz = timezone(timedelta(hours=-7))
    now = datetime(2026, 6, 9, 23, 30, tzinfo=local_tz)
    same_local_day_utc = datetime(2026, 6, 10, 4, 0, tzinfo=timezone.utc)
    next_local_day = datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc)
    assert GmailService.is_today(same_local_day_utc, now)
    assert not GmailService.is_today(next_local_day, now)


def test_gmail_fetch_today_uses_broad_query_pagination_and_local_filter(tmp_path):
    local_tz = datetime.now().astimezone().tzinfo
    now = datetime(2026, 6, 16, 12, 0, tzinfo=local_tz)
    older = now - timedelta(days=1)
    body = base64.urlsafe_b64encode(b"Full body text").decode("ascii").rstrip("=")

    def message(message_id, sent_at, subject):
        return {
            "id": message_id,
            "internalDate": str(int(sent_at.timestamp() * 1000)),
            "snippet": f"Snippet {subject}",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Sender Name <sender@example.com>"},
                    {"name": "Subject", "value": subject},
                ],
                "mimeType": "text/plain",
                "body": {"data": body},
            },
        }

    messages_by_id = {
        "newer": message("newer", now, "Newest"),
        "older-today": message("older-today", now - timedelta(hours=2), "Older today"),
        "yesterday": message("yesterday", older, "Yesterday"),
    }

    class ListCall:
        def __init__(self, outer, page_token):
            self.outer = outer
            self.page_token = page_token

        def execute(self):
            if self.page_token == "page-2":
                return {"messages": [{"id": "older-today"}, {"id": "newer"}]}
            return {"messages": [{"id": "yesterday"}, {"id": "newer"}], "nextPageToken": "page-2"}

    class GetCall:
        def __init__(self, message_id):
            self.message_id = message_id

        def execute(self):
            return messages_by_id[self.message_id]

    class Messages:
        def __init__(self):
            self.list_calls = []

        def list(self, **kwargs):
            self.list_calls.append(kwargs)
            return ListCall(self, kwargs.get("pageToken"))

        def get(self, userId, id, format, metadataHeaders=None):
            assert userId == "me"
            if format == "metadata":
                assert metadataHeaders == ["From", "Subject"]
            return GetCall(id)

    messages = Messages()
    users = type("Users", (), {"messages": lambda self: messages})()
    service_api = type("Service", (), {"users": lambda self: users})()
    service = GmailService(tmp_path / "client.json", tmp_path / "token.json")
    service._service = lambda: service_api

    records = service.fetch_today()

    assert [call["q"] for call in messages.list_calls] == ["newer_than:2d", "newer_than:2d"]
    assert all(call["includeSpamTrash"] is True for call in messages.list_calls)
    assert [record["email_id"] for record in records] == ["newer", "older-today"]
    assert records[0]["subject"] == "Newest"
    assert records[0]["sender_name"] == "Sender Name"
    assert records[0]["full_body_optional"] == ""

    full_record = service.fetch_message("newer")
    assert full_record["full_body_optional"] == "Full body text"


def test_gmail_send_builds_reply_message(tmp_path):
    class SendCall:
        def __init__(self):
            self.body = None

        def send(self, userId, body):
            assert userId == "me"
            self.body = body
            return self

        def execute(self):
            return {"id": "sent-123"}

    call = SendCall()
    messages = type("Messages", (), {"send": call.send})()
    users = type("Users", (), {"messages": lambda self: messages})()
    service_api = type("Service", (), {"users": lambda self: users})()
    service = GmailService(tmp_path / "client.json", tmp_path / "token.json")
    service._service = lambda: service_api

    result = service.send_email("person@example.com", "Hello", "Thanks for the update.")

    assert result["id"] == "sent-123"
    decoded = base64.urlsafe_b64decode(call.body["raw"]).decode("utf-8")
    assert "To: person@example.com" in decoded
    assert "Subject: Re: Hello" in decoded
