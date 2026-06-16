import json
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from agents import (
    AIEmailClassifierAgent,
    AuditLogAgent,
    CategoryRegroupAgent,
    ChartAgent,
    DailyBriefAgent,
    EmailFetchAgent,
    EmailPreprocessAgent,
    EmailResponseAgent,
    GroundTruthTestAgent,
    MockEmailClassifierAgent,
    PromptManagerAgent,
    SummaryAgent,
)
from agents.constants import CATEGORIES, CATEGORY_COLORS
from config import BASE_DIR, Config, DATA_DIR, save_local_config
from services import GmailService, OpenAIService


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    data_dir = Path(app.config.get("DATA_DIR", DATA_DIR))
    data_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    prompt_agent = PromptManagerAgent(data_dir / "prompt_versions.json")
    audit_agent = AuditLogAgent(data_dir / "audit_log.json")
    gmail_service = GmailService(app.config["GOOGLE_CLIENT_SECRET_FILE"], data_dir / "token.json")
    openai_service = OpenAIService(app.config.get("OPENAI_API_KEY", ""), app.config["OPENAI_MODEL"])
    fetch_agent = EmailFetchAgent(data_dir / "synthetic_emails.json", gmail_service)
    preprocess_agent = EmailPreprocessAgent()
    response_agent = EmailResponseAgent(openai_service)
    regroup_agent = CategoryRegroupAgent()
    summary_agent = SummaryAgent()
    chart_agent = ChartAgent()
    daily_brief_agent = DailyBriefAgent(openai_service)
    ground_truth_agent = GroundTruthTestAgent()
    state_file = data_dir / "classification_state.json"
    response_drafts_file = data_dir / "response_drafts.json"

    def sort_emails_newest_first(emails):
        def timestamp(email):
            value = str(email.get("date") or "").strip()
            if not value:
                return float("-inf")
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.astimezone()
                return parsed.timestamp()
            except ValueError:
                return float("-inf")

        return sorted(emails, key=timestamp, reverse=True)

    def load_state():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["emails"] = regroup_agent.process(state.get("emails", []))
            return state
        except (OSError, json.JSONDecodeError):
            return {"mode": "synthetic", "emails": [], "raw_emails": [], "response_drafts": {}, "last_run": None, "status": "ready"}

    def save_state(state):
        state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def load_response_drafts():
        try:
            drafts = json.loads(response_drafts_file.read_text(encoding="utf-8"))
            return drafts if isinstance(drafts, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def save_response_drafts(drafts):
        response_drafts_file.write_text(json.dumps(drafts, indent=2), encoding="utf-8")

    def find_email(email_id):
        state = load_state()
        classified = next((email for email in state.get("emails", []) if email.get("email_id") == email_id), None)
        raw = next((email for email in state.get("raw_emails", []) if email.get("email_id") == email_id), None)
        return classified, raw

    def hydrate_gmail_raw(raw):
        if raw and raw.get("source_type") == "gmail" and not raw.get("full_body_optional"):
            try:
                return {**raw, **gmail_service.fetch_message(raw["email_id"])}
            except Exception:
                return raw
        return raw

    def initialize_startup_state():
        return load_raw_state(fetch_agent.load_synthetic(), "synthetic")

    def load_raw_state(raw_emails, mode):
        state = {
            "mode": mode,
            "raw_emails": raw_emails,
            "emails": [],
            "response_drafts": load_response_drafts(),
            "last_run": None,
            "status": "awaiting_classification",
            "errors": [],
        }
        save_state(state)
        return state

    initialize_startup_state()

    def use_mock_classifier():
        return app.config["MOCK_MODE"] or not openai_service.is_configured

    def classifier():
        if use_mock_classifier():
            return MockEmailClassifierAgent()
        return AIEmailClassifierAgent(openai_service)

    def run_classification(raw_emails, mode, is_rerun=False):
        started = datetime.now().astimezone()
        prompt = prompt_agent.get()
        errors = []
        mock_mode = use_mock_classifier()
        try:
            normalized = preprocess_agent.process(raw_emails)
            classified = classifier().classify(normalized, prompt["prompt"])
            classified = regroup_agent.process(classified)
            classified = sort_emails_newest_first(classified)
            daily_brief = daily_brief_agent.build(classified, use_ai=not mock_mode)
            status = "complete"
        except Exception as exc:
            classified = []
            daily_brief = daily_brief_agent.build([])
            errors.append(str(exc))
            status = "error"
        state = {
            "mode": mode,
            "raw_emails": raw_emails,
            "emails": classified,
            "last_run": started.isoformat(),
            "classification_model": "mock-rules-v1" if mock_mode else openai_service.model,
            "daily_brief": daily_brief,
            "status": status,
            "errors": errors,
        }
        save_state(state)
        audit_agent.record(
            mode=mode,
            prompt_version=prompt["version"],
            model="mock-rules-v1" if mock_mode else openai_service.model,
            emails_processed=len(classified),
            errors=errors,
            rerun=is_rerun,
            duration_ms=int((datetime.now().astimezone() - started).total_seconds() * 1000),
        )
        if errors:
            raise RuntimeError(errors[0])
        return state

    def dashboard_payload(state=None):
        state = state or load_state()
        emails = sort_emails_newest_first(state.get("emails", []))
        daily_brief = state.get("daily_brief") or daily_brief_agent.build(emails)
        if daily_brief.get("text"):
            daily_brief = {
                **daily_brief,
                "text": daily_brief_agent._format_for_quick_read(daily_brief["text"]),
            }
        counts = {category: 0 for category in CATEGORIES}
        confidence_totals = {category: [] for category in CATEGORIES}
        for email in emails:
            category = email.get("category", "Other / Needs Review")
            counts[category] = counts.get(category, 0) + 1
            confidence_totals.setdefault(category, []).append(float(email.get("confidence_score") or 0))
        categories = [
            {
                "name": category,
                "count": counts[category],
                "average_confidence": round(sum(confidence_totals[category]) / len(confidence_totals[category]), 2)
                if confidence_totals[category]
                else 0,
                "color": CATEGORY_COLORS[category],
            }
            for category in CATEGORIES
        ]
        return {
            **state,
            "emails": emails,
            "pending_count": len(state.get("raw_emails", [])) if not emails else 0,
            "categories": categories,
            "summary": summary_agent.build(emails),
            "response_drafts": load_response_drafts(),
            "daily_brief": daily_brief,
            "chart": chart_agent.build(emails),
            "today": datetime.now().astimezone().strftime("%A, %B %-d, %Y"),
            "app_version": app.config["APP_VERSION"],
            "mock_mode": use_mock_classifier(),
            "gmail_connected": gmail_service.is_connected,
            "gmail_configured": gmail_service.is_configured,
            "openai_configured": openai_service.is_configured,
            "model": "mock-rules-v1" if use_mock_classifier() else openai_service.model,
        }

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({"error": "Upload is too large. Maximum file size is 12 MB."}), 413

    @app.route("/")
    def index():
        return render_template("index.html", initial_data=dashboard_payload())

    @app.get("/api/status")
    def status():
        return jsonify(dashboard_payload())

    @app.get("/api/emails/today")
    def emails_today():
        state = load_state()
        return jsonify({"emails": state.get("emails", []), "mode": state.get("mode")})

    @app.post("/api/emails/synthetic")
    def synthetic():
        return jsonify(dashboard_payload(load_raw_state(fetch_agent.load_synthetic(), "synthetic")))

    @app.post("/api/upload-email-json")
    def upload_email_json():
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return jsonify({"error": "Choose an email JSON file to upload."}), 400
        if not uploaded.filename.lower().endswith(".json"):
            return jsonify({"error": "Only JSON files are supported."}), 400
        destination = upload_dir / secure_filename(uploaded.filename)
        uploaded.save(destination)
        try:
            rows = fetch_agent.load_email_json(destination, source_type="upload")
            state = load_raw_state(rows, "upload")
            return jsonify(dashboard_payload(state))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/classify")
    def classify_route():
        payload = request.get_json(silent=True) or {}
        mode = payload.get("mode", load_state().get("mode", "synthetic"))
        try:
            if mode == "gmail":
                raw = fetch_agent.load_gmail_today()
            elif mode == "synthetic":
                raw = fetch_agent.load_synthetic()
            else:
                raw = load_state().get("raw_emails", [])
            if not raw:
                return jsonify({"error": "No emails were found for this mode."}), 400
            return jsonify(dashboard_payload(run_classification(raw, mode)))
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/categories")
    def categories():
        return jsonify(dashboard_payload()["categories"])

    @app.get("/api/category/<path:category_name>")
    def category(category_name):
        emails = sort_emails_newest_first(
            [email for email in load_state().get("emails", []) if email.get("category") == category_name]
        )
        return jsonify({"category": category_name, "emails": emails, "count": len(emails)})

    @app.get("/api/email/<path:email_id>/raw")
    def raw_email(email_id):
        classified, raw = find_email(email_id)
        if not classified or not raw:
            return jsonify({"error": "Email was not found in the current classified inbox."}), 404
        if classified.get("category") not in response_agent.ALLOWED_CATEGORIES:
            return jsonify({"error": "Raw email retrieval is available only for Urgent Priority, Work, and Personal emails."}), 403
        raw = hydrate_gmail_raw(raw)
        return jsonify(
            {
                "email_id": raw.get("email_id"),
                "sender_name": raw.get("sender_name", ""),
                "sender_email": raw.get("sender_email", ""),
                "subject": raw.get("subject", ""),
                "date": raw.get("date", ""),
                "body": raw.get("full_body_optional") or raw.get("body_preview", ""),
            }
        )

    @app.post("/api/email/<path:email_id>/draft-response")
    def draft_email_response(email_id):
        classified, raw = find_email(email_id)
        if not classified or not raw:
            return jsonify({"error": "Email was not found in the current classified inbox."}), 404
        raw = hydrate_gmail_raw(raw)
        email = {
            **raw,
            "category": classified.get("category", ""),
            "subcategory": classified.get("subcategory", ""),
            "urgency_level": classified.get("urgency_level", ""),
        }
        try:
            return jsonify({"email_id": email_id, "draft": response_agent.draft(email), "generated_by": "ai"})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 403
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/email/<path:email_id>/save-response")
    def save_email_response(email_id):
        classified, raw = find_email(email_id)
        if not classified or not raw:
            return jsonify({"error": "Email was not found in the current classified inbox."}), 404
        if classified.get("category") not in response_agent.ALLOWED_CATEGORIES:
            return jsonify({"error": "Responses are available only for Urgent Priority, Work, and Personal emails."}), 403
        payload = request.get_json(silent=True) or {}
        draft = str(payload.get("draft", "")).strip()
        if not draft:
            return jsonify({"error": "The response draft cannot be empty."}), 400
        if len(draft) > 20000:
            return jsonify({"error": "The response draft is too long."}), 400
        drafts = load_response_drafts()
        drafts[email_id] = draft
        save_response_drafts(drafts)
        return jsonify({"ok": True, "email_id": email_id, "draft": draft})

    @app.post("/api/email/<path:email_id>/send-response")
    def send_email_response(email_id):
        classified, raw = find_email(email_id)
        if not classified or not raw:
            return jsonify({"error": "Email was not found in the current classified inbox."}), 404
        if classified.get("category") not in response_agent.ALLOWED_CATEGORIES:
            return jsonify({"error": "Responses are available only for Urgent Priority, Work, and Personal emails."}), 403
        if raw.get("source_type") != "gmail":
            return jsonify({"error": "Sending is available only for emails retrieved from live Gmail."}), 409
        payload = request.get_json(silent=True) or {}
        draft = str(payload.get("draft", "")).strip()
        if not draft:
            return jsonify({"error": "The response draft cannot be empty."}), 400
        if len(draft) > 20000:
            return jsonify({"error": "The response draft is too long."}), 400
        try:
            result = gmail_service.send_email(raw.get("sender_email"), raw.get("subject", ""), draft)
            drafts = load_response_drafts()
            drafts[email_id] = draft
            save_response_drafts(drafts)
            state = load_state()
            state.setdefault("sent_responses", {})[email_id] = {
                "gmail_message_id": result.get("id", ""),
                "sent_at": datetime.now().astimezone().isoformat(),
            }
            save_state(state)
            return jsonify({"ok": True, "email_id": email_id, "gmail_message_id": result.get("id", "")})
        except (ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/prompt")
    def prompt():
        return jsonify(prompt_agent.get())

    @app.post("/api/prompt/update")
    def prompt_update():
        payload = request.get_json(silent=True) or {}
        try:
            return jsonify(prompt_agent.save(payload.get("prompt", "")))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/prompt/reset")
    def prompt_reset():
        return jsonify(prompt_agent.reset())

    @app.post("/api/rerun")
    def rerun():
        state = load_state()
        raw = state.get("raw_emails") or fetch_agent.load_synthetic()
        try:
            return jsonify(dashboard_payload(run_classification(raw, state.get("mode", "synthetic"), is_rerun=True)))
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/audit-log")
    def audit_log():
        return jsonify({"runs": audit_agent.list()})

    @app.post("/api/test-ground-truth")
    def test_ground_truth():
        started = datetime.now().astimezone()
        try:
            state = load_state()
            if state.get("mode") != "synthetic" or state.get("status") != "complete":
                return jsonify(
                    {"error": "Classify the synthetic emails first, then run Test Ground Truth."}
                ), 409
            raw = state.get("raw_emails") or []
            predictions = state.get("emails") or []
            if not predictions or any(not email.get("category") for email in predictions):
                return jsonify(
                    {"error": "Classify the synthetic emails first, then run Test Ground Truth."}
                ), 409
            result = ground_truth_agent.evaluate(raw, predictions)
            result.update(
                {
                    "model": state.get("classification_model") or "saved-classification",
                    "mock_mode": state.get("classification_model") == "mock-rules-v1",
                    "reused_predictions": True,
                    "timestamp": started.isoformat(),
                }
            )
            audit_agent.record(
                mode="ground-truth-test",
                prompt_version=prompt_agent.get()["version"],
                model=result["model"],
                emails_processed=len(predictions),
                errors=[],
                rerun=False,
                category_accuracy=result["category_accuracy"],
                subcategory_accuracy=result["subcategory_accuracy"],
                exact_accuracy=result["exact_accuracy"],
                duration_ms=int((datetime.now().astimezone() - started).total_seconds() * 1000),
            )
            return jsonify(result)
        except (ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/setup/openai")
    def setup_openai():
        payload = request.get_json(silent=True) or {}
        api_key = str(payload.get("api_key", "")).strip()
        model = str(payload.get("model", app.config["OPENAI_MODEL"])).strip()
        if api_key and not api_key.startswith("sk-"):
            return jsonify({"error": "That key format does not look like an OpenAI API key."}), 400
        save_local_config({"openai_api_key": api_key, "openai_model": model})
        openai_service.api_key = api_key
        openai_service.model = model
        app.config["MOCK_MODE"] = not bool(api_key)
        return jsonify({"ok": True, "openai_configured": bool(api_key), "mock_mode": not bool(api_key)})

    @app.get("/api/gmail/connect")
    def gmail_connect():
        try:
            redirect_uri = url_for("gmail_callback", _external=True)
            authorization_url, state, code_verifier = gmail_service.get_authorization_url(redirect_uri)
            session["oauth_state"] = state
            session["oauth_code_verifier"] = code_verifier
            return redirect(authorization_url)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/oauth2/callback")
    def gmail_callback():
        try:
            gmail_service.complete_authorization(
                request.url,
                url_for("gmail_callback", _external=True),
                session.get("oauth_state"),
                session.get("oauth_code_verifier"),
            )
            session.pop("oauth_state", None)
            session.pop("oauth_code_verifier", None)
            return redirect(url_for("index", gmail="connected"))
        except Exception as exc:
            return jsonify({"error": f"Gmail connection failed: {exc}"}), 400

    app.extensions["email_copilot"] = {
        "fetch_agent": fetch_agent,
        "prompt_agent": prompt_agent,
        "run_classification": run_classification,
    }
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
