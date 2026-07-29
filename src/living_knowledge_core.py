#!/usr/bin/env python3
"""
living_knowledge_core.py — The Abvorn Living Knowledge Core

A self-updating knowledge base that learns from every cycle,
every article, every product review, and every user interaction.
Stores structured knowledge and generates strategic briefs.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


KNOWLEDGE_FILE = Path("data/knowledge_base.json")
CATEGORY_FILE = Path("data/category_knowledge.json")


class LivingKnowledgeCore:
    def __init__(self, library_path: str = None, watch_folder: bool = False):
        self.library_path = library_path
        self.watch_folder = watch_folder
        self.knowledge_base = {}
        self.category_knowledge = defaultdict(list)
        self.cycle_count = 0
        self.insights = []
        self._load()

    def _load(self):
        if KNOWLEDGE_FILE.exists():
            try:
                self.knowledge_base = json.loads(
                    KNOWLEDGE_FILE.read_text(encoding="utf-8")
                )
                logger.info(
                    f"Knowledge Core loaded: {len(self.knowledge_base)} entries"
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Knowledge Core load failed: {e}")
                self.knowledge_base = {}
        if CATEGORY_FILE.exists():
            try:
                self.category_knowledge = json.loads(
                    CATEGORY_FILE.read_text(encoding="utf-8")
                )
                logger.info(
                    f"Category knowledge loaded: {len(self.category_knowledge)} categories"
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Category knowledge load failed: {e}")
                self.category_knowledge = defaultdict(list)

    def _save(self):
        KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        KNOWLEDGE_FILE.write_text(
            json.dumps(self.knowledge_base, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        CATEGORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        CATEGORY_FILE.write_text(
            json.dumps(
                dict(self.category_knowledge), indent=2, ensure_ascii=False
            ),
            encoding="utf-8",
        )
        logger.info("Knowledge Core saved to disk")

    def ingest(self, entry: Dict[str, Any]) -> str:
        entry_id = entry.get("id", f"knowledge_{self.cycle_count}_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        entry["ingested_at"] = datetime.now().isoformat()
        entry["cycle"] = self.cycle_count
        self.knowledge_base[entry_id] = entry

        category = entry.get("category", entry.get("topic_cluster", "general"))
        self.category_knowledge[category].append(entry_id)

        self.cycle_count += 1
        self._save()
        logger.info(f"Knowledge ingested: {entry_id} -> {category}")
        return entry_id

    def ingest_from_verdict(self, product_data: Dict[str, Any], niche: str = "") -> str:
        entry = {
            "type": "verdict",
            "product_name": product_data.get("product_name", "Unknown"),
            "category": niche or product_data.get("category", "general"),
            "overall_score": product_data.get("verdict", {}).get("overall", 0),
            "breakdown": product_data.get("verdict", {}).get("breakdown", {}),
            "price": product_data.get("price", 0),
            "features": product_data.get("features", []),
        }
        return self.ingest(entry)

    def generate_strategy_brief(self, category: str) -> Dict[str, Any]:
        entries = self.category_knowledge.get(category, [])
        if not entries:
            return {"category": category, "insights": [], "trend": "no_data"}

        insights = []
        scores = []
        for entry_id in entries:
            entry = self.knowledge_base.get(entry_id, {})
            score = entry.get("overall_score", 0)
            scores.append(score)

            if score >= 8.0:
                insights.append({
                    "source": entry.get("product_name", "Unknown"),
                    "insight": f"High-performing product in {category} with score {score}",
                    "type": "strength",
                    "score": score,
                })
            elif score >= 5.0:
                insights.append({
                    "source": entry.get("product_name", "Unknown"),
                    "insight": f"Mid-range product in {category} with score {score}",
                    "type": "neutral",
                    "score": score,
                })
            else:
                insights.append({
                    "source": entry.get("product_name", "Unknown"),
                    "insight": f"Low-performing product in {category} with score {score}",
                    "type": "weakness",
                    "score": score,
                })

        avg_score = sum(scores) / len(scores) if scores else 0
        trend = "improving" if len(scores) >= 2 and scores[-1] > scores[0] else "stable"

        return {
            "category": category,
            "insights": insights[:5],
            "average_score": round(avg_score, 2),
            "trend": trend,
            "total_entries": len(entries),
        }

    def record_cycle_result(self, niche: str, result: Dict[str, Any]) -> None:
        entry = {
            "type": "cycle_result",
            "niche": niche,
            "status": result.get("status", "unknown"),
            "products_processed": result.get("products", 0),
            "timestamp": datetime.now().isoformat(),
        }
        self.ingest(entry)

    def get_knowledge_summary(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self.knowledge_base),
            "total_cycles": self.cycle_count,
            "categories": list(self.category_knowledge.keys()),
            "category_counts": {
                cat: len(entries)
                for cat, entries in self.category_knowledge.items()
            },
            "last_updated": datetime.now().isoformat(),
        }


def create_living_knowledge_core(library_path: str = None, watch_folder: bool = False) -> LivingKnowledgeCore:
    return LivingKnowledgeCore(library_path=library_path, watch_folder=watch_folder)


if __name__ == "__main__":
    core = create_living_knowledge_core()

    core.ingest_from_verdict(
        {
            "product_name": "Sony WH-1000XM6",
            "category": "wireless-headphones",
            "price": 299.99,
            "verdict": {"overall": 8.7, "breakdown": {"sound": 9.2, "comfort": 8.8, "battery": 7.5}},
        },
        "wireless-headphones",
    )

    brief = core.generate_strategy_brief("wireless-headphones")
    print(json.dumps(brief, indent=2))

    summary = core.get_knowledge_summary()
    print(json.dumps(summary, indent=2))