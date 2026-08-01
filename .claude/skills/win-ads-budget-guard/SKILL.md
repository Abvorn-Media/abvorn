---
name: win-ads-budget-guard
description: Scoped loop execution skill for Ads Budget Guard. Use when win.sh or win-loops gives a run brief for this loop.
---

<!-- Installed by win-loops for codex. This is a scoped loop execution skill. -->

# Ads Budget Guard Executor

This is a scoped loop execution skill. Execute the run brief; do not redefine the business objective.

## Inputs

- The run brief from `.win/runs/<run-id>.md` or win.sh Cloud.
- The loop contract from `.win/loops/ads-budget-guard/LOOP.md`.
- Any linked artifacts, logs, screenshots, metrics, issues, or customer messages.

## Workflow

1. Read the run brief and loop contract.
2. Restate the signal and target outcome in one short paragraph.
3. Gather only the context needed for this run.
4. Diagnose using the loop contract's Diagnosis section.
5. Take the smallest allowed action within authority.
6. Run relevant checks or explain why no check is available.
7. Report artifacts, risks, expected outcome, and recommended next check.

## Output

Return:

- Summary
- Action taken or proposed
- Artifact links
- Checks run
- Remaining risks
- Verification recommendation

## Constraints

- Do not exceed the loop authority.
- Do not spend money, publish, email customers, merge, deploy, or change billing unless the run brief explicitly authorizes it.
- Prefer no-op or escalation when evidence is weak.
