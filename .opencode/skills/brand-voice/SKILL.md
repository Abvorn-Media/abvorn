---
name: brand-voice
description: Build and maintain a consistent brand voice across Abvorn's content. Source-derived from real examples, avoid AI tropes.
---

# Brand Voice

Abvorn produces content for multiple niches — each needs a consistent voice that matches the target audience.

## Voice Profile Schema
- Sentence length: short and direct for busy readers
- Compression vs explanation: compress features, explain benefits
- Tone: honest, specific, authoritative without being salesy
- Claims: backed by numbers, prices, real specs
- Banned: "In today's rapidly evolving landscape", "game-changer", "revolutionary", "cutting-edge"

## Per-Niche Voice
Set via persona in `AbvornState.persona_registry`:
- tone_of_voice: conversational | professional | enthusiastic | authoritative
- pain_points: what frustrates this niche audience
- desires: what they want to achieve

## Downstream Use
- `content-engine` skill for writing
- `brand-voice` is the canonical source of truth — reuse across related tasks in same session