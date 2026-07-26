import pytest
from abvorn.crm.template import render_email, render_lead_magnet_email, render_persona_update
from abvorn.crm.sender import EmailSender


def test_render_email_basic():
    """Should render a complete HTML email."""
    html = render_email(
        to_name="Marcus",
        subject="Your wireless headphone guide is here",
        body_html="<p>We found the perfect headphones for your commute.</p>",
    )
    assert "<!DOCTYPE html" in html
    assert "Marcus" in html
    assert "wireless headphone" in html
    assert "unsubscribe" in html.lower()


def test_render_with_cta():
    """Should include a call-to-action button."""
    html = render_email(
        to_name="Marcus",
        subject="Test",
        body_html="<p>Check this out</p>",
        cta_text="Read the Full Guide",
        cta_url="https://abvorn.com/guide",
    )
    assert "Read the Full Guide" in html
    assert "abvorn.com/guide" in html


def test_render_lead_magnet():
    """Lead magnet email should include download CTA."""
    html = render_lead_magnet_email(
        to_name="Marcus",
        magnet_title="Commuter Headphone Cheat Sheet",
    )
    assert "Commuter Headphone Cheat Sheet" in html
    assert "Download" in html


def test_render_persona_update():
    """Persona update email should reference the persona."""
    html = render_persona_update(
        to_name="Marcus",
        persona_name="Marcus the Commuter",
        post_title="Best Wireless Headphones for Commuters",
        post_url="https://abvorn.com/headphones",
    )
    assert "Marcus the Commuter" in html
    assert "Best Wireless Headphones" in html
    assert "abvorn.com/headphones" in html


def test_email_sender_no_creds():
    """Should handle missing credentials gracefully."""
    sender = EmailSender(email="", password="")
    result = sender.send_email(to_email="test@example.com", subject="Test", html_body="<p>Hi</p>")
    assert result is False


def test_email_sender_format_persona():
    """Should format a persona update correctly without sending."""
    sender = EmailSender(email="", password="")
    recipients = [{"email": "marcus@example.com", "name": "Marcus"}]
    result = sender.send_persona_content(
        persona_id="marcus_commuter",
        niche="wireless headphones",
        content={"post_title": "Best Headphones", "persona_name": "Marcus the Commuter"},
        recipients=recipients,
    )
    assert result["sent"] == 0  # no creds, but formatted correctly
    assert result["total"] == 1