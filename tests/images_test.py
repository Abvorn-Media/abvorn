"""Tests for image generation, prompts, and resizing."""
import pytest
from abvorn.images import (
    ImageGenerator, ImageResizer, PromptWriter,
    PLATFORM_DIMENSIONS, PROMPT_TEMPLATES, STYLE_GUIDE
)


def test_generator_initializes():
    g = ImageGenerator()
    assert g is not None


def test_generate_returns_bytes():
    g = ImageGenerator()
    result = g.generate("Test Product", "tech", "The Best Test Product of 2026")
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_custom_size():
    g = ImageGenerator()
    result = g.generate("Test", "tv", "Best TV", output_size=(600, 315))
    assert len(result) > 0


def test_generate_with_content_type():
    g = ImageGenerator()
    for ctype in ("buying_guide", "comparison", "social_thread", "tiktok_script"):
        result = g.generate("Test", "tech", "Test", content_type=ctype)
        assert len(result) > 0, f"Failed for {ctype}"


def test_generate_from_prompt():
    g = ImageGenerator()
    result = g.generate_from_prompt(
        "A sleek black TV on a dark wall, ambient lighting"
    )
    assert len(result) > 0


def test_resizer_initializes():
    r = ImageResizer()
    assert r is not None


def test_resize_og():
    g = ImageGenerator()
    r = ImageResizer()
    base = g.generate("Test", "tech", "Test")
    og = r.resize(base, "og")
    assert len(og) > 0


def test_resize_all_platforms():
    g = ImageGenerator()
    r = ImageResizer()
    base = g.generate("Test", "tech", "Test")
    results = r.resize_all(base)
    assert set(results.keys()) == set(PLATFORM_DIMENSIONS.keys())
    for platform, data in results.items():
        assert len(data) > 0, f"Empty result for {platform}"


def test_resize_tiktok():
    g = ImageGenerator()
    r = ImageResizer()
    base = g.generate("Test", "tech", "Test")
    tiktok = r.resize(base, "tiktok")
    assert len(tiktok) > 0


def test_resize_instagram():
    g = ImageGenerator()
    r = ImageResizer()
    base = g.generate("Test", "tech", "Test")
    insta = r.resize(base, "instagram")
    assert len(insta) > 0


def test_unknown_platform_returns_original():
    g = ImageGenerator()
    r = ImageResizer()
    base = g.generate("Test", "tech", "Test")
    result = r.resize(base, "unknown_platform")
    assert result == base


def test_generate_post_image_convenience():
    from abvorn.images import generate_post_image
    result = generate_post_image("Test Product", "tech", "Best Test 2026")
    assert len(result) > 0


def test_resizer_cover_fit_maintains_aspect():
    from PIL import Image
    from io import BytesIO
    g = ImageGenerator()
    r = ImageResizer()
    base = g.generate("Test", "tech", "Test")
    for platform, dims in PLATFORM_DIMENSIONS.items():
        resized_bytes = r.resize(base, platform)
        resized = Image.open(BytesIO(resized_bytes))
        assert resized.size == dims, f"{platform}: expected {dims}, got {resized.size}"


def test_all_platform_dimensions_defined():
    expected = {"og", "blog", "x", "linkedin", "instagram", "tiktok",
                "pinterest", "facebook", "email"}
    assert set(PLATFORM_DIMENSIONS.keys()) == expected


def test_dimensions_are_positive():
    for platform, (w, h) in PLATFORM_DIMENSIONS.items():
        assert w > 0 and h > 0, f"{platform} has invalid dimensions: {w}x{h}"


# === PromptWriter Tests ===

def test_prompt_writer_initializes():
    pw = PromptWriter()
    assert pw is not None


def test_prompt_writer_returns_string():
    pw = PromptWriter()
    prompt = pw.write_prompt("Samsung TV", "tv", "Best TV 2026")
    assert isinstance(prompt, str)
    assert len(prompt) > 50


def test_prompt_writer_includes_style():
    pw = PromptWriter()
    prompt = pw.write_prompt("MacBook Air", "laptop", "Best Laptop 2026")
    assert "Abvorn" in prompt or "editorial" in prompt or "dark" in prompt


def test_prompt_writer_content_types():
    pw = PromptWriter()
    for ctype in ("buying_guide", "comparison", "social_thread", "tiktok_script"):
        prompt = pw.write_prompt("Test Product", "tech", "Test", content_type=ctype)
        assert len(prompt) > 50, f"Empty prompt for {ctype}"
        assert ctype in PROMPT_TEMPLATES


def test_prompt_writer_with_features():
    pw = PromptWriter()
    prompt = pw.write_prompt("Monitor", "tech", "Best Monitor",
                              features=["4K resolution", "144Hz", "IPS panel"])
    assert len(prompt) > 50


def test_prompt_writer_all_types():
    pw = PromptWriter()
    result = pw.write_prompts_for_all_types("TV", "tech", "Best TV")
    assert set(result.keys()) == set(PROMPT_TEMPLATES.keys())
    for prompt in result.values():
        assert len(prompt) > 50


def test_style_guide_defined():
    assert isinstance(STYLE_GUIDE, str)
    assert "Abvorn" in STYLE_GUIDE


def test_propmt_templates_defined():
    for ctype in ("buying_guide", "comparison", "social_thread", "tiktok_script"):
        assert ctype in PROMPT_TEMPLATES
        assert "{product}" in PROMPT_TEMPLATES[ctype]