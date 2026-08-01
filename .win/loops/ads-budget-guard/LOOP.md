---
name: ads-budget-guard
title: Ads Budget Guard
description: Monitor paid campaigns and enforce CAC, ROAS, and spend safety.
category: ads
required_connectors:
  - ads
  - stripe
  - analytics
default_authority: ask_first
---

# Ads Budget Guard

## Goal

Prevent paid acquisition from burning money.

## When This Runs

Spend, CAC, ROAS, or conversion moves outside guardrails.

The loop may also run when the owner manually starts it from win.sh, the local CLI, Codex, or Claude Code.

## Signals

Ad platform spend, analytics, Stripe revenue, landing page conversion.

The loop should ignore low-confidence or stale signals unless they repeat or affect important customers.

## Diagnosis

Separate tracking issue, creative fatigue, bad audience, landing mismatch, and seasonal noise.

The loop must explicitly separate facts, assumptions, unknowns, and recommended next actions.

## Allowed Actions

Recommend cut, pause, budget cap, or new test.

The loop may also create a decision record, attach artifacts, and request approval when the action exceeds authority.

## Authority

Spend changes require ads authority and hard caps. Draft mode by default.

Default mode is ask-first. Observe-only is allowed for newly installed loops. The loop cannot raise its own authority.

## Executor Instructions

Use the companion `SKILL.md` as the executor workflow. The executor receives a scoped run brief and should not broaden the business objective. Codex, Claude Code, GitHub Actions, or win.sh Cloud may act as executors.

## Verification

CAC/ROAS returns within guardrails or spend is safely paused.

Verification must produce an outcome: success, failed, inconclusive, or no-action-correct.

## Adaptive Scheduling

Run daily for active spend, faster on spend spikes.

Every execution must end with `nextRunAt`, a reason, a confidence level, and the signal required before the next meaningful run.

## Journal

Append one journal entry after each run with signal, diagnosis, action, expected outcome, verification date, actual outcome when known, and learning.

## Memory Update

Campaign, diagnosis, action, spend saved or revenue impact.

Write learnings as reusable loop memory, not generic notes. Failed tactics should be recorded so the loop does not retry them blindly.
