# abvorn/core/kimi_strategist.py
"""KimiStrategist — high-value strategy calls on the official Moonshot API.

Uses the Moonshot official key (stored as KIMI_KEY in the boardroom
secrets.json) for low-frequency, high-intelligence calls: economic
insight, cross-domain synthesis, and connection discovery. This is the
zero-credit-card alternative to the Vercel AI Gateway — it talks straight
to Moonshot's servers.

Endpoint fallback: api.moonshot.ai (international) first, then
api.moonshot.cn (China mainland). Both are OpenAI-compatible.

Every call degrades gracefully — if the key is missing or a call fails,
methods return {"error": ...} so callers can proceed without crashing.
"""

import json
import logging

logger = logging.getLogger(__name__)


def _load_moonshot_key() -> str:
    """Load the Moonshot official API key from env or boardroom secrets."""
    key = __import__("os").environ.get("KIMI_KEY", "")
    if key:
        return key
    try:
        from abvorn.core.secrets import load_secrets
        return load_secrets().get("KIMI_KEY", "")
    except Exception:
        return ""


class KimiStrategist:
    """Official Moonshot API client for professional-data and synthesis calls."""

    BASE_URLS = [
        "https://api.moonshot.ai/v1",
        "https://api.moonshot.cn/v1",
    ]

    def __init__(self, api_key: str = "", model: str = "kimi-k2.6", base_url: str = ""):
        self.model = model
        self.api_key = api_key or _load_moonshot_key()
        self.enabled = False
        self.client = None
        self.base_url = base_url
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        if not self.api_key or not self.api_key.startswith("sk-"):
            logger.warning("KIMI_KEY missing or invalid. KimiStrategist disabled.")
            return

        try:
            from openai import OpenAI
        except ImportError:
            logger.warning("openai SDK not installed; KimiStrategist disabled")
            return

        urls = [self.base_url] if self.base_url else self.BASE_URLS
        for url in urls:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=url)
                self.base_url = url
                self.enabled = True
                break
            except Exception as e:
                logger.warning(f"KimiStrategist client init failed for {url}: {e}")
        if self.enabled:
            logger.info(f"KimiStrategist enabled via {self.base_url} (model={self.model})")

    # ── low-level ──────────────────────────────────────────────────────

    def _complete(self, messages, temperature: float = 0.2, max_tokens: int = 1500) -> dict:
        """Run a chat completion. Returns parsed JSON dict or {"error": ...}."""
        if not self.enabled or not self.client:
            return {"error": "KimiStrategist disabled"}
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            if response.usage:
                self.total_input_tokens += response.usage.prompt_tokens or 0
                self.total_output_tokens += response.usage.completion_tokens or 0
            content = (response.choices[0].message.content or "").strip()
            if not content:
                return {"error": "empty response"}
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"error": "non-JSON response", "raw": content[:500]}
        except Exception as e:
            logger.error(f"KimiStrategist query failed: {e}")
            return {"error": str(e)}

    # ── public API ─────────────────────────────────────────────────────

    def query_economic_insight(self, query: str) -> dict:
        """Query economic / market intelligence (World Bank, financial datasets)."""
        return self._complete(
            [
                {
                    "role": "system",
                    "content": (
                        "You are an economic analyst with access to World Bank and "
                        "financial datasets. Answer with grounded, current economic "
                        "reasoning. Return valid JSON only."
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.2,
        )

    def discover_connections(self, concept_a: str, concept_b: str) -> dict:
        """Discover novel cross-domain connections between two concepts."""
        return self._complete(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a cross-domain synthesis engine. Find 3 non-obvious "
                        "links between concepts. Return valid JSON only with keys: "
                        "connections (list of {idea, reasoning}), summary (string)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Connect '{concept_a}' and '{concept_b}'.",
                },
            ],
            temperature=0.8,
        )

    def get_usage_summary(self) -> dict:
        """Return cumulative token usage."""
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "enabled": self.enabled,
            "model": self.model,
            "base_url": self.base_url,
        }


_strategist = None


def get_kimi_strategist() -> KimiStrategist:
    """Singleton accessor for the KimiStrategist."""
    global _strategist
    if _strategist is None:
        _strategist = KimiStrategist()
    return _strategist
