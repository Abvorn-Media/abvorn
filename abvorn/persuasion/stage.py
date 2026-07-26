"""BuyingStageDetector — classifies articles into buying stages."""

from enum import Enum


class BuyingStage(Enum):
    AWARENESS = "awareness"
    CONSIDERATION = "consideration"
    DECISION = "decision"


STAGE_KEYWORDS = {
    BuyingStage.AWARENESS: [
        "what is", "guide to", "types of", "how to choose", "introduction",
        "explained", "understanding", "beginner", "overview", "learn",
    ],
    BuyingStage.CONSIDERATION: [
        "best", "top", "review", "vs", "comparison", "versus",
        "compared", "rated", "recommended", "ranking",
    ],
    BuyingStage.DECISION: [
        "buy", "discount", "coupon", "price", "where to buy",
        "affordable", "deals", "save", "cheap", "order",
    ],
}


def detect_stage(content: dict) -> BuyingStage:
    title = (content.get("title") or "").lower()
    body = (content.get("article_html") or "")[:500].lower()

    text = f"{title} {body}"

    if not text.strip():
        return BuyingStage.AWARENESS

    scores = {stage: 0 for stage in BuyingStage}
    for stage, keywords in STAGE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[stage] += 1

    max_stage = max(scores, key=scores.get)
    return max_stage if scores[max_stage] > 0 else BuyingStage.AWARENESS
