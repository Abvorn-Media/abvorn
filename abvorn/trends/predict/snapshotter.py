"""SignalSnapshotter — stores per-scan signal data for velocity tracking."""

import json, logging
from datetime import datetime

logger = logging.getLogger("abvorn.trends.predict.snapshotter")

MAX_SNAPSHOTS = 50


class SignalSnapshotter:
    """Records which products appeared per niche per source per scan."""

    def store(self, niche: str, results: list[dict], state) -> None:
        """Persist a snapshot of products found for this niche."""
        grouped = {}
        for r in results:
            source = r.get("source", "unknown")
            if source not in grouped:
                grouped[source] = set()
            grouped[source].add(r["product_name"])

        for source, products in grouped.items():
            key = f"trend_signal:{niche}:{source}"
            try:
                raw = state.get_meta(key, "[]")
                history = json.loads(raw)
                history.append({
                    "ts": datetime.now().isoformat(),
                    "products": sorted(products),
                    "count": len(products),
                })
                if len(history) > MAX_SNAPSHOTS:
                    history = history[-MAX_SNAPSHOTS:]
                state.set_meta(key, json.dumps(history))
            except Exception as e:
                logger.debug(f"Snapshot store failed for {key}: {e}")