"""neural_memory.py — Abvorn Neural Memory (Graphify).

Self-updating knowledge graph over the codebase, pipeline, data and docs.
Discovers correlations and insights. Graphify is optional: if the CLI is
unavailable the layer degrades gracefully instead of breaking the core.
"""

import subprocess
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class NeuralMemory:
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.graph_dir = self.repo_path / ".graphify"
        self.memory_file = self.repo_path / "data/neural_memory_state.json"
        self.available = True
        self._ensure_directories()
        self._check_graphify()

    def _ensure_directories(self):
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.memory_file.exists():
            self.memory_file.write_text(json.dumps({
                "last_ingestion": None,
                "entities": 0,
                "relationships": 0,
                "insights": [],
                "queries": [],
                "correlations": [],
                "versions": []
            }, indent=2))

    def _check_graphify(self):
        try:
            subprocess.run(["graphify", "--version"], capture_output=True, check=True, timeout=15)
        except FileNotFoundError:
            logger.warning("Graphify CLI not installed (pip install graphifyy && graphify install). "
                           "Neural memory will run in offline mode.")
            self.available = False
        except Exception as e:
            logger.warning("Graphify check failed: %s. Running offline.", e)
            self.available = False

    def _load_state(self) -> dict:
        try:
            return json.loads(self.memory_file.read_text(encoding='utf-8'))
        except Exception:
            return {"last_ingestion": None, "entities": 0, "relationships": 0,
                    "insights": [], "queries": [], "correlations": [], "versions": []}

    def _save_state(self, state: dict):
        self.memory_file.write_text(json.dumps(state, indent=2), encoding='utf-8')

    def ingest(self, path: str = ".", mode: str = "normal") -> dict:
        if not self.available:
            return {"entities": 0, "relationships": 0}
        cmd = ["graphify", str(path), "--mode", mode, "--json"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception as e:
            logger.error("Graphify run failed: %s", e)
            return {"error": str(e)}
        try:
            data = json.loads(result.stdout)
            state = self._load_state()
            state["last_ingestion"] = datetime.now().isoformat()
            state["entities"] = data.get("entities", 0)
            state["relationships"] = data.get("relationships", 0)
            self._save_state(state)
            return data
        except json.JSONDecodeError:
            logger.error("Graphify ingestion failed: %s", result.stderr)
            return {"error": result.stderr}

    def ingest_all(self) -> dict:
        results = {}
        if not self.available:
            logger.info("Graphify offline — skipping ingestion.")
            return results
        results["codebase"] = self.ingest("./abvorn", mode="deep")
        results["pipeline"] = self.ingest("./run_cycle.py", mode="deep")
        results["data"] = self.ingest("./data", mode="normal")
        state_file = Path("cycle_state.json")
        if state_file.exists():
            results["state"] = self.ingest(str(state_file), mode="normal")
        docs = Path("docs")
        if docs.exists():
            results["docs"] = self.ingest(str(docs), mode="normal")
        return results

    def query(self, query: str) -> List[Dict]:
        if not self.available:
            return []
        result = subprocess.run(["graphify", "query", query, "--json"],
                                capture_output=True, text=True, timeout=60)
        try:
            data = json.loads(result.stdout)
            state = self._load_state()
            state["queries"].append({
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "results": len(data)
            })
            self._save_state(state)
            return data
        except json.JSONDecodeError:
            logger.error("Graphify query failed: %s", result.stderr)
            return []

    def get_correlation(self, entity_a: str, entity_b: str) -> Optional[Dict]:
        results = self.query(f"Find relationships between {entity_a} and {entity_b}")
        if results:
            correlation = {
                "entity_a": entity_a,
                "entity_b": entity_b,
                "correlations": results,
                "timestamp": datetime.now().isoformat()
            }
            state = self._load_state()
            state["correlations"].append(correlation)
            self._save_state(state)
            return correlation
        return None

    def discover_insights(self) -> List[Dict]:
        insights = []
        queries = [
            "What factors correlate with high economic surplus?",
            "What code changes affected SEO score?",
            "How does price tracking relate to conversion?",
            "What patterns exist in user click behavior?",
            "What actions have historically improved drive score?",
            "How do different niches perform over time?"
        ]
        for q in queries:
            res = self.query(q)
            if res:
                insights.append({
                    "query": q,
                    "insight": res[:5],
                    "timestamp": datetime.now().isoformat()
                })
        if insights:
            state = self._load_state()
            state["insights"].extend(insights)
            self._save_state(state)
        return insights

    def get_state(self) -> dict:
        return self._load_state()

    def add_version(self, version: str):
        state = self._load_state()
        state["versions"].append({
            "version": version,
            "timestamp": datetime.now().isoformat()
        })
        self._save_state(state)


_instance = None


def get_neural_memory() -> NeuralMemory:
    global _instance
    if _instance is None:
        _instance = NeuralMemory()
    return _instance