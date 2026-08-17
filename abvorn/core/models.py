import time, logging
from collections import defaultdict
from openai import OpenAI

logger = logging.getLogger("abvorn.models")

# Capability tiers for task-aware routing. TASK_MODELS still maps a task to its
# model hint (kept for back-compat); TIER_FOR_TASK maps the same tasks to a
# capability tier so the router can prefer the right class of provider.
TIER_FOR_TASK = {
    "research": "fast",
    "social": "fast",
    "brain": "fast",
    "outline": "strong",
    "draft": "strong",
    "fact_check": "strong",
    "polish": "strong",
}

class AIProvider:
    def __init__(self, name: str, api_key: str, base_url: str = None, model: str = None, timeout: float = None,
                 tier: str = "standard"):
        self.name = name
        self.tier = tier
        self.model = model or "gpt-4o"
        import httpx
        to = httpx.Timeout(timeout if timeout else 60.0, connect=timeout if timeout else 10.0)
        http_client = httpx.Client(timeout=to)
        kwargs = {"api_key": api_key, "base_url": base_url, "http_client": http_client, "max_retries": 0}
        self.client = OpenAI(**kwargs) if api_key else None
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

    def call_with_metadata(self, messages: list, json_mode: bool = False, max_retries: int = 2) -> dict:
        """Like call() but returns content + metadata dict with retry logic."""
        import openai
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                start = time.time()
                fmt = {"type": "json_object"} if json_mode else None
                if self.client is None:
                    raise RuntimeError(f"{self.name}: no API key configured")
                resp = self.client.chat.completions.create(
                    model=self.model, messages=messages, response_format=fmt
                )
                elapsed = time.time() - start
                self.total_calls += 1
                tokens = resp.usage.total_tokens if resp.usage else 0
                self.total_tokens += tokens
                self.total_time += elapsed
                return resp.choices[0].message.content, {
                    "model": self.model,
                    "tokens": tokens,
                    "time_ms": int(elapsed * 1000),
                    "provider": self.name,
                    "success": True,
                }
            except openai.AuthenticationError:
                raise
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    import time as t
                    t.sleep(1 * (attempt + 1))
                    continue
        self.failures += 1
        raise last_error


class ModelRouter:
    def __init__(self, secrets: dict, timeout: float = None):
        self.providers = []
        configs = [
            ("cerebras", secrets.get("CEREBRAS_KEY"), "https://api.cerebras.ai/v1", "gpt-oss-120b", "strong"),
            ("deepseek", secrets.get("DEEPSEEK_KEY"), "https://api.deepseek.com/v1", "deepseek-chat", "strong"),
            ("qwen", secrets.get("QWEN_KEY"), "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen3.5-flash", "fast"),
            ("groq", secrets.get("GROQ_KEY"), "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "strong"),
            ("glm", secrets.get("GLM_KEYS"), "https://open.bigmodel.cn/api/paas/v4/", "glm-4-flash", "fast"),
            ("gemini", secrets.get("GEMINI_KEY"), "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.0-flash", "fast"),
            ("openai", secrets.get("OPENAI_KEY"), None, "gpt-4o", "strong"),
        ]
        for name, key, url, model, tier in configs:
            if key and "YOUR_" not in key:
                self.providers.append(AIProvider(name, key, url, model, timeout=timeout, tier=tier))

    def ask(self, prompt: str, system: str = None, json_mode: bool = False,
            model_hint: str = None, task: str = None) -> str:
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
        # If task is specified, prefer providers whose capability tier matches
        # the task (fast for research/social/brain, strong for drafting and
        # verification), then fall back to the remaining providers.
        if task and task in TIER_FOR_TASK:
            tier = TIER_FOR_TASK[task]
            for p in self.providers:
                if p.tier == tier and p.available:
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

    def health(self) -> dict:
        """Kilo health check. Returns availability + recent failure count."""
        total = len(self.providers)
        avail = sum(1 for p in self.providers if p.available)
        recent_fails = sum(1 for p in self.providers if p.failures > 0 and not p.available)
        return {
            "total_providers": total,
            "available": avail,
            "unavailable": total - avail,
            "recent_failures": recent_fails,
            "healthy": avail > 0,
        }

    def get_fallback_response(self, prompt: str, task: str = None) -> str:
        """Graceful fallback when no model is available.

        Returns a template response so the system degrades gracefully
        rather than crashing.
        """
        logger.warning("ModelRouter fallback: no AI providers available")
        return ""

    def ask_with_health(self, prompt: str, system: str = None, json_mode: bool = False,
                        model_hint: str = None, task: str = None) -> tuple:
        """Like ask() but returns (response, health_dict) for observability."""
        result = self.ask(prompt, system, json_mode, model_hint, task)
        if result is None:
            result = self.get_fallback_response(prompt, task)
        return result, self.health()

    def get_stats(self) -> list:
        return [{"name": p.name, "calls": p.total_calls, "tokens": p.total_tokens,
                 "time": round(p.total_time, 2), "failures": p.failures,
                 "available": p.available} for p in self.providers]


TASK_MODELS = {
    "research": "haiku",
    "social": "haiku",
    "outline": "sonnet",
    "draft": "sonnet",
    "fact_check": "sonnet",
    "polish": "sonnet",
    "brain": "haiku",
}


class ModelCostTracker:
    """Tracks per-call model costs. In-memory or state-backed."""

    def __init__(self, state=None):
        self._state = state
        self._calls = []

    @property
    def session_calls(self):
        return self._calls

    def record_call(self, provider: str, model: str, task: str,
                    tokens: int, time_ms: int, success: bool):
        entry = dict(provider=provider, model=model, task=task,
                     tokens=tokens, time_ms=time_ms, success=success)
        self._calls.append(entry)
        if self._state:
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
