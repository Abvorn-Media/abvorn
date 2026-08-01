---
name: seo-growth
title: SEO Growth
description: Run a complete organic growth loop across GSC, competitor research, page updates, and delayed verification.
category: seo
required_connectors:
  - gsc
  - github
default_authority: ask_first
---

# SEO Growth

## Goal

Grow qualified organic traffic with measurable search improvements. The loop should find the highest-leverage SEO action, execute or draft it, then verify after search data has had time to move.

The loop optimizes for qualified clicks and business intent. It should not create thin content just to increase page count.

## When This Runs

Run when one of these conditions is true:

- GSC has fresh data and a page/query crosses the minimum evidence threshold.
- A valuable page loses clicks, CTR, or average position for at least 7 days.
- A query sits in positions 4-20 with meaningful impressions.
- A page has high impressions and below-benchmark CTR.
- Competitors gain rankings on commercially relevant terms.
- A new product feature, use case, or customer phrase creates a search opportunity.
- The owner manually starts an SEO growth cycle.

Minimum evidence:

- at least 100 impressions over the comparison window, or
- at least 20 clicks over the comparison window, or
- a commercial query tied to an existing paying customer segment.

## Signals

Read:

- GSC query, page, country, device, clicks, impressions, CTR, and average position.
- Existing page title, meta description, H1, first viewport, internal links, schema, and update date.
- Sitemap, robots, canonical, indexing state, and page status.
- Competitor SERP pages and snippets.
- Prior SEO Growth and Content Refresh journal entries.
- Product positioning, pricing, and conversion data when available.

Ignore:

- tiny impression changes
- seasonal shifts without actionability
- queries unrelated to the product
- pages where a stronger page already owns the intent

## Diagnosis

Choose exactly one primary action type:

1. CTR improvement: title, meta, snippet, FAQ, proof, or SERP promise.
2. Ranking improvement: content depth, examples, intent match, internal links.
3. New page: uncovered intent with enough demand and clear differentiation.
4. Internal linking: relevant source pages can lift a target page.
5. Technical fix: indexing, canonical, schema, sitemap, or performance issue.
6. No-op: evidence is weak, query is irrelevant, or another loop should handle it.

Check cannibalization before creating or changing pages. If two pages compete for the same query, recommend consolidation or clearer intent split.

Diagnosis must include:

- target page or proposed URL
- target query cluster
- baseline clicks, impressions, CTR, and average position
- search intent
- competitor pattern
- chosen action
- why the other action types were rejected

## Allowed Actions

The loop may:

- Create an SEO opportunity brief.
- Edit title, meta, intro, headings, FAQ, examples, schema, and internal links.
- Draft a new page or article.
- Open a PR against a website repo.
- Create a technical SEO issue.
- Request indexing or validation when the connector exists.
- Schedule delayed verification.

The loop may not:

- Publish AI-slop pages.
- Create pages without unique proof, product fit, or search intent.
- Change canonical, noindex, robots, sitemap, or large navigation structures without approval.
- Rewrite brand positioning without approval.
- Delete or redirect pages without approval.

## Authority

Default authority:

- Read GSC and crawl public pages: automatic.
- Create brief: automatic.
- Draft content or PR: automatic.
- Publish existing-page copy edits: ask-first.
- Publish new page: ask-first.
- Technical indexing changes: ask-first.
- Delete, redirect, noindex, canonical changes: ask-first.

The loop can suggest authority upgrade after at least 8 verified SEO changes with positive or neutral outcomes and no quality regressions.

## Executor Instructions

Use the companion `SKILL.md` as the scoped executor workflow.

The run brief must include:

- target page or proposed URL
- query cluster
- baseline metrics
- selected action type
- competitor examples
- required proof or product examples
- verification date

The executor should make the smallest content or code change that matches the action type. It should preserve brand voice, avoid generic filler, and keep claims supportable.

## Verification

SEO verification is delayed.

Default windows:

- Existing-page CTR/title/meta/internal-link changes: verify after 14 days.
- Content depth or major page refresh: verify after 21 days.
- New page: verify indexing after 7 days, then performance after 28 days.
- Technical indexing fix: verify as soon as GSC validation or crawl result updates.

Success:

- clicks increase by at least 10%, or
- CTR improves by at least 15% on the target query cluster, or
- average position improves by at least 2 positions, or
- page becomes indexed and starts receiving impressions, or
- no-op was correct because evidence stayed weak.

Failure:

- traffic drops materially without explanation
- cannibalization appears
- page is not indexed after the expected window
- conversion quality worsens despite click growth

## Adaptive Scheduling

Scheduling rules:

- Fresh GSC data with material opportunity: run within 24 hours.
- After existing-page change: verify in 14 days.
- After major refresh: verify in 21 days.
- After new page publish: index check in 7 days, performance check in 28 days.
- If GSC data volume is below minimum evidence: wait until sample threshold is reached.
- If cannibalization risk is detected: pause and ask before publishing.

Every run must end with `nextRunAt`, reason, confidence, target metric, and verification window.

## Journal

Append one entry per SEO action:

- target page
- query cluster
- baseline metrics
- action type
- exact change
- expected outcome
- verification date
- actual outcome
- decision: keep, revert, expand, or stop

Do not overwrite failed SEO hypotheses. They prevent repeat mistakes.

## Memory Update

Record:

- search intent pattern
- competitor pattern
- page type that worked or failed
- title/meta pattern
- internal-link source pages
- cannibalization notes
- verification result
- query clusters to avoid

If a tactic fails twice for the same site, require stronger evidence before trying it again.
