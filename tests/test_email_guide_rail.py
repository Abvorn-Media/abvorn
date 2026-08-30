import json

from src.warm_editorial import WARM_EMAIL_GUIDE_JS, build_review_rail


def test_review_rail_has_email_guide_form():
    rail = build_review_rail(
        post_title="Best 4K Monitors",
        article_url="https://abvorn.com/reviews/4k-monitors/",
        niche_slug="4k-monitors",
        niche_name="4K Monitors",
        toc_items=[("verdict", "Abvorn Verdict")],
        base="",
        form_url="https://script.google.com/macros/s/x/exec",
    )
    assert "email-guide-form" in rail
    assert "submitEmailGuide(event)" in rail
    assert "Email Me the PDF" in rail
    assert "mailto:" not in rail


def test_email_guide_js_embeds_payload():
    payload = json.dumps({
        "action": "pdf_guide",
        "slug": "4k-monitors",
        "title": "Best 4K Monitors",
        "niche": "4k-monitors",
        "source": "review_rail",
        "pdf_url": "https://abvorn.com/reviews/4k-monitors/x.pdf",
        "guide_url": "https://abvorn.com/reviews/4k-monitors/",
    }, ensure_ascii=True)
    js = WARM_EMAIL_GUIDE_JS.replace("__GUIDE_PAYLOAD__", payload)
    assert "__GUIDE_PAYLOAD__" not in js
    assert '"pdf_url"' in js
    assert "pdf_guide" in js
    assert "x.pdf" in js