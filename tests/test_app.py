import io
import json
from datetime import datetime

import pytest

from app import create_app
from config import resolve_app_version


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATA_DIR": tmp_path,
            "MOCK_MODE": True,
            "GOOGLE_CLIENT_SECRET_FILE": str(tmp_path / "client_secret.json"),
        }
    )
    return app.test_client()


def test_dashboard_loads_raw_emails_without_classifying_at_startup(client):
    response = client.get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'id="processedStatButton"' in page
    assert 'id="topCategoryStatButton"' in page
    assert 'id="attentionStatButton"' in page
    assert 'id="reviewStatButton"' in page
    status = client.get("/api/status").get_json()
    assert status["summary"]["total"] == 0
    assert status["pending_count"] == 200
    assert status["status"] == "awaiting_classification"
    assert status["mode"] == "synthetic"
    expected_version = resolve_app_version()
    assert status["app_version"] == expected_version
    assert "Original Author" in page
    assert "Duc Haba" in page
    assert "GNU GPL 3.0" in page
    assert f"v{expected_version}" in page
    assert [category["name"] for category in status["categories"]] == [
        "Urgent Priority",
        "Work",
        "Personal",
        "Social Media",
        "Spam",
    ]
    assert status["chart"]["labels"] == []


def test_user_can_classify_loaded_startup_emails(client):
    response = client.post("/api/rerun")
    assert response.status_code == 200
    result = response.get_json()
    assert result["status"] == "complete"
    assert result["summary"]["total"] == 200
    assert result["pending_count"] == 0
    assert result["daily_brief"]["generated_by"] == "local"
    assert result["daily_brief"]["text"]
    assert sum(category["count"] for category in result["categories"]) == 200
    assert len({email["email_id"] for email in result["emails"]}) == 200
    assert all(isinstance(email["category"], str) for email in result["emails"])
    timestamps = [datetime.fromisoformat(email["date"]).timestamp() for email in result["emails"]]
    assert timestamps == sorted(timestamps, reverse=True)

    actionable = next(email for email in result["emails"] if email["category"] in {"Urgent Priority", "Work", "Personal"})
    raw = client.get(f"/api/email/{actionable['email_id']}/raw")
    assert raw.status_code == 200
    raw_result = raw.get_json()
    assert raw_result["email_id"] == actionable["email_id"]
    assert "expected_category" not in raw_result

    excluded = next(email for email in result["emails"] if email["category"] in {"Social Media", "Spam"})
    assert client.get(f"/api/email/{excluded['email_id']}/raw").status_code == 403
    assert client.post(f"/api/email/{excluded['email_id']}/draft-response").status_code == 403

    saved = client.post(
        f"/api/email/{actionable['email_id']}/save-response",
        json={"draft": "Thanks for the note."},
    )
    assert saved.status_code == 200
    assert client.get("/api/status").get_json()["response_drafts"][actionable["email_id"]] == "Thanks for the note."

    send = client.post(
        f"/api/email/{actionable['email_id']}/send-response",
        json={"draft": "Thanks for the note."},
    )
    assert send.status_code == 409
    assert "live Gmail" in send.get_json()["error"]


def test_email_listing_sorts_latest_first_and_invalid_dates_last(client):
    emails = [
        {"email_id": "old", "sender_email": "a@example.com", "subject": "Old", "date": "2026-06-10T08:00:00-07:00"},
        {"email_id": "invalid", "sender_email": "b@example.com", "subject": "Invalid", "date": "not-a-date"},
        {"email_id": "new", "sender_email": "c@example.com", "subject": "New", "date": "2026-06-12T17:00:00-07:00"},
    ]
    upload = client.post(
        "/api/upload-email-json",
        data={"file": (io.BytesIO(json.dumps(emails).encode()), "emails.json")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 200

    result = client.post("/api/rerun").get_json()
    assert [email["email_id"] for email in result["emails"]] == ["new", "old", "invalid"]


def test_prompt_rejects_broken_output_contract(client):
    response = client.post("/api/prompt/update", json={"prompt": "A" * 100})
    assert response.status_code == 400
    assert "required JSON fields" in response.get_json()["error"]


def test_upload_email_json_loads_raw_messages_without_classifying(client):
    email_data = json.dumps([{"sender_email": "a@example.com", "subject": "Hello"}]).encode()
    response = client.post(
        "/api/upload-email-json",
        data={"file": (io.BytesIO(email_data), "emails.json")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    result = response.get_json()
    assert result["status"] == "awaiting_classification"
    assert result["mode"] == "upload"
    assert result["pending_count"] == 1
    assert result["summary"]["total"] == 0
    assert result["raw_emails"][0]["source_type"] == "upload"


def test_ground_truth_endpoint_scores_synthetic_fixture(client):
    before_classification = client.post("/api/test-ground-truth")
    assert before_classification.status_code == 409
    assert "Classify the synthetic emails first" in before_classification.get_json()["error"]

    classification = client.post("/api/rerun")
    assert classification.status_code == 200
    response = client.post("/api/test-ground-truth")
    assert response.status_code == 200
    result = response.get_json()
    assert result["total"] == 200
    assert result["category_accuracy"] == 1.0
    assert result["subcategory_accuracy"] == 1.0
    assert result["exact_accuracy"] == 1.0
    assert result["mismatches"] == []
    assert len(result["chart"]["labels"]) == 5
    assert result["reused_predictions"] is True

    state_after_test = client.get("/api/status").get_json()
    assert state_after_test["last_run"] == classification.get_json()["last_run"]


def test_app_version_prefers_environment_override(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "v9.99")
    assert resolve_app_version() == "9.99"


def test_app_version_uses_latest_git_tag(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.setattr("config.subprocess.check_output", lambda *args, **kwargs: "v1.23\n")
    assert resolve_app_version() == "1.23"
