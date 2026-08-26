# Debug Report — 2026-08-26

## Symptom
14 tests failing across `tests/api_test.py` (2) and `tests/cta_test.py` (12).

## Root Causes

### Issue 1: CTA tests (12 failures)
**`AbvornState` missing `log_cta_event()` method.**

`CTATracker` (created in commit `4d50f44`) called `self.state.log_cta_event()` in 3 places, but `AbvornState` never implemented this method. Forward-reference gap — consumer created before provider. Commit `f7007d5` ("missing state methods") added read-side methods (`get_cta_stats`, `get_cta_summary`) but missed the write-side `log_cta_event`.

**Secondary:** `get_cta_stats()` had no `niche`/`post_id` filter params, causing `TypeError` in callers (`analyzer.py`, `optimizer.py`, tests).

**Tertiary:** `get_cta_stats()` returned unaggregated rows — each CTA event was a separate row, not grouped by `cta_id`. Tests expected aggregation.

### Issue 2: API tests (2 failures)
**Pre-existing `crm.db` lacked `tracking_consent` column.**

Commit `8d48bb1` added `tracking_consent` to the `CREATE TABLE` schema and `INSERT` statement, but SQLite's `CREATE TABLE IF NOT EXISTS` is a no-op against existing tables. No `ALTER TABLE` migration was added. The pre-existing database file had the old schema.

**Secondary:** `AbvornState.add_subscriber()` accepted `tracking_consent` param but silently ignored it (not in INSERT).

## Fix

### Files changed:
- `abvorn/core/state.py`:
  - Added `log_cta_event()` method (enqueue with `stage='cta_tracked'`)
  - Updated `get_cta_stats()` to accept `niche`/`post_id` filters, add `cta_location` to SELECT, use `GROUP BY` for aggregation, fix column indices
  - Added `tracking_consent` column to `subscribers` schema
  - Added `ALTER TABLE` migration for pre-existing databases
  - Fixed `add_subscriber()` to include `tracking_consent` in INSERT
  - Updated `get_subscribers_for_niche()` keys to include `tracking_consent`
- `abvorn/cta/tracker.py`:
  - Fixed `get_stats()` call: removed `niche=niche` arg from `get_cta_summary()` (method takes no args)
- `abvorn/crm/subscriber.py`:
  - Added `ALTER TABLE` migration for `tracking_consent` column

## Evidence
- Before: 14 failures (2 API + 12 CTA)
- After: 0 failures, 80/80 tests pass
- No regressions in entitlements, reflection, n8n bridge, encoding guard, pipeline, state, health tests

## Related
- Pattern: **Forward-reference gap** — CTATracker written against an API contract that was never implemented
- Pattern: **Schema drift** — `CREATE TABLE IF NOT EXISTS` doesn't add new columns to existing tables
- Architectural note: CTA events stored in `queue` table with `stage='cta_tracked'` and JSON payload, not a dedicated `cta_events` table

## Status: DONE
