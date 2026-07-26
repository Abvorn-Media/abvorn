import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("abvorn.seo.schema")

_SITE_NAME = "Abvorn"
_PUBLISHER = {
    "@type": "Organization",
    "name": _SITE_NAME,
    "url": "https://abvorn.com",
}
_AUTHOR = {
    "@type": "Person",
    "name": "Abvorn Editorial Team",
}


class SchemaBuilder:
    def build_article_schema(self, content: dict) -> dict:
        headline = content.get("post_title", "")
        description = content.get("meta_description", "")
        date = content.get("datePublished", datetime.now().isoformat())
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": headline,
            "description": description,
            "datePublished": date,
            "dateModified": datetime.now().isoformat(),
            "author": _AUTHOR,
            "publisher": _PUBLISHER,
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": content.get("url", ""),
            },
        }

    def build_product_schema(self, product_name: str, price: float = 0.0,
                              rating: float = 0.0, url: str = "") -> dict:
        schema: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product_name,
        }
        if price > 0:
            schema["offers"] = {
                "@type": "Offer",
                "price": price,
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock",
            }
        if rating > 0:
            schema["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": min(rating, 5.0),
                "ratingCount": 100,
                "bestRating": 5,
            }
        if url:
            schema["url"] = url
        return schema

    def build_faq_schema(self, questions_answers: list[dict]) -> dict:
        items = []
        for qa in questions_answers:
            items.append({
                "@type": "Question",
                "name": qa.get("question", ""),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": qa.get("answer", ""),
                },
            })
        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": items,
        }

    def build_howto_schema(self, steps: list[dict]) -> dict:
        howto_steps = []
        for i, step in enumerate(steps, 1):
            howto_steps.append({
                "@type": "HowToStep",
                "position": i,
                "name": step.get("name", f"Step {i}"),
                "text": step.get("text", ""),
            })
        return {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": steps[0].get("name", "Guide") if steps else "Guide",
            "step": howto_steps,
        }

    def _detect_schema_types(self, content: dict) -> list[str]:
        types = ["Article"]
        article_html = content.get("article_html", "")
        if article_html.count("<li>") > 3 and any(q in article_html.lower() for q in ["how to", "steps", "step "]):
            types.append("HowTo")
        if content.get("product_name"):
            types.append("Product")
        if "faq" in content or article_html.count("faq") > 1:
            types.append("FAQPage")
        return types

    def build_all(self, content: dict) -> dict[str, Any]:
        schemas = {}
        types = self._detect_schema_types(content)

        if "Article" in types:
            schemas["article"] = self.build_article_schema(content)
        if "Product" in types:
            schemas["product"] = self.build_product_schema(
                content.get("product_name", ""),
                content.get("product_price", 0.0),
                content.get("product_rating", 0.0),
            )
        if "FAQPage" in types:
            faqs = content.get("faq", [])
            if faqs:
                schemas["faq"] = self.build_faq_schema(faqs)
        if "HowTo" in types:
            steps = content.get("steps", [])
            if steps:
                schemas["howto"] = self.build_howto_schema(steps)

        return schemas
