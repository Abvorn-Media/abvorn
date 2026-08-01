---
name: win-seo-growth
description: Scoped loop execution skill for SEO Growth. Use when win.sh or win-loops gives an SEO opportunity run brief.
---

<!-- Installed by win-loops for codex. This is a scoped loop execution skill. -->

# SEO Growth Executor

This is a scoped loop execution skill. Execute the selected SEO action. Do not invent a new strategy unless the run brief asks for diagnosis only.

## Inputs

- Run brief from `.win/runs/<run-id>.md` or win.sh Cloud.
- Loop contract from `.win/loops/seo-growth/LOOP.md`.
- GSC baseline, target query cluster, page URL, competitor examples, and prior journal entries.

## Workflow

1. Read the run brief and loop contract.
2. Restate target page, query cluster, baseline metrics, and selected action type.
3. Check cannibalization risk before creating or changing pages.
4. Inspect the current page or proposed page angle.
5. Compare competitor SERP pattern without copying.
6. Make the smallest useful edit: title/meta, intro, proof, content depth, internal links, schema, or page draft.
7. Preserve brand voice and support claims with product-specific proof.
8. Avoid filler, generic definitions, and unsupported superlatives.
9. Open a PR or return a draft artifact.
10. Report the verification date and target metrics.

## Output

Return:

- Target page or proposed URL
- Query cluster
- Baseline metrics
- Change summary
- Files changed or draft link
- Cannibalization assessment
- Verification window: 14, 21, or 28 days
- Expected outcome

## Constraints

- Do not publish new pages without approval.
- Do not delete, redirect, noindex, or canonicalize pages without approval.
- Do not create thin pages.
- Do not change brand positioning beyond the scoped SEO action.
- Prefer no-op when evidence is below threshold.
