---
name: cost-aware-llm-pipeline
description: Model routing, budget tracking, and cost optimization for Abvorn's ModelRouter. Selects Haiku/Sonnet/Opus by task complexity, tracks cumulative spend, retries transient errors.
---

# Cost-Aware LLM Pipeline

Abvorn's `abvorn/core/models.py` already implements `ModelRouter` — this skill defines when to route to which model and how to track costs.

## Model Tiers (Abvorn)

| Task | Model | When |
|------|-------|------|
| Research / Product search | haiku | Cheap, fast, sufficient for web search |
| Outline generation | sonnet | Needs strategic thinking |
| Full draft writing | sonnet | Complex, long-form |
| Fact-checking | sonnet | Needs accuracy |
| Polish / Schema | sonnet | Needs quality |
| Brain analysis / Retrieval | haiku | Simple keyword matching |

## Cost Tracking

Use `AbvornState.log_model_metric()` to record every API call:
- provider name
- time in ms
- token count

Review with `state.get_model_stats()` for weekly cost audit.

## Retry Logic
- Transient errors (timeout, rate limit): retry with exponential backoff (1s, 2s, 4s)
- Auth/validation errors: fail immediately
- Max 3 retries per call