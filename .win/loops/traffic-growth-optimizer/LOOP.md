---
name: traffic-growth-optimizer
title: Traffic Growth Optimizer
description: Diagnose traffic changes and choose the next highest-leverage channel action.
category: growth
required_connectors:
  - analytics
  - gsc
default_authority: ask_first
---

# Traffic Growth Optimizer

## Goal

Grow qualified traffic without chasing vanity metrics.

## When This Runs

Traffic changes materially or a channel underperforms baseline.

The loop may also run when the owner manually starts it from win.sh, the local CLI, Codex, or Claude Code.

## Signals

Analytics channels, GSC, campaigns, referrals, landing pages, conversion by source.

The loop should ignore low-confidence or stale signals unless they repeat or affect important customers.

## Diagnosis

Separate volume, quality, conversion, attribution, and seasonality effects.

The loop must explicitly separate facts, assumptions, unknowns, and recommended next actions.

## Allowed Actions

Recommend channel action, create content brief, adjust internal links, or flag no-op.

The loop may also create a decision record, attach artifacts, and request approval when the action exceeds authority.

## Authority

Recommendations are automatic. Publishing/spend actions require loop-specific authority.

Default mode is ask-first. Observe-only is allowed for newly installed loops. The loop cannot raise its own authority.

## Executor Instructions

Use the companion `SKILL.md` as the executor workflow. The executor receives a scoped run brief and should not broaden the business objective. Codex, Claude Code, GitHub Actions, or win.sh Cloud may act as executors.

## Verification

Traffic quality improves: qualified visits, activation, or paid conversion by channel.

Verification must produce an outcome: success, failed, inconclusive, or no-action-correct.

## Adaptive Scheduling

Run when data changes enough, not on a fixed cadence.

Every execution must end with `nextRunAt`, a reason, a confidence level, and the signal required before the next meaningful run.

## Journal

Append one journal entry after each run with signal, diagnosis, action, expected outcome, verification date, actual outcome when known, and learning.

## Memory Update

Channel diagnosis, action, metric target, outcome.

Write learnings as reusable loop memory, not generic notes. Failed tactics should be recorded so the loop does not retry them blindly.
