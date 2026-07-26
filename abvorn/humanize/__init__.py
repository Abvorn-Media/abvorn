"""Humanization engine — post-processes AI content to sound natural."""

import logging, re
from .scanner import AIScanner
from .variator import SentenceVariator
from .transitions import TransitionInjector
from .specificity import SpecificityBooster

logger = logging.getLogger("abvorn.humanize")

from ..brand import check_text


class HumanizationEngine:
    """Post-processes content to strip AI-isms, vary sentences, and add flow."""

    def __init__(self):
        self.scanner = AIScanner()
        self.variator = SentenceVariator()
        self.transitions = TransitionInjector()
        self.specificity = SpecificityBooster()

    def analyze(self, content: dict) -> dict:
        """Run all humanization checks on content. Returns analysis without modifying."""
        article = content.get("article_html", "")
        intro = content.get("intro", "")
        title = content.get("post_title", "")
        full_text = re.sub(r'<[^>]+>', '', article + " " + intro)

        ai_isms = self.scanner.scan_html(article) + self.scanner.scan_html(intro)
        vague = self.specificity.scan_for_vagueness_html(article) + self.specificity.scan_for_vagueness_html(intro)
        brand_violations = check_text(full_text) + check_text(title, "title")
        ai_score = self.scanner.get_ai_score(full_text)
        spec_score = self.specificity.get_specificity_score(full_text)

        return {
            "ai_ism_count": len(ai_isms),
            "vague_count": len(vague),
            "brand_violations": brand_violations,
            "ai_score": ai_score,
            "specificity_score": spec_score,
            "overall_score": round((ai_score + spec_score) / 2, 2),
            "issues": ai_isms[:10] + vague[:5],
        }

    def humanize(self, content: dict) -> dict:
        """Apply humanization fixes to content. Modifies article_html and intro."""
        content = dict(content)
        article = content.get("article_html", "")
        intro = content.get("intro", "")

        if article:
            article = self.transitions.inject_transitions_html(article)
            article = self._apply_text_fixes(article)
            content["article_html"] = article

        if intro:
            intro = self.transitions.inject_transitions_html(intro)
            intro = self._apply_text_fixes(intro)
            content["intro"] = intro

        analysis = self.analyze(content)
        content["humanization"] = analysis
        logger.info(f"Humanized: {analysis['ai_ism_count']} AI-isms, {analysis['vague_count']} vague claims → {analysis['overall_score']}")
        return content

    def _apply_text_fixes(self, html: str) -> str:
        """Apply non-destructive text fixes within HTML."""
        text = html
        text = re.sub(r'\bIn order to\b', 'to', text, flags=re.IGNORECASE)
        text = re.sub(r"\bIt('s| is) worth noting that\s*,?\s*", '', text, flags=re.IGNORECASE)
        text = re.sub(r"\bIt('s| is) important to\s+", '', text, flags=re.IGNORECASE)
        text = re.sub(r"\bNeedless to say[,.]?\s*", '', text, flags=re.IGNORECASE)
        text = re.sub(r"\bIt goes without saying[,.]?\s*", '', text, flags=re.IGNORECASE)
        return text