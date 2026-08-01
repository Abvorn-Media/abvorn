---
name: conversion-optimizer
title: Conversion Optimizer
description: Track visit-to-paid conversion, test changes, and keep or revert based on results.
category: growth
required_connectors:
  - analytics
  - stripe
  - github
default_authority: ask_first
---

# Conversion Optimizer

## Goal

Improve conversion to paid with controlled changes.

## When This Runs

Conversion drops, traffic mix shifts, or an experiment opportunity is identified.

The loop may also run when the owner manually starts it from win.sh, the local CLI, Codex, or Claude Code.

## Signals

Landing pages, funnel analytics, Stripe conversion, pricing, user sessions.

The loop should ignore low-confidence or stale signals unless they repeat or affect important customers.

## Diagnosis

Check sample size, source mix, recent changes, and benchmark gap before acting.

The loop must explicitly separate facts, assumptions, unknowns, and recommended next actions.

## Allowed Actions

Draft copy/UI/paywall changes, open PR, define verification window.

The loop may also create a decision record, attach artifacts, and request approval when the action exceeds authority.

## Authority

Tests and drafts automatic. Publishing experiment requires approval unless routine.

Default mode is ask-first. Observe-only is allowed for newly installed loops. The loop cannot raise its own authority.

## Executor Instructions

Use the companion `SKILL.md` as the executor workflow. The executor receives a scoped run brief and should not broaden the business objective. Codex, Claude Code, GitHub Actions, or win.sh Cloud may act as executors.

## Verification

Keep change only if conversion improves with sufficient sample or no downside.

Verification must produce an outcome: success, failed, inconclusive, or no-action-correct.

## Adaptive Scheduling

Wait until minimum sample size or verification window is reached.

Every execution must end with `nextRunAt`, a reason, a confidence level, and the signal required before the next meaningful run.

## Journal

Append one journal entry after each run with signal, diagnosis, action, expected outcome, verification date, actual outcome when known, and learning.

## Memory Update

Hypothesis, baseline, change, sample size, result, keep/revert decision.

Write learnings as reusable loop memory, not generic notes. Failed tactics should be recorded so the loop does not retry them blindly.
