"""Generate ~/.abvorn/boardroom/secrets.json from a simple KEY=VALUE .env file.

The daemon (abvorn.core.secrets.load_secrets) prefers the boardroom secrets
JSON; run_cycle (os.environ.get) uses env vars. The VPS keeps a single .env
and this script materializes both sources.

Usage:
    python make_secrets_json.py /path/to/.env /path/to/output/secrets.json
"""
import json
import sys
from pathlib import Path

ENV_KEYS = [
    "OPENAI_KEY", "DEEPSEEK_KEY", "GEMINI_KEY", "GROQ_KEY", "GLM_KEYS",
    "QWEN_KEY", "PEXELS_KEY", "OPENWEB_NINJA_KEY", "TAVILY_KEY",
    "CEREBRAS_KEY", "AMAZON_TAG", "SHAREASALE_ID", "EBAY_CAMPID",
    "GMAIL_USER", "GMAIL_APP_PASSWORD", "SHEET_ID", "APPS_SCRIPT_URL",
    "LISTMONK_URL", "LISTMONK_TOKEN", "GA4_MEASUREMENT_ID", "GA4_API_SECRET",
    "GA4_PROPERTY_ID", "GA4_CREDENTIALS_JSON", "TELEGRAM_TOKEN",
    "TELEGRAM_CHAT_ID", "GITHUB_TOKEN", "GITHUB_REPO", "SITE_URL",
    "COMPOSIO_KEY", "KILL_SWITCH_PASSWORD",
]


def parse_env(path: Path) -> dict:
    result = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        result[key] = value
    return result


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    env_file = Path(sys.argv[1])
    out_file = Path(sys.argv[2])
    if not env_file.exists():
        print(f"env file not found: {env_file}")
        return 1
    values = parse_env(env_file)
    secrets = {k: values.get(k, "") for k in ENV_KEYS if values.get(k)}
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        json.dumps(secrets, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {len(secrets)} secrets to {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())