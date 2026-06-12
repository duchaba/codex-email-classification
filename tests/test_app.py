import io

import pytest

from app import create_app


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
    status = client.get("/api/status").get_json()
    assert status["summary"]["total"] == 0
    assert status["pending_count"] == 200
    assert status["status"] == "awaiting_classification"
    assert status["mode"] == "synthetic"
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
    assert sum(category["count"] for category in result["categories"]) == 200
    assert len({email["email_id"] for email in result["emails"]}) == 200
    assert all(isinstance(email["category"], str) for email in result["emails"])


def test_prompt_rejects_broken_output_contract(client):
    response = client.post("/api/prompt/update", json={"prompt": "A" * 100})
    assert response.status_code == 400
    assert "required JSON fields" in response.get_json()["error"]


def test_upload_requires_at_least_200_rows(client):
    csv_data = b"sender_email,subject\na@example.com,Hello\n"
    response = client.post(
        "/api/upload-csv",
        data={"file": (io.BytesIO(csv_data), "emails.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "at least 200" in response.get_json()["error"]


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
