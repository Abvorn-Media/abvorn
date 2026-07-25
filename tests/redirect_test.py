"""Tests for redirect HTML generator."""
from abvorn.deploy.redirect import generate_redirect_html


def test_redirect_to_site_path():
    html = generate_redirect_html("/tech-gadgets/tv/")
    assert "0; url=/tech-gadgets/tv/" in html
    assert "meta http-equiv" in html

def test_redirect_to_domain():
    html = generate_redirect_html("https://techandgadgets.com/tv/")
    assert "0; url=https://techandgadgets.com/tv/" in html

def test_redirect_is_valid_html():
    html = generate_redirect_html("/new-path/")
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
