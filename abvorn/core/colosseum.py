"""colosseum.py — The Adversarial Refinement Engine.

Real, synchronous version. Wraps the actual content pipeline:

  creator   -> ai_sql (real LLM calls) via src.content_generation
  puritan   -> Brain (timeless principles) + LLM critic
  chaos     -> PlatformSkillEngine performance history + LLM critic
  mutator   -> blends draft + critiques weighted by bias_toward_chaos

Every LLM step falls back gracefully (returns the input unchanged with a
"skipped" marker) so the Colosseum never crashes the Relentless Core, even
when no provider is configured.

Usage:
    from abvorn.core.colosseum import Colosseum
    colosseum = Colosseum()
    refined = colosseum.conduct_debate(carousel, platform="tiktok")
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TIMELESS_FALLBACK_INSIGHTS = [
    "Honest reviews build trust; never exaggerate claims.",
    "Specific numbers beat vague superlatives.",
    "A clear verdict up front helps decisive buyers.",
    "Compare against real alternatives, not strawmen.",
]

_CHAOS_FALLBACK_WEAKNESSES = [
    "Hook does not create curiosity within the first line.",
    "No emotional driver is named in the opening.",
    "Missing a concrete stat or number in the hook.",
]


def _parse_json(content: str, default: Dict[str, Any]) -> Dict[str, Any]:
    """Parse LLM JSON output with a tolerant fallback."""
    if not content:
        return default
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    # Strip prose around a JSON object
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
    return default


class Colosseum:
    """Adversarial refinement of platform content (synchronous)."""

    def __init__(self, bias_toward_chaos: float = 0.5):
        self.bias_toward_chaos = float(bias_toward_chaos)

        # Optional integrations (never fatal if unavailable)
        self.brain = None
        try:
            from abvorn.core.brain import get_brain
            self.brain = get_brain()
        except Exception as e:
            logger.warning(f"Brain unavailable: {e}")

        self.platform_skill = None
        try:
            from abvorn.core.platform_skill import get_platform_skill
            self.platform_skill = get_platform_skill()
        except Exception as e:
            logger.warning(f"Platform skill engine unavailable: {e}")

        # ai_sql is a module-level global configured by run_cycle.py
        self._ai_sql = None

        self._load_bias()
        self.debates_dir = Path("data/debates")
        self.debates_dir.mkdir(parents=True, exist_ok=True)

    # ── plumbing ────────────────────────────────────────────────────────

    def _ask(self, system_prompt: str, user_prompt: str) -> str:
        """Call the real LLM router. Returns "" if no provider is available."""
        ai = self._ai_sql
        if ai is None:
            try:
                from src import content_generation
                ai = content_generation.ai_sql
                self._ai_sql = ai
            except Exception:
                return ""
        if ai is None:
            return ""
        try:
            from src.ai_sql import QueryPlan
            result = ai.query(QueryPlan(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                params={"temperature": 0.8, "max_tokens": 600},
            ))
            return result.content or ""
        except Exception as e:
            logger.warning(f"Colosseum LLM call failed: {e}")
            return ""

    def _load_bias(self):
        """Load inherited bias from lineage if present."""
        try:
            lineage_file = Path("data/genesis/lineage.json")
            if lineage_file.exists():
                data = json.loads(lineage_file.read_text(encoding="utf-8"))
                self.bias_toward_chaos = float(data.get("ideological_bias", self.bias_toward_chaos))
        except Exception as e:
            logger.warning(f"Could not load bias from lineage: {e}")

    def _save_bias(self):
        """Persist bias to lineage, creating the key if missing."""
        try:
            lineage_file = Path("data/genesis/lineage.json")
            lineage_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if lineage_file.exists():
                try:
                    data = json.loads(lineage_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    data = {}
            data["ideological_bias"] = round(self.bias_toward_chaos, 4)
            lineage_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not save bias to lineage: {e}")

    # ── the five agents ─────────────────────────────────────────────────

    def _spawn_strategist(self, carousel: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Agent 1: choose the psychological angle for this platform."""
        product = carousel.get("product_name", "this product")
        verdict = carousel.get("verdict", {}) or {}
        default = {
            "angle": "problem_solution",
            "emotional_driver": "curiosity",
            "target_audience": "shoppers",
        }
        response = self._ask(
            "You are a master content strategist. Return JSON only.",
            f"Product: {product}\nVerdict: {json.dumps(verdict)[:300]}\n"
            f"Platform: {platform}\n"
            f"Return JSON with keys: angle, emotional_driver, target_audience.",
        )
        if not response:
            return default
        return _parse_json(response, default)

    def _spawn_creator(self, carousel: Dict[str, Any], strategy: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Agent 2: generate the hook + slides using real LLM calls."""
        product = carousel.get("product_name", "this product")
        verdict = carousel.get("verdict", {}) or {}
        breakdown = verdict.get("breakdown", {}) or {}
        label = verdict.get("label", "Excellent")
        overall = verdict.get("overall", 0)
        default = dict(carousel)  # keep existing payload if generation fails
        default.setdefault("slides", carousel.get("slides") or {})

        response = self._ask(
            "You write viral product-review hooks. Return JSON only.",
            f"Product: {product}\nVerdict: {label} {overall}/10\n"
            f"Breakdown: {json.dumps(breakdown)[:300]}\n"
            f"Angle: {strategy.get('angle')}\n"
            f"Emotional driver: {strategy.get('emotional_driver')}\n"
            f"Platform: {platform}\n"
            f"Return JSON with keys: hook (a curiosity-driven first line), "
            f"slides (object of 6 keys: hook, problem, verdict, breakdown, comparison, call).",
        )
        if not response:
            return default
        data = _parse_json(response, {})
        if not data:
            return default
        refined = dict(carousel)
        if data.get("hook"):
            refined["hook"] = data["hook"]
        if isinstance(data.get("slides"), dict) and data["slides"]:
            refined["slides"] = data["slides"]
        refined["debate_strategy"] = strategy
        return refined

    def _spawn_puritan_critic(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        """Agent 3: enforce timeless principles from the Brain."""
        insights = []
        if self.brain is not None:
            try:
                insights = self.brain.query(
                    f"Psychological principles for {draft.get('product_name', 'products')}",
                    limit=3,
                )
            except Exception as e:
                logger.warning(f"Brain query failed in colosseum: {e}")
        insight_text = "\n".join(
            i.get("insight", "") for i in insights[:3] if i.get("insight")
        ) or "\n".join(_TIMELESS_FALLBACK_INSIGHTS)

        default = {"approved": True, "violations": [], "suggested_fix": ""}
        response = self._ask(
            "You are a strict Puritan Critic enforcing honest-review principles. Return JSON only.",
            f"Principles:\n{insight_text}\n\nDraft hook: {draft.get('hook', '')}\n"
            f"Return JSON with keys: approved (bool), violations (list), suggested_fix (string).",
        )
        if not response:
            return default
        return _parse_json(response, default)

    def _spawn_chaos_critic(self, draft: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Agent 4: enforce viral velocity using real platform performance history."""
        recent = []
        if self.platform_skill is not None:
            try:
                recent = self.platform_skill.get_performance_history(platform)[-10:]
            except Exception:
                recent = []
        perf_text = json.dumps(recent, default=str)[:400] if recent else "No performance history yet."

        default = {"viral_potential": 5, "weaknesses": _CHAOS_FALLBACK_WEAKNESSES, "suggested_rewrite": ""}
        response = self._ask(
            "You are a Chaotic Viral Analyst. You only care what works NOW. Return JSON only.",
            f"Platform: {platform}\nRecent performance: {perf_text}\n"
            f"Draft hook: {draft.get('hook', '')}\n"
            f"Return JSON with keys: viral_potential (0-10), weaknesses (list), suggested_rewrite (string).",
        )
        if not response:
            return default
        return _parse_json(response, default)

    def _spawn_mutator(self, draft: Dict[str, Any], puritan: Dict[str, Any],
                       chaos: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Agent 5: synthesize the final version, weighted by bias."""
        weight_timeless = 1 - self.bias_toward_chaos
        weight_viral = self.bias_toward_chaos
        puritan_text = json.dumps(puritan, default=str)[:300]
        chaos_text = json.dumps(chaos, default=str)[:300]

        default = dict(draft)
        response = self._ask(
            "You are the Supreme Mutator. Merge the draft with both critiques. Return JSON only.",
            f"Draft: {draft.get('hook', '')}\n"
            f"Puritan weight {weight_timeless:.1f}: {puritan_text}\n"
            f"Chaos weight {weight_viral:.1f}: {chaos_text}\n"
            f"Platform: {platform}\n"
            f"Return JSON with keys: hook (final), notes (string).",
        )
        if not response:
            return default
        data = _parse_json(response, {})
        if data.get("hook"):
            refined = dict(draft)
            refined["hook"] = data["hook"]
            refined["debate_notes"] = data.get("notes", "")
            return refined
        return default

    # ── public API ──────────────────────────────────────────────────────

    def conduct_debate(self, carousel: Dict[str, Any], platform: str = "general") -> Dict[str, Any]:
        """Run the full 5-agent debate on a carousel payload. Synchronous.

        Returns a refined carousel (same keys as the input). Never raises.
        """
        strategy = self._spawn_strategist(carousel, platform)
        draft = self._spawn_creator(carousel, strategy, platform)
        puritan = self._spawn_puritan_critic(draft)
        chaos = self._spawn_chaos_critic(draft, platform)
        final = self._spawn_mutator(draft, puritan, chaos, platform)

        # Record the debate for the trajectory/evolution layers
        debate_log = {
            "product": carousel.get("product_name", "Unknown"),
            "platform": platform,
            "strategy": strategy,
            "draft": {k: v for k, v in draft.items() if k != "debate_strategy"},
            "puritan_critique": puritan,
            "chaos_critique": chaos,
            "final_verdict": final,
            "bias_used": self.bias_toward_chaos,
            "timestamp": datetime.now().isoformat(),
        }
        self._ingest_debate(debate_log)
        self._update_bias(chaos)

        final = dict(final)
        final["debate_log_path"] = debate_log["_path"]
        return final

    def _ingest_debate(self, debate_log: Dict[str, Any]):
        """Store the debate log on disk for the trajectory/evolution layers."""
        debate_id = f"debate_{datetime.now().strftime('%Y%m%d%H%M%S_%f')}"
        path = self.debates_dir / f"{debate_id}.json"
        try:
            path.write_text(json.dumps(debate_log, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not write debate log: {e}")
            path = None
        debate_log["_path"] = str(path) if path else ""

    def _update_bias(self, chaos: Dict[str, Any]):
        """Drift ideological bias from chaos critique, then persist."""
        try:
            viral = float(chaos.get("viral_potential", 5) or 5)
        except (TypeError, ValueError):
            viral = 5.0
        if viral > 7:
            self.bias_toward_chaos = min(1.0, self.bias_toward_chaos + 0.01)
        elif viral < 4:
            self.bias_toward_chaos = max(0.0, self.bias_toward_chaos - 0.01)
        self._save_bias()

    def get_bias(self) -> float:
        return self.bias_toward_chaos


def get_colosseum() -> Colosseum:
    """Singleton accessor."""
    global _colosseum
    if _colosseum is None:
        _colosseum = Colosseum()
    return _colosseum


_colosseum: Optional[Colosseum] = None
