import time, logging
from collections import defaultdict
from openai import OpenAI

logger = logging.getLogger("abvorn.models")

class AIProvider:
    def __init__(self, name: str, api_key: str, base_url: str = None, model: str = None):
        self.name = name
        self.model = model or "gpt-4o"
        self.client = OpenAI(api_key=api_key, base_url=base_url) if api_key else None
        self._banned_until = 0.0
        self.total_calls = 0
        self.total_tokens = 0
        self.total_time = 0.0
        self.failures = 0

    @property
    def available(self) -> bool:
        return self.client is not None and time.time() > self._banned_until

    def ban(self, duration: int = 60):
        self._banned_until = time.time() + duration
        self.failures += 1

    def call(self, messages: list, json_mode: bool = False) -> str:
        start = time.time()
        fmt = {"type": "json_object"} if json_mode else None
        if self.client is None:
            raise RuntimeError(f"{self.name}: no API key configured")
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages, response_format=fmt
            )
            elapsed = time.time() - start
            self.total_calls += 1
            self.total_tokens += resp.usage.total_tokens if resp.usage else 0
            self.total_time += elapsed
            return resp.choices[0].message.content
        except Exception as e:
            logger.warning(f"{self.name} failed: {str(e)[:80]}")
            raise


class ModelRouter:
    def __init__(self, secrets: dict):
        self.providers = []
        configs = [
            ("qwen", secrets.get("QWEN_KEY"), "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen3.5-flash"),
            ("gemini", secrets.get("GEMINI_KEY"), "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.0-flash"),
            ("groq", secrets.get("GROQ_KEY"), "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
            ("deepseek", secrets.get("DEEPSEEK_KEY"), "https://api.deepseek.com/v1", "deepseek-chat"),
            ("openai", secrets.get("OPENAI_KEY"), None, "gpt-4o"),
        ]
        for name, key, url, model in configs:
            if key and "YOUR_" not in key:
                self.providers.append(AIProvider(name, key, url, model))

    def ask(self, prompt: str, system: str = None, json_mode: bool = False,
            model_hint: str = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        if model_hint:
            for p in self.providers:
                if model_hint in p.name and p.available:
                    try:
                        return p.call(messages, json_mode)
                    except Exception:
                        p.ban()
        for p in self.providers:
            if not p.available:
                continue
            try:
                return p.call(messages, json_mode)
            except Exception:
                p.ban()
                continue
        logger.error("All AI providers exhausted")
        return None

    def get_stats(self) -> list:
        return [{"name": p.name, "calls": p.total_calls, "tokens": p.total_tokens,
                 "time": round(p.total_time, 2), "failures": p.failures,
                 "available": p.available} for p in self.providers]


class ModelCostTracker:
    """Tracks per-call model costs via state DB. Attached to daemon lifecycle."""

    def __init__(self, state):
        self._state = state
        self._calls = []

    def record_call(self, provider: str, model: str, task: str,
                    tokens: int, time_ms: int, success: bool):
        entry = dict(provider=provider, model=model, task=task,
                     tokens=tokens, time_ms=time_ms, success=success)
        self._calls.append(entry)
        self._state.set_meta(f"cost_log_{len(self._calls)}", entry)
        self._state.set_meta("cost_call_count", len(self._calls))

    def get_stats(self) -> dict:
        total = len(self._calls)
        successful = sum(1 for c in self._calls if c.get("success"))
        failed = total - successful
        total_tokens = sum(c.get("tokens", 0) for c in self._calls)
        rate_per_1k = 0.002
        estimated_cost = (total_tokens / 1000) * rate_per_1k
        return dict(
            total_calls=total,
            successful=successful,
            failed=failed,
            total_tokens=total_tokens,
            estimated_cost_usd=round(estimated_cost, 4),
        )
