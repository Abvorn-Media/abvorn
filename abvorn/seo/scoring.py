import logging
import re
from typing import Any

logger = logging.getLogger("abvorn.seo.scoring")

SEO_WEIGHTS = {
    "keyword_usage": 0.25,
    "heading_structure": 0.15,
    "meta_quality": 0.20,
    "readability": 0.15,
    "content_length": 0.10,
    "internal_links": 0.10,
    "schema_presence": 0.05,
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


class SEOContentScorer:
    def score_content(self, content: dict, keywords: list[dict]) -> dict[str, Any]:
        details: dict[str, float] = {}
        suggestions: list[str] = []

        details["keyword_usage"] = self._score_keyword_usage(content, keywords, suggestions)
        details["heading_structure"] = self._score_headings(content, suggestions)
        details["meta_quality"] = self._score_meta(content, suggestions)
        details["readability"] = self._score_readability(content, suggestions)
        details["content_length"] = self._score_content_length(content, suggestions)
        details["internal_links"] = self._score_internal_links(content, suggestions)
        details["schema_presence"] = self._score_schema(content, suggestions)

        total = sum(details[k] * SEO_WEIGHTS[k] for k in SEO_WEIGHTS)
        score = round(min(total, 100.0), 1)

        grade = self._grade(score)

        return {
            "score": score,
            "grade": grade,
            "suggestions": suggestions,
            "details": details,
        }

    def _grade(self, score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 75:
            return "B"
        if score >= 60:
            return "C"
        if score >= 40:
            return "D"
        return "F"

    def _score_keyword_usage(self, content: dict, keywords: list[dict], suggestions: list[str]) -> float:
        if not keywords:
            suggestions.append("No keywords provided for analysis")
            return 0.0

        primary = keywords[0].get("keyword", "") if keywords else ""
        title = content.get("post_title", "").lower()
        meta = content.get("meta_description", "").lower()
        article_html = content.get("article_html", "")
        body = _strip_html(article_html).lower()
        score = 0.0

        if primary and primary.lower() in title:
            score += 30.0
        elif primary:
            suggestions.append(f"Include primary keyword '{primary}' in the title")
            score += 5.0

        if primary and primary.lower() in meta:
            score += 20.0
        elif primary:
            suggestions.append(f"Include primary keyword '{primary}' in the meta description")

        secondary_found = 0
        if len(keywords) > 1:
            for kw in keywords[1:5]:
                kw_text = kw.get("keyword", "").lower()
                if kw_text in body:
                    secondary_found += 1
            secondary_score = min(secondary_found / max(len(keywords[1:5]), 1) * 30.0, 30.0)
            score += secondary_score
            if secondary_found < 2:
                suggestions.append("Include more secondary keywords in the article body")

        if primary:
            count = body.count(primary.lower())
            if 2 <= count <= 5:
                score += 20.0
            elif count > 5:
                score += 10.0
                suggestions.append(f"Keyword '{primary}' appears {count} times — consider reducing density")

        return min(score, 100.0)

    def _score_headings(self, content: dict, suggestions: list[str]) -> float:
        article_html = content.get("article_html", "")
        score = 30.0

        h1_count = len(re.findall(r"<h1[^>]*>", article_html))
        h2_count = len(re.findall(r"<h2[^>]*>", article_html))
        h3_count = len(re.findall(r"<h3[^>]*>", article_html))

        if h1_count == 0:
            suggestions.append("Add an H1 heading to the article")
            score -= 20.0
        elif h1_count > 1:
            suggestions.append(f"Multiple H1 tags found ({h1_count}) — use only one")
            score -= 10.0

        if h2_count == 0:
            suggestions.append("Add H2 subheadings to structure the article")
            score -= 25.0
        elif h2_count < 3:
            suggestions.append(f"Only {h2_count} H2 subheadings — aim for 3+")
            score -= 10.0

        if h3_count > 0:
            score += 10.0

        return max(0.0, min(score, 100.0))

    def _score_meta(self, content: dict, suggestions: list[str]) -> float:
        title = content.get("post_title", "")
        meta = content.get("meta_description", "")
        score = 50.0

        if not title:
            suggestions.append("Missing post title")
            score -= 50.0
        elif len(title) < 30:
            suggestions.append(f"Post title too short ({len(title)} chars) — aim for 50-65")
            score -= 15.0
        elif len(title) > 70:
            suggestions.append(f"Post title too long ({len(title)} chars) — aim for 50-65")
            score -= 10.0

        if not meta:
            suggestions.append("Missing meta description")
            score -= 50.0
        elif len(meta) < 150:
            suggestions.append(f"Meta description too short ({len(meta)} chars) — aim for 150-160")
            score -= 20.0
        elif len(meta) > 165:
            suggestions.append(f"Meta description too long ({len(meta)} chars) — aim for 150-160")
            score -= 10.0

        return max(0.0, score)

    def _score_readability(self, content: dict, suggestions: list[str]) -> float:
        article_html = content.get("article_html", "")
        body = _strip_html(article_html)
        score = 70.0

        sentences = re.split(r"[.!?]+", body)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
        if not sentences:
            suggestions.append("No readable content found")
            return 0.0

        total_words = sum(len(s.split()) for s in sentences)
        avg_words = total_words / len(sentences) if sentences else 0

        if avg_words > 30:
            suggestions.append(f"Average sentence length is {avg_words:.0f} words — aim for 15-20")
            score -= 20.0
        elif avg_words > 25:
            score -= 10.0

        list_count = len(re.findall(r"<[uo]l>", article_html))
        if list_count == 0:
            suggestions.append("Add bulleted or numbered lists for scannability")
            score -= 15.0
        else:
            score += 10.0

        return max(0.0, min(score, 100.0))

    def _score_content_length(self, content: dict, suggestions: list[str]) -> float:
        article_html = content.get("article_html", "")
        body = _strip_html(article_html)
        word_count = len(body.split())

        if word_count < 300:
            suggestions.append(f"Content too short ({word_count} words) — aim for 1000+")
            return 0.0
        if word_count < 600:
            suggestions.append(f"Content is thin ({word_count} words) — aim for 1000+")
            return 30.0
        if word_count < 1000:
            suggestions.append(f"Content length is marginal ({word_count} words) — aim for 1000+")
            return 60.0
        return 100.0

    def _score_internal_links(self, content: dict, suggestions: list[str]) -> float:
        article_html = content.get("article_html", "")
        internal_links = len(re.findall(r'href=[\'"]?(/[^\'">]+)', article_html))

        if internal_links == 0:
            suggestions.append("Add internal links to related articles")
            return 0.0
        if internal_links < 2:
            suggestions.append(f"Only {internal_links} internal link — aim for 2-3")
            return 50.0
        if internal_links > 5:
            return 70.0
        return 100.0

    def _score_schema(self, content: dict, suggestions: list[str]) -> float:
        schema = content.get("schema", {})
        if schema:
            return 100.0
        suggestions.append("Add structured data (JSON-LD schema) to improve rich snippets")
        return 0.0
