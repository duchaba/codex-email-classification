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


def test_dashboard_and_status_bootstrap_200_emails(client):
    response = client.get("/")
    assert response.status_code == 200
    status = client.get("/api/status").get_json()
    assert status["summary"]["total"] == 200
    assert status["mode"] == "synthetic"
    assert [category["name"] for category in status["categories"]] == [
        "Urgent Priority",
        "Work",
        "Personal",
        "Social Media",
        "Spam",
    ]
    assert status["chart"]["labels"] == [
        category["name"] for category in status["categories"] if category["count"]
    ]


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
