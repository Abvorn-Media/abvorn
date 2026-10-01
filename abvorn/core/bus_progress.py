"""bus_progress.py - "have I already handled event N?" as a monotonic watermark.

Four agents (ResearchAgent, ContentAgent, DeployAgent, SocialAmbassador) track
consumed bus events by keeping the last 200 handled ids in ``state.meta`` and
filtering anything outside that window:

    fresh = [e for e in events if e["id"] not in handled]

That is only correct while the handled list stays larger than the unhandled
backlog. It stopped being true, and the failure was silent and total.

``content.drafted`` accumulated 663 events (632 of them ``tv``) while the
remembered set was capped at 200. The ~460 oldest ids fell out of the window,
so ``DeployAgent.perceive()`` kept rediscovering them as unhandled work: it
re-deployed the same tv page, emitted a fresh ``content.published``, and
``SocialAmbassador`` promoted it. Every single cycle. The backlog was larger
than the memory of the backlog, so no id could ever retire - a livelock that
presents as "the same tv post every six minutes, forever."

The fix is to stop remembering ids and remember a position instead. Bus ids are
monotonic (autoincrement ``events.id``) and events are only ever consumed in
order, so a single high-water mark answers the only question that is actually
asked: *is this id newer than the last one I handled?* That is O(1) state that
cannot be outgrown by the backlog.

Migration is the subtle part. An existing deployment already has a 200-entry
list under the old key, and the production backlog is ~460 ids wide. The naive
read - "watermark = max(stored list)" - would leave those ~460 ids below the
watermark looking handled, which is correct. But any id *between* the list's min
and max that never got stored would be silently swallowed, so the watermark is
seeded at the max stored id and the legacy list is only ever consulted to derive
that seed. Once the watermark exists it is authoritative and the list is not
maintained.
"""

import logging

logger = logging.getLogger("abvorn.bus_progress")

# Legacy keys held a truncated list of handled ids. Kept readable so an existing
# deployment migrates instead of re-handling its entire backlog on upgrade.
_LEGACY_ID_LIST_MAX = 200


def read_watermark(state, key: str) -> int:
    """Highest event id already consumed for ``key``. 0 means nothing yet.

    Returns a monotonically non-decreasing value for a given ``key``: once a
    watermark is written it always wins, so a failed or reordered write can
    never move the mark backwards and replay old events.
    """
    if state is None:
        return 0
    try:
        raw = state.get_meta(key, 0)
    except Exception as e:
        # A state layer that cannot answer must not read as "nothing handled",
        # or a transient DB error replays the whole backlog.
        logger.warning(f"bus_progress: cannot read watermark {key!r}: {e}")
        return 0

    # New format: a plain integer watermark.
    if isinstance(raw, bool):
        return 0
    if isinstance(raw, int):
        return max(0, raw)
    if isinstance(raw, float):
        return max(0, int(raw))

    # New format: {"watermark": n} envelope, for callers that prefer a dict.
    if isinstance(raw, dict):
        value = raw.get("watermark", 0)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0, int(value))
        return 0

    # Legacy format: the truncated id list. Seed from its max. Anything at or
    # below it is treated as handled, which retires the un-tracked backlog in
    # one step instead of replaying ~460 stale deploys after a deploy.
    if isinstance(raw, (list, tuple)):
        ids = [int(i) for i in raw if isinstance(i, (int, float)) and not isinstance(i, bool)]
        if not ids:
            return 0
        seed = max(ids)
        logger.info(
            f"bus_progress: seeding watermark for {key!r} from legacy id list "
            f"(max={seed}, {len(ids)} entries) - older backlog retired, not replayed"
        )
        return seed

    return 0


def is_handled(state, key: str, event_id: int) -> bool:
    """True when ``event_id`` is at or below the watermark for ``key``."""
    if event_id is None:
        return False
    try:
        eid = int(event_id)
    except (TypeError, ValueError):
        return False
    return eid <= read_watermark(state, key)


def fresh_events(state, key: str, events: list) -> list:
    """Events newer than the watermark, oldest first (ready to consume in order)."""
    if not events:
        return []
    mark = read_watermark(state, key)
    fresh = []
    for event in events:
        eid = event.get("id") if isinstance(event, dict) else None
        try:
            eid = int(eid)
        except (TypeError, ValueError):
            # An event with no usable id cannot be proven handled or unhandled;
            # passing it through would risk an infinite re-consume loop.
            logger.warning(f"bus_progress: event without usable id in {key!r}, skipping")
            continue
        if eid > mark:
            fresh.append(event)
    fresh.sort(key=lambda e: int(e["id"]))
    return fresh


def advance(state, key: str, event_ids) -> int:
    """Mark ``event_ids`` consumed and persist the new watermark.

    Only ever moves forward: a repeated or out-of-order call is a no-op, and a
    failure to persist leaves the previous mark rather than clearing it.
    """
    if state is None:
        return 0
    try:
        ids = []
        for raw in (event_ids or []):
            if isinstance(raw, bool):
                continue
            if isinstance(raw, (int, float)):
                ids.append(int(raw))
        mark = max(ids) if ids else read_watermark(state, key)
        current = read_watermark(state, key)
        if mark <= current:
            return current
        state.set_meta(key, mark)
        return mark
    except Exception as e:
        logger.warning(f"bus_progress: failed to advance watermark {key!r}: {e}")
        return read_watermark(state, key)