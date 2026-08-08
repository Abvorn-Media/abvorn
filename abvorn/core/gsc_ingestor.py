"""gsc_ingestor.py - Ingests Google Search Console data into Abvorn's systems.

Updates the unified database summary files, writes top/growth data for the
Neural Memory (Graphify), and records insights to Ab's Evolution Journal.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from abvorn.core.gsc_client import GSCClient
from abvorn.core.unified_database import get_unified_db
from abvorn.core.neural_memory import get_neural_memory

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
SUMMARY_FILE = DATA_DIR / "gsc_latest_summary.json"
INGESTION_LOG = DATA_DIR / "gsc_ingestion_log.jsonl"
JOURNAL_FILE = DATA_DIR / "ab_journal_entries.jsonl"


class GSCIngestor:
    """Ingests Google Search Console data into Abvorn's systems."""

    def __init__(self):
        self.client = GSCClient()
        self.db = get_unified_db()
        self.memory = get_neural_memory()
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def ingest_performance(self, days: int = 7) -> Dict[str, Any]:
        """Ingest performance data for the last N days."""
        logger.info("Ingesting GSC data for last %s days...", days)

        if not self.client.enabled:
            return {"status": "failed", "error": "GSC Client disabled"}

        df = self.client.fetch_performance(days)
        if not df:
            return {"status": "failed", "error": "No data fetched"}

        top_content = self.client.fetch_top_performing(days)
        opportunities = self.client.fetch_growth_opportunities(days)

        self._store_summary(df, days)
        self._ingest_to_graphify(top_content, "top_performing")
        self._ingest_to_graphify(opportunities, "growth_opportunity")

        insights = self._generate_insights(top_content, opportunities)
        self._write_to_journal(insights)
        self._log_ingestion(days, len(df), len(top_content), len(opportunities))

        return {
            "status": "success",
            "rows_processed": len(df),
            "top_content_count": len(top_content),
            "opportunities_count": len(opportunities),
            "insights": insights,
        }

    def _store_summary(self, rows: List[Dict], days: int):
        """Store summary stats in a JSON file for the dashboard."""
        try:
            total_clicks = sum(r.get("clicks", 0) for r in rows)
            total_impressions = sum(r.get("impressions", 0) for r in rows)
            ctrs = [r.get("ctr", 0) for r in rows]
            positions = [r.get("position", 0) for r in rows]
            summary = {
                "total_clicks": int(total_clicks),
                "total_impressions": int(total_impressions),
                "avg_ctr": float(sum(ctrs) / len(ctrs)) if ctrs else 0.0,
                "avg_position": float(sum(positions) / len(positions)) if positions else 0.0,
                "days": days,
                "rows": len(rows),
                "timestamp": datetime.now().isoformat(),
            }
            SUMMARY_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            logger.info("GSC summary stored")
        except Exception as e:
            logger.error("Failed to store summary: %s", e)

    def _ingest_to_graphify(self, data: List[Dict], data_type: str):
        """Ingest GSC data into Graphify for querying."""
        if not data:
            return
        try:
            graph_data = {
                "type": "gsc_insight",
                "subtype": data_type,
                "timestamp": datetime.now().isoformat(),
                "items": data,
            }
            temp_file = DATA_DIR / f"gsc_{data_type}.json"
            temp_file.write_text(json.dumps(graph_data, indent=2), encoding="utf-8")
            self.memory.ingest(str(temp_file), mode="normal")
            logger.info("Ingested %s items as '%s' into Graphify", len(data), data_type)
        except Exception as e:
            logger.error("Failed to ingest to Graphify: %s", e)

    def _generate_insights(self, top_content: List, opportunities: List) -> List[str]:
        """Generate human-readable insights for the Brain and Journal."""
        insights = []

        if top_content:
            top_urls = [item["url"][:50] for item in top_content[:3]]
            insights.append(f"Top performing content: {', '.join(top_urls)}")
            insights.append(
                f"Highest CTR: {top_content[0].get('ctr', 0):.2%} for {top_content[0].get('url', '')[:30]}"
            )

        if opportunities:
            insights.append(
                f"Found {len(opportunities)} growth opportunities with high impressions but low CTR"
            )
            top_opp = opportunities[0]
            insights.append(
                f"Biggest opportunity: {top_opp.get('page', '')[:30]} "
                f"(CTR: {top_opp.get('ctr', 0):.2%}, Impressions: {top_opp.get('impressions', 0)})"
            )

        return insights

    def _write_to_journal(self, insights: List[str]):
        """Write GSC insights to Ab's Evolution Journal."""
        if not insights:
            return
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": "Google Search Console",
            "insights": insights,
        }
        try:
            with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error("Failed to write journal entry: %s", e)

    def _log_ingestion(self, days: int, rows: int, top_count: int, opp_count: int):
        """Log the ingestion for tracking."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "days": days,
            "rows_fetched": rows,
            "top_content_count": top_count,
            "opportunities_count": opp_count,
        }
        try:
            with open(INGESTION_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            logger.info("GSC ingestion logged: %s rows, %s top, %s opps", rows, top_count, opp_count)
        except Exception as e:
            logger.error("Failed to log ingestion: %s", e)
