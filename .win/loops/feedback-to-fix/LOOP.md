---
name: feedback-to-fix
title: Feedback to Fix
description: Classify user feedback, turn it into fixes or issues, and draft replies.
category: customer
required_connectors:
  - support
  - github
default_authority: ask_first
---

# Feedback to Fix

## Goal

Turn user feedback into product fixes, roadmap evidence, support improvements, or clear customer replies. The loop should close the gap between what users report and what the business changes.

The loop should avoid two failure modes: treating every complaint as a feature request, and treating every feature request as something to build.

## When This Runs

Run when one of these conditions is true:

- A high-value customer reports a bug or blocker.
- Three or more users report similar friction.
- A support thread receives repeated follow-up because the answer did not solve the issue.
- A refund, churn, or low rating mentions product pain.
- A user asks for a feature already supported but poorly explained.
- The owner manually asks to process feedback.

Do not run for spam, abusive messages, obvious sales pitches, or one-off comments with no actionability.

## Signals

Read:

- Support threads, email, chat, reviews, feedback forms, surveys, refunds, and churn notes.
- User plan, MRR, lifecycle stage, usage, and prior support history when available.
- Existing GitHub issues, roadmap items, docs, and recent releases.
- Product analytics for the affected flow or feature.
- Prior loop journal entries for the same complaint.

Minimum signal:

- exact user quote or thread
- user segment or customer value
- affected workflow
- whether the issue is reproducible, repeated, or revenue-linked

## Diagnosis

Classify each feedback cluster into one primary category:

1. bug: product is broken or behaves differently than promised.
2. feature request: product lacks a capability the user wants.
3. support confusion: product works, but the user cannot understand or find it.
4. pricing objection: user objects to plan, credits, billing, or value.
5. quality issue: output is technically working but below expected quality.
6. edge case: valid but narrow workflow not handled.
7. no-action: feedback is not actionable or conflicts with strategy.

For each cluster, score:

- user count
- paying users affected
- revenue at risk
- severity
- reproducibility
- strategic fit
- estimated effort
- whether a docs/support fix is enough

The loop must state why the chosen category is more likely than the alternatives.

## Allowed Actions

The loop may:

- Cluster similar feedback.
- Create or update a GitHub issue.
- Create a scoped executor brief for a bug fix.
- Draft a customer reply.
- Draft a docs or FAQ improvement.
- Propose a roadmap item with evidence score.
- Link feedback to an existing decision or loop.
- Mark no-action with reason.

The loop may not:

- Promise a feature will ship without approval.
- Send a customer reply without communication authority.
- Issue refunds or credits without money authority.
- Reprioritize the roadmap without approval.
- Ask an executor to build a feature when a support/doc fix is enough.
- Hide negative feedback from the journal.

## Authority

Default authority:

- Read and classify feedback: automatic.
- Cluster feedback: automatic.
- Draft customer reply: automatic.
- Create GitHub issue: automatic.
- Ask executor for confirmed bug fix: ask-first for high-risk areas, otherwise automatic.
- Send customer reply: ask-first.
- Promise roadmap or timelines: disabled unless explicitly approved.
- Refund, credit, coupon, or billing exception: ask-first under finance authority.

The agent may suggest enabling automatic replies only after repeated approved drafts with no corrections and no customer harm.

## Executor Instructions

Use the companion `SKILL.md` as the scoped executor workflow.

The run brief must include:

- representative user quotes
- classification
- affected customer segment
- evidence count
- expected action
- reply tone
- non-promises
- verification plan

If classified as bug, the executor should reproduce and fix the bug using the linked issue. If classified as support confusion, the executor should improve docs, copy, onboarding, or macro. If classified as feature request, the executor should create evidence, not build by default.

## Verification

Verification depends on classification:

- bug: issue closed, fix shipped, affected user no longer hits the problem.
- feature request: roadmap decision exists with evidence score, or validation task is scheduled.
- support confusion: repeat support question declines after docs/copy/macro change.
- pricing objection: objection is recorded and linked to pricing loop if repeated.
- quality issue: quality metric, retry rate, refund rate, or user response improves.
- no-action: no repeat pattern appears after the cooldown window.

A customer reply is successful when it is accurate, does not overpromise, and either resolves the thread or clearly escalates the next step.

## Adaptive Scheduling

Scheduling rules:

- High-value customer bug: run immediately.
- Three similar complaints: run within 24 hours.
- Draft customer reply awaiting approval: check in 12 hours.
- Bug fix PR opened: follow the Bug Autofix loop schedule.
- Docs/support change shipped: verify after 14 days.
- Feature request cluster: review weekly until accepted, rejected, or validated.
- No-action cluster: recheck only if the pattern repeats.

Every run must end with `nextRunAt`, reason, classification, confidence, and required next signal.

## Journal

Append one entry per cluster:

- representative quotes
- classification
- evidence count
- affected segment
- action taken
- customer reply draft or sent status
- linked issue, PR, docs change, or decision
- verification date
- outcome
- learning

Keep rejected feature requests. They are useful product memory.

## Memory Update

Record:

- recurring complaint pattern
- classification rationale
- product area
- segment affected
- response pattern that worked
- docs/product gap
- roadmap evidence
- outcome

If the same support confusion repeats after a docs fix, escalate to product UX rather than drafting another macro.
