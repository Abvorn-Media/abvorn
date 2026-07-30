#!/usr/bin/env python3
"""
ai_sql.py — The AI SQL Engine

A stable abstraction layer for AI providers.
Separates what you want (the query) from how you get it (the provider).
"""

import logging, os
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    system_prompt: str
    user_prompt: str
    params: Dict[str, Any]
    fallback: Optional[Dict[str, Any]] = None
    provider_hint: Optional[str] = None


@dataclass
class QueryResult:
    content: str
    provider_used: str
    confidence: float
    tokens_used: int
    cost_estimate: float


class ProviderAdapter:
    def __init__(self, name: str, priority: int = 5):
        self.name = name
        self.priority = priority
        self.available = True
        self.last_error = None

    def execute(self, query: QueryPlan) -> QueryResult:
        raise NotImplementedError

    def health_check(self) -> bool:
        return self.available


class OpenAIProvider(ProviderAdapter):
    def __init__(self):
        super().__init__("openai", priority=1)

    def execute(self, query: QueryPlan) -> QueryResult:
        return QueryResult(
            content="",
            provider_used=self.name,
            confidence=0.0,
            tokens_used=0,
            cost_estimate=0.0
        )


class AnthropicProvider(ProviderAdapter):
    def __init__(self):
        super().__init__("anthropic", priority=2)

    def execute(self, query: QueryPlan) -> QueryResult:
        return QueryResult(
            content="",
            provider_used=self.name,
            confidence=0.0,
            tokens_used=0,
            cost_estimate=0.0
        )


class GeminiProvider(ProviderAdapter):
    def __init__(self):
        super().__init__("gemini", priority=3)

    def execute(self, query: QueryPlan) -> QueryResult:
        return QueryResult(
            content="",
            provider_used=self.name,
            confidence=0.0,
            tokens_used=0,
            cost_estimate=0.0
        )


class DeepSeekProvider(ProviderAdapter):
    def __init__(self, api_key: str = ""):
        super().__init__("deepseek", priority=4)
        self.api_key = api_key or os.environ.get("DEEPSEEK_KEY", "")
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
                self.available = True
            except Exception as e:
                logger.warning(f"DeepSeek client init failed: {e}")
                self.available = False

    def execute(self, query: QueryPlan) -> QueryResult:
        if not self._client:
            return QueryResult(content="", provider_used=self.name, confidence=0.0, tokens_used=0, cost_estimate=0.0)
        try:
            response = self._client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": query.system_prompt},
                    {"role": "user", "content": query.user_prompt},
                ],
                temperature=query.params.get("temperature", 0.7),
                max_tokens=query.params.get("max_tokens", 2000),
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            return QueryResult(
                content=content,
                provider_used=self.name,
                confidence=0.9 if content else 0.0,
                tokens_used=usage.total_tokens if usage else 0,
                cost_estimate=0.0,
            )
        except Exception as e:
            logger.error(f"DeepSeek query failed: {e}")
            self.last_error = str(e)
            return QueryResult(content="", provider_used=self.name, confidence=0.0, tokens_used=0, cost_estimate=0.0)

    def health_check(self) -> bool:
        return self._client is not None


class KimiProvider(ProviderAdapter):
    """Kimi (Moonshot AI) provider — OpenAI-compatible, reachable from China networks."""

    def __init__(self, api_key: str = "", model: str = "kimi-k2.6"):
        super().__init__("kimi", priority=3)
        self.model = model
        self.api_key = api_key or os.environ.get("KIMI_KEY", "")
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key, base_url="https://api.moonshot.cn/v1")
                self.available = True
            except Exception as e:
                logger.warning(f"Kimi client init failed: {e}")
                self.available = False

    def execute(self, query: QueryPlan) -> QueryResult:
        if not self._client:
            return QueryResult(content="", provider_used=self.name, confidence=0.0, tokens_used=0, cost_estimate=0.0)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": query.system_prompt},
                    {"role": "user", "content": query.user_prompt},
                ],
                temperature=query.params.get("temperature", 0.7),
                max_tokens=query.params.get("max_tokens", 2000),
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            return QueryResult(
                content=content,
                provider_used=self.name,
                confidence=0.9 if content else 0.0,
                tokens_used=usage.total_tokens if usage else 0,
                cost_estimate=0.0,
            )
        except Exception as e:
            logger.error(f"Kimi query failed: {e}")
            self.last_error = str(e)
            return QueryResult(content="", provider_used=self.name, confidence=0.0, tokens_used=0, cost_estimate=0.0)

    def health_check(self) -> bool:
        return self._client is not None


class KiloGatewayProvider(ProviderAdapter):
    """Free tier provider via Kilo Gateway — no API key needed."""

    FREE_MODELS = ["openrouter/free", "inclusionai/ling-3.0-flash:free", "kilo-auto/free"]

    def __init__(self, model: str = "openrouter/free"):
        super().__init__("kilogateway", priority=1)
        self.model = model
        try:
            from openai import OpenAI
            self._client = OpenAI(base_url="https://api.kilo.ai/api/gateway/", api_key="anonymous")
            self.available = True
        except Exception as e:
            logger.warning(f"KiloGateway client init failed: {e}")
            self.available = False

    def execute(self, query: QueryPlan) -> QueryResult:
        if not self._client:
            return QueryResult(content="", provider_used=self.name, confidence=0.0, tokens_used=0, cost_estimate=0.0)
        models_to_try = [self.model] + [m for m in self.FREE_MODELS if m != self.model]
        for model in models_to_try:
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": query.system_prompt},
                        {"role": "user", "content": query.user_prompt},
                    ],
                    temperature=query.params.get("temperature", 0.7),
                    max_tokens=query.params.get("max_tokens", 2000),
                )
                content = response.choices[0].message.content or ""
                if content:
                    usage = response.usage
                    return QueryResult(
                        content=content,
                        provider_used=self.name,
                        confidence=0.9,
                        tokens_used=usage.total_tokens if usage else 0,
                        cost_estimate=0.0,
                    )
                logger.warning(f"KiloGateway model {model} returned empty, trying next")
            except Exception as e:
                logger.warning(f"KiloGateway model {model} failed: {e}")
        return QueryResult(content="", provider_used=self.name, confidence=0.0, tokens_used=0, cost_estimate=0.0)

    def health_check(self) -> bool:
        return self.available


class LocalProvider(ProviderAdapter):
    def __init__(self):
        super().__init__("local", priority=5)

    def execute(self, query: QueryPlan) -> QueryResult:
        return QueryResult(
            content="",
            provider_used=self.name,
            confidence=0.0,
            tokens_used=0,
            cost_estimate=0.0
        )


class AISQL:
    """
    Unified AI query interface — the "SQL for AI."
    """

    def __init__(self):
        self.providers: Dict[str, ProviderAdapter] = {
            "kilogateway": KiloGatewayProvider(),
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
            "kimi": KimiProvider(),
            "deepseek": DeepSeekProvider(),
            "local": LocalProvider(),
        }
        self.primary_provider = "kilogateway"
        self.fallback_chain = ["kilogateway", "kimi", "deepseek", "gemini", "local"]
        self.provider_scores: Dict[str, float] = {}
        self.provider_usage: Dict[str, int] = {}
        self.prompt_variants: Dict[str, Dict[str, Any]] = {}

    def update_provider_score(self, provider_name: str, engagement_score: float):
        current = self.provider_scores.get(provider_name, 0.5)
        self.provider_scores[provider_name] = current * 0.7 + engagement_score * 0.3
        self.provider_usage[provider_name] = self.provider_usage.get(provider_name, 0) + 1
        logger.info(f"Provider {provider_name} score updated to {self.provider_scores[provider_name]:.2f}")

    def log_prompt_variant(self, variant_id: str, system_prompt: str, user_prompt: str, engagement_score: float):
        self.prompt_variants[variant_id] = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "engagement_score": engagement_score,
            "timestamp": datetime.now().isoformat(),
        }

    def get_best_prompt(self) -> tuple:
        if not self.prompt_variants:
            return None, None
        best = max(self.prompt_variants.items(), key=lambda x: x[1]["engagement_score"])
        return best[1]["system_prompt"], best[1]["user_prompt"]

    def query(self, query_plan: QueryPlan) -> QueryResult:
        tried = set()
        chain = [self._select_provider(query_plan)]
        for name in self.fallback_chain:
            p = self.providers.get(name)
            if p and p is not chain[0]:
                chain.append(p)
        for provider in chain:
            if provider is None or provider.name in tried:
                continue
            tried.add(provider.name)
            try:
                result = provider.execute(query_plan)
                if result.content and result.confidence > 0:
                    logger.info(f"AI SQL query executed via {provider.name}")
                    return result
                logger.warning(f"Provider {provider.name} returned empty content, trying next")
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
        return QueryResult(content="", provider_used="none", confidence=0.0, tokens_used=0, cost_estimate=0.0)

    def _select_provider(self, query_plan: QueryPlan) -> Optional[ProviderAdapter]:
        if query_plan.provider_hint and query_plan.provider_hint in self.providers:
            return self.providers[query_plan.provider_hint]
        healthy = [name for name in self.providers if self.providers[name].health_check()]
        if not healthy:
            return None
        scored = []
        for name in healthy:
            base_priority = self.providers[name].priority
            feedback_score = self.provider_scores.get(name, 0.5)
            combined = (1.0 / (base_priority + 1)) * 0.5 + feedback_score * 0.5
            scored.append((combined, name))
        scored.sort(key=lambda x: x[0], reverse=True)
        return self.providers[scored[0][1]]

    def _get_fallback(self, failed_provider: str) -> Optional[ProviderAdapter]:
        for fallback_name in self.fallback_chain:
            if fallback_name != failed_provider:
                provider = self.providers.get(fallback_name)
                if provider and provider.health_check():
                    return provider
        return None

    def batch_query(self, queries: List[QueryPlan]) -> List[QueryResult]:
        return [self.query(q) for q in queries]

    def health_status(self) -> Dict[str, Any]:
        return {
            provider_name: provider.health_check()
            for provider_name, provider in self.providers.items()
        }


def create_ai_sql() -> AISQL:
    """Create AISQL with API keys loaded from env vars or boardroom secrets."""
    try:
        from abvorn.core.secrets import load_secrets
        secrets = load_secrets()
    except Exception:
        secrets = {}
    deepseek_key = os.environ.get("DEEPSEEK_KEY", "") or secrets.get("DEEPSEEK_KEY", "")
    kimi_key = os.environ.get("KIMI_KEY", "") or secrets.get("KIMI_KEY", "")
    ai = AISQL()
    if deepseek_key and "deepseek" in ai.providers:
        ai.providers["deepseek"] = DeepSeekProvider(api_key=deepseek_key)
    if kimi_key and "kimi" in ai.providers:
        ai.providers["kimi"] = KimiProvider(api_key=kimi_key)
    # Auto-select first healthy provider as primary
    for name in ai.fallback_chain:
        p = ai.providers.get(name)
        if p and p.health_check():
            ai.primary_provider = name
            break
    return ai


if __name__ == "__main__":
    ai_sql = create_ai_sql()
    query = QueryPlan(
        system_prompt="You are an expert reviewer.",
        user_prompt="Review the Sony WH-1000XM6.",
        params={"temperature": 0.7, "max_tokens": 1000, "format": "json"},
    )
    result = ai_sql.query(query)
    print(f"Provider: {result.provider_used}")
    print(f"Confidence: {result.confidence}")
    print(f"Health: {ai_sql.health_status()}")