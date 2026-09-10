---
name: content-engine
description: Create platform-native content for Abvorn's pipeline — buying guides, product reviews, comparison articles, and social repurposing. Source-first, voice-consistent, platform-adapted.
---

# Content Engine

Abvorn's content pipeline (`abvorn/content/pipeline.py`) generates buying guides. This skill defines the voice, structure, and platform adaptation rules.

## Source-First Workflow
1. Brain context → extract copywriting principles, psychology triggers, SEO tactics
2. Research phase → find real products, real prices, real features
3. Outline → strategic angle selection based on persona
4. Draft → PAS framework (Problem-Agitate-Solution) per product
5. Fact-check → verify claims against research
6. Polish → emotional arc, conversion optimization

## Voice Rules
- Lead with the reader's problem, not the product
- Be specific — real numbers, real scenarios, real prices
- Connect every feature back to a benefit for THIS reader
- Address objections head-on before the reader raises them
- No generic filler: "In today's world", "game-changer", "cutting-edge"

## Platform Adaptation
- Blog post: Full buying guide with schema markup, FAQs, comparison tables
- X/Twitter: Strongest claim first, 1-3 posts per article
- LinkedIn: Expanded enough for non-niche readers, remove corporate cadence
- YouTube: Script around visual sequence, show result early
- Instagram (`viral_script_generator.py` → `social_publisher.py`): Carousel post, visual hook first, max 2200 chars. Feed images render at **1080x1350 (4:5 portrait)** — IG favors it over square; fallback square is 1080x1080, story 1080x1920. Needs **>=2 images** per carousel; frames that fail resize are dropped, never posted unresized. Caption is honest (real claim + real angle, no inflated promise) and includes the guide link + relevant hashtags.
- Telegram (`_telegram_script` → Bot API `sendMessage`): Hook-only first line (curiosity), then body = first ~3 summary paragraphs (HTML stripped), capped at 1900 chars, closed with `Full guide: <url>`. `enable_preview=True` so the page og:image (current logo, `assets/logo.png?v=2`) renders — never strip the preview.

## Quality Gate
Before delivery:
- Every claim backed by research or brain context
- No generic AI transitions
- Affiliate links are contextual, not突兀
- Emotional arc: problem → trust → solution → proof → action
- CTA is earned and clear