import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"


def _load_dotenv():
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_local_config():
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_local_config(values):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current = load_local_config()
    current.update(values)
    CONFIG_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")


_load_dotenv()
LOCAL_CONFIG = load_local_config()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "local-email-copilot")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or LOCAL_CONFIG.get("openai_api_key", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", LOCAL_CONFIG.get("openai_model", "gpt-4.1-mini"))
    GOOGLE_CLIENT_SECRET_FILE = os.getenv(
        "GOOGLE_CLIENT_SECRET_FILE", str(DATA_DIR / "client_secret.json")
    )
    MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() in {"1", "true", "yes", "on"}
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024

