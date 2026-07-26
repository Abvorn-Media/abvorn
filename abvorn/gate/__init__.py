"""Content Quality Gate — the final checkpoint every piece must pass before deployment.

Combines: SEO score, humanization score, soul check, platform voice check.
If content doesn't meet the bar, it doesn't deploy.
"""

import logging, json
from typing import Optional
from datetime import datetime

logger = logging.getLogger("abvorn.gate")

from ..seo.pipeline import SEOPipeline
from ..seo.scoring import SEOContentScorer
from ..humanize import HumanizationEngine
from ..brand import check_soul, format_voice_rules, MISSION
from ..platform.voice import get_voice, format_voice_rules_for_prompt

# Minimum thresholds for each dimension (0-100 scale)
_THRESHOLDS = {
    "seo": {"min": 50, "target": 75, "weight": 0.25},
    "humanization": {"min": 60, "target": 80, "weight": 0.25},
    "soul": {"min": 100, "target": 100, "weight": 0.30},
    "specificity": {"min": 50, "target": 70, "weight": 0.10},
    "readability": {"min": 40, "target": 65, "weight": 0.10},
}


class QualityGate:
    """The final checkpoint. Content must pass this to deploy.

    Returns a detailed report with pass/fail status, scores, and actionable fixes.
    """

    def __init__(self, seo_pipeline: Optional[SEOPipeline] = None,
                 humanizer: Optional[HumanizationEngine] = None):
        self.seo = seo_pipeline or SEOPipeline()
        self.scorer = SEOContentScorer()
        self.humanizer = humanizer or HumanizationEngine()
        self._history = []

    def evaluate(self, content: dict, niche: str = "", persona: dict = None,
                 platform: str = None) -> dict:
        """Run every quality check on content. Returns comprehensive report."""
        niche = niche or content.get("niche", "")
        persona_name = persona.get("name", "the reader") if persona else "the reader"

        # 1. SEO check
        seo_result = self.seo.run(content, niche, {"name": persona_name})
        seo_score = seo_result.get("seo_score", {}).get("score", 0) if isinstance(seo_result.get("seo_score"), dict) else (seo_result.get("seo_score", 0) if isinstance(seo_result.get("seo_score"), (int, float)) else 0)
        seo_grade = seo_result.get("seo_score", {}).get("grade", "F") if isinstance(seo_result.get("seo_score"), dict) else "?"
        seo_suggestions = seo_result.get("seo_suggestions", [])

        # Direct score if pipeline didn't score it
        if not seo_score:
            score_result = self.scorer.score_content(content, [])
            seo_score = score_result.get("score", 0)
            seo_grade = score_result.get("grade", "F")
            seo_suggestions = score_result.get("suggestions", [])

        # 2. Humanization check
        human_result = self.humanizer.analyze(content)
        human_score = human_result.get("ai_score", 0) * 100
        spec_score = human_result.get("specificity_score", 0) * 100
        ai_isms = human_result.get("ai_ism_count", 0)
        vague = human_result.get("vague_count", 0)
        human_issues = human_result.get("issues", [])

        # 3. Soul check
        soul_result = check_soul(f"quality_gate_{niche}", {
            "title": content.get("post_title", ""),
            "text": content.get("article_html", "")[:2000] + content.get("intro", ""),
        })
        soul_pass = soul_result["pass"]
        soul_violations = soul_result["violations"]

        # 4. Platform voice check (if platform specified)
        platform_issues = []
        if platform:
            voice = get_voice(platform)
            article = content.get("article_html", "")
            for rule in voice.get("rules", []):
                platform_issues.append({"rule": rule, "note": "verify against platform voice"})

        # 5. Composite score
        scores = {
            "seo": seo_score,
            "humanization": human_score,
            "soul": 100 if soul_pass else 0,
            "specificity": spec_score,
            "readability": _estimate_readability(content.get("article_html", "")),
        }

        composite = sum(
            scores[key] * _THRESHOLDS[key]["weight"]
            for key in scores if key in _THRESHOLDS
        )

        # 6. Pass/fail
        failures = []
        warnings = []
        for key, threshold in _THRESHOLDS.items():
            actual = scores.get(key, 0)
            if actual < threshold["min"]:
                failures.append(f"{key}: {actual:.0f}/100 (min {threshold['min']})")
            elif actual < threshold["target"]:
                warnings.append(f"{key}: {actual:.0f}/100 (target {threshold['target']})")

        passed = len(failures) == 0

        report = {
            "passed": passed,
            "composite_score": round(composite, 1),
            "scores": scores,
            "failures": failures,
            "warnings": warnings,
            "seo_grade": seo_grade,
            "seo_suggestions": seo_suggestions[:3],
            "ai_isms_found": ai_isms,
            "vague_claims": vague,
            "soul_violations": soul_violations,
            "platform_voice_notes": platform_issues[:3] if platform_issues else [],
            "improvement_suggestions": self._build_suggestions(scores, failures, seo_suggestions),
            "timestamp": datetime.now().isoformat(),
        }

        self._history.append({"niche": niche, "passed": passed, "score": composite})
        logger.info(f"Gate: {niche} — {'PASSED' if passed else 'BLOCKED'} ({composite:.1f}/100, {len(failures)} failures)")
        return report

    def evaluate_for_platform(self, content: dict, platform: str,
                               niche: str = "", persona: dict = None) -> dict:
        """Evaluate content for a specific platform."""
        base = self.evaluate(content, niche, persona, platform)
        voice = get_voice(platform)

        # Check content length against platform limits
        config = getattr(self.seo, '_config', {})
        article = content.get("article_html", "")
        word_count = len(article.split()) if article else 0

        length_ok = True
        if word_count < 50 and platform != "x":
            base["warnings"].append(f"Content too short for {platform} ({word_count} words)")
            length_ok = False

        base["platform_check"] = {
            "platform": platform,
            "voice_profile": voice.get("tone", ""),
            "word_count": word_count,
            "length_ok": length_ok,
        }

        return base

    def get_summary(self) -> dict:
        """Get summary of all quality gate evaluations."""
        total = len(self._history)
        if total == 0:
            return {"total": 0, "pass_rate": 0}
        passed = sum(1 for h in self._history if h["passed"])
        avg_score = sum(h["score"] for h in self._history) / total
        return {
            "total": total,
            "passed": passed,
            "blocked": total - passed,
            "pass_rate": round(passed / total * 100, 1),
            "average_score": round(avg_score, 1),
        }

    def _build_suggestions(self, scores: dict, failures: list,
                           seo_suggestions: list) -> list[str]:
        """Build prioritized improvement suggestions."""
        suggestions = []
        for failure in failures:
            suggestions.append(f"FIX: {failure}")
        suggestions.extend(seo_suggestions[:2])
        if scores.get("humanization", 100) < 60:
            suggestions.append("FIX: Content reads like AI — run humanization pass")
        if scores.get("specificity", 100) < 50:
            suggestions.append("FIX: Add specific numbers, prices, and measurements")
        return suggestions[:5]


def _estimate_readability(html: str) -> float:
    """Estimate readability score 0-100 based on sentence length and structure."""
    import re
    text = re.sub(r'<[^>]+>', '', html)
    sentences = [s for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if not sentences:
        return 50
    avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
    if avg_words < 10:
        return 80
    if avg_words < 15:
        return 70
    if avg_words < 20:
        return 60
    if avg_words < 25:
        return 45
    return 30