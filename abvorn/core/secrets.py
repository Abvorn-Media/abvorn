import json, os, logging
from pathlib import Path

logger = logging.getLogger("abvorn.secrets")

BOARDROOM_PATHS = [
    Path(os.environ.get("ABVORN_BOARDROOM", "")),
    Path("/content/drive/MyDrive/The_Synthetic_Boardroom"),
    Path.home() / ".abvorn" / "boardroom",
]

def _find_boardroom() -> Path:
    for p in BOARDROOM_PATHS:
        if p.exists() and (p / "secrets.json").exists():
            return p
    local = Path.home() / ".abvorn" / "boardroom"
    local.mkdir(parents=True, exist_ok=True)
    return local

def load_secrets() -> dict:
    boardroom = _find_boardroom()
    secrets = {}
    sf = boardroom / "secrets.json"
    if sf.exists():
        raw = sf.read_bytes()
        if raw.startswith(b'\xef\xbb\xbf'):
            raw = raw[3:]
        try:
            secrets = json.loads(raw.decode('utf-8'))
        except json.JSONDecodeError:
            logger.warning("secrets.json corrupt, falling back to env vars")
    env_map = {
        "GLM_KEYS": "GLM_KEYS", "DEEPSEEK_KEY": "DEEPSEEK_KEY",
        "OPENAI_KEY": "OPENAI_KEY", "QWEN_KEY": "QWEN_KEY",
        "GEMINI_KEY": "GEMINI_KEY", "GROQ_KEY": "GROQ_KEY",
        "GITHUB_TOKEN": "GITHUB_TOKEN", "GITHUB_REPO": "GITHUB_REPO",
        "SITE_URL": "SITE_URL", "AMAZON_TAG": "AMAZON_TAG",
        "GA4_MEASUREMENT_ID": "GA4_MEASUREMENT_ID",
        "GA4_API_SECRET": "GA4_API_SECRET",
        "GA4_PROPERTY_ID": "GA4_PROPERTY_ID",
        "GA4_CREDENTIALS_JSON": "GA4_CREDENTIALS_JSON",
        "TELEGRAM_TOKEN": "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID": "TELEGRAM_CHAT_ID",
        "GMAIL_USER": "GMAIL_USER",
        "GMAIL_APP_PASSWORD": "GMAIL_APP_PASSWORD",
        "SHEET_ID": "SHEET_ID",
        "COMPOSIO_KEY": "COMPOSIO_KEY",
        "PEXELS_KEY": "PEXELS_KEY",
        "ABVORN_BRAIN_PATH": "ABVORN_BRAIN_PATH",
    }
    for env_key, secrets_key in env_map.items():
        val = os.environ.get(env_key)
        if val and "YOUR_" not in val:
            secrets[secrets_key] = val
    ga4_file = boardroom / "ga4_credentials.json"
    if ga4_file.exists():
        secrets["GA4_CREDENTIALS_JSON"] = ga4_file.read_text().strip()
    return secrets

def get_boardroom_path() -> Path:
    return _find_boardroom()

def get_empire_path() -> Path:
    return _find_boardroom() / "6_Empire_Network"
