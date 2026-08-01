---
name: win-feedback-to-fix
description: Scoped loop execution skill for Feedback to Fix. Use when win.sh or win-loops gives a user feedback cluster run brief.
---

<!-- Installed by win-loops for codex. This is a scoped loop execution skill. -->

# Feedback to Fix Executor

This is a scoped loop execution skill. Convert the supplied feedback into the smallest useful action: classification, issue, bug fix, docs improvement, support reply, or no-op.

## Inputs

- Run brief from `.win/runs/<run-id>.md` or win.sh Cloud.
- Loop contract from `.win/loops/feedback-to-fix/LOOP.md`.
- User quotes, support thread links, customer segment, usage data, related issues, and prior journal entries.

## Workflow

1. Read the run brief and loop contract.
2. Restate the representative user pain and affected segment.
3. Classify the cluster: bug, feature request, support confusion, pricing objection, quality issue, edge case, or no-action.
4. State why the selected classification beats the alternatives.
5. If bug: create/reuse an issue and, if authorized, produce a scoped fix brief or patch.
6. If support confusion: draft docs, macro, copy, onboarding, or FAQ improvement.
7. If feature request: produce evidence score and roadmap recommendation. Do not build by default.
8. Draft a customer reply when useful, with no promises unless authorized.
9. Return artifacts and verification plan.

## Output

Return:

- Classification
- Evidence count and affected segment
- Recommended action
- Issue, PR, doc draft, or decision link
- Customer reply draft when applicable
- Explicit non-promises
- Verification recommendation

## Constraints

- Do not send customer replies without communication authority.
- Do not promise roadmap dates.
- Do not issue refunds, credits, or coupons without money authority.
- Do not build a feature when a docs/support fix is enough.
- Preserve negative feedback in the journal.
