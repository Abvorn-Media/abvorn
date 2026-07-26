"""Full persuasion pipeline — generates conversion-optimized content for one persona."""

import json, logging
from . import persuasion
from ..brand import format_voice_rules, BANNED_PHRASES

logger = logging.getLogger("abvorn.factory")


class PersuasionPipeline:
    """Runs the 8-stage persuasion pipeline for a single niche + persona combo."""

    def run(self, niche: str, persona: dict, router, brain=None) -> dict:
        """Generate a complete content bundle for one persona."""
        name = persona.get("name", "the reader")

        prompt = f"""Write a persuasive buying guide for '{niche}' targeting ONE specific person: {name}.

PERSONA PROFILE:
{json.dumps(persona.get('psychology', {}), indent=2)}

PERSUASION FRAMEWORK:
1. PRE-SUADE: {persuasion.build_pre_suade(persona)}
2. AWARENESS MATCH: {persuasion.build_awareness_match(persona)}
3. DESIRE TAP: {persuasion.build_desire_tap(persona)}
4. NEURO ENGAGE: {persuasion.build_neuro_engage(persona)}
5. EVIDENCE: {persuasion.build_evidence_block(persona)}
6. SCANNABLE: {persuasion.build_scannable_structure()}
7. CONVERT: {persuasion.build_conversion_block()}

ABVORN VOICE RULES:
{format_voice_rules()}

BANNED PHRASES (never use these):
{chr(10).join('- ' + p for p in BANNED_PHRASES)}

Return JSON:
{{
  "post_title": "SEO title (50-65 chars, includes niche + persona hook)",
  "meta_description": "Meta description (150-160 chars)",
  "intro": "<p>2-3 sentence hook (HTML)</p>",
  "article_html": "Full article body (HTML, 1000-2000 words)",
  "lead_magnet_title": "Checklist or cheat sheet title",
  "lead_magnet_description": "Short pitch for email capture",
  "lead_magnet_content": "Full content of the lead magnet",
  "tags": ["{niche}", "buying guide", "review"],
  "selected_angle": "problem_solution | comparison | review | listicle"
}}"""
        result = router.ask(prompt, json_mode=True)
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                logger.error("Factory JSON parse failed")
                return None
        if result:
            result["persona_name"] = name
            result["persona_id"] = persona.get("persona_id", "")
            result["niche"] = niche
        return result