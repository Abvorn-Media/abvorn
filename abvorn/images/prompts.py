"""PromptWriter — generates descriptive image prompts using the LLM."""

import logging

logger = logging.getLogger("abvorn.images")

PROMPT_TEMPLATES = {
    "buying_guide": (
        "Product hero shot. {product} prominently displayed in center, "
        "professional studio lighting, clean minimalist background, "
        "product photography style, 4K detail, subtle depth of field, "
        "editorial quality, warm tones, soft shadows, hyperrealistic."
    ),
    "comparison": (
        "Side-by-side comparison of two products. {product} on the left, "
        "competitor on the right. Clean split composition, neutral background, "
        "professional studio lighting, editorial photography style, "
        "balanced framing, crisp detail, objective product shot aesthetic."
    ),
    "social_thread": (
        "Lifestyle scene. Someone using {product} in a real home setting, "
        "natural lighting, warm inviting atmosphere, candid moment, "
        "authentic lifestyle photography, soft focus background, "
        "natural color palette, relatable everyday scene."
    ),
    "tiktok_script": (
        "Dynamic close-up shot of {product}. Vibrant colors, dramatic lighting, "
        "social media vertical aesthetic, eye-catching composition, "
        "bright and energetic, bold contrast, scroll-stopping visual, "
        "trendy modern style, high saturation, punchy colors."
    ),
}

STYLE_GUIDE = (
    "Abvorn visual identity: dark gradient backgrounds (#1a1a1a to #283040), "
    "clean sans-serif typography overlay, subtle brand mark bottom-right, "
    "product-centered composition, editorial quality, "
    "consistent with a premium Wirecutter-style review site. "
    "No text in the generated image — text overlays are added separately."
)


class PromptWriter:
    """Generates detailed, brand-aligned image prompts using the LLM."""

    def __init__(self, router=None):
        self.router = router

    def write_prompt(self, product_name: str, niche: str, headline: str,
                     content_type: str = "buying_guide", features: list = None) -> str:
        """Generate a descriptive image prompt for the given content."""
        template = PROMPT_TEMPLATES.get(content_type, PROMPT_TEMPLATES["buying_guide"])
        base_prompt = template.format(product=product_name)

        if self.router:
            enriched = self._enrich_with_llm(product_name, niche, headline,
                                              content_type, features)
            if enriched:
                return enriched

        return f"{base_prompt} Style: {STYLE_GUIDE}"

    def _enrich_with_llm(self, product_name: str, niche: str, headline: str,
                         content_type: str, features: list = None) -> str:
        """Use the LLM to craft a richer, more specific prompt."""
        features_text = ", ".join(features[:5]) if features else ""
        system = (
            "You are an expert image prompt engineer for a product review site. "
            "Write ONE concise paragraph describing an image for a blog post. "
            "Be specific about angles, lighting, composition, and mood. "
            "Include visual details that match the product and niche. "
            f"Brand style: {STYLE_GUIDE}"
        )
        prompt = (
            f"Product: {product_name}\n"
            f"Niche: {niche}\n"
            f"Headline: {headline}\n"
            f"Content type: {content_type}\n"
        )
        if features_text:
            prompt += f"Key features: {features_text}\n"
        prompt += "\nWrite a detailed image generation prompt for this post's featured image:"

        try:
            result = self.router.ask(prompt, system=system, task="image_prompt")
            if result and len(result) > 50:
                return result.strip()
        except Exception as e:
            logger.warning(f"LLM prompt generation failed: {e}")

        return ""

    def write_prompts_for_all_types(self, product_name: str, niche: str,
                                     headline: str, features: list = None) -> dict:
        """Generate prompts for all content types at once."""
        return {
            ctype: self.write_prompt(product_name, niche, headline, ctype, features)
            for ctype in PROMPT_TEMPLATES
        }