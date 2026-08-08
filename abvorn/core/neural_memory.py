"""neural_memory.py — Abvorn Neural Memory (Graphify).

Self-updating knowledge graph over the codebase, pipeline, data and docs.
Discovers correlations and insights. Graphify is optional: if the package is
unavailable the layer degrades gracefully instead of breaking the core.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class NeuralMemory:
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.graph_dir = self.repo_path / "graphify-out"
        self.graph_file = self.graph_dir / "graph.json"
        self.memory_file = self.repo_path / "data/neural_memory_state.json"
        self.available = True
        self._ensure_directories()
        self._check_graphify()

    def _ensure_directories(self):
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        if not self.memory_file.exists():
            self.memory_file.write_text(json.dumps({
                "last_ingestion": None,
                "entities": 0,
                "relationships": 0,
                "insights": [],
                "queries": [],
                "correlations": [],
                "versions": []
            }, indent=2), encoding='utf-8')

    def _check_graphify(self):
        try:
            from graphify.extract import extract, collect_files, _get_extractor  # noqa: F401
            from graphify.build import build_merge  # noqa: F401
            from graphify.export import to_json  # noqa: F401
            from graphify.serve import _score_query, _query_terms  # noqa: F401
            self.available = True
        except Exception as e:
            logger.warning("Graphify Python API unavailable (pip install graphifyy): %s. "
                           "Neural memory will run in offline mode.", e)
            self.available = False

    def _load_state(self) -> dict:
        try:
            return json.loads(self.memory_file.read_text(encoding='utf-8'))
        except Exception:
            return {"last_ingestion": None, "entities": 0, "relationships": 0,
                    "insights": [], "queries": [], "correlations": [], "versions": []}

    def _save_state(self, state: dict):
        self.memory_file.write_text(json.dumps(state, indent=2), encoding='utf-8')

    def _load_graph(self):
        """Load graph.json into a NetworkX graph, mirroring graphify.serve._load_graph
        but returning None (instead of sys.exit) on any failure."""
        if not self.graph_file.exists():
            return None
        from networkx.readwrite import json_graph
        try:
            data = json.loads(self.graph_file.read_text(encoding='utf-8'))
            if "links" not in data and "edges" in data:
                data = dict(data, links=data["edges"])
            data = {**data, "directed": True}
            try:
                return json_graph.node_link_graph(data, edges="links")
            except TypeError:
                return json_graph.node_link_graph(data)
        except Exception as e:
            logger.warning("Graphify graph could not be loaded: %s", e)
            return None

    def ingest(self, path: str = ".", mode: str = "normal") -> dict:
        """Extract a file or directory and merge it into the persistent graph.

        Uses graphify's in-process Python API (no CLI spawn). The target's
        nodes/edges are merged incrementally into graphify-out/graph.json;
        re-ingesting a changed file replaces its prior contribution.
        """
        if not self.available:
            return {"entities": 0, "relationships": 0}
        target = Path(path)
        if not target.exists():
            logger.warning("Graphify ingest target not found: %s", target)
            return {"entities": 0, "relationships": 0}
        try:
            from graphify.extract import collect_files, extract, _get_extractor
            from graphify.build import build_merge
            from graphify.export import to_json

            if target.is_dir():
                files = [f for f in collect_files(target) if _get_extractor(f) is not None]
            else:
                files = [target] if _get_extractor(target) is not None else []
            if not files:
                logger.info("Graphify: no extractable files under %s", target)
                return {"entities": 0, "relationships": 0}

            extraction = extract(files, cache_root=self.graph_dir, root=self.repo_path)
            G = build_merge([extraction], graph_path=self.graph_file, root=str(self.repo_path))
            ok = to_json(G, {}, str(self.graph_file))
            if not ok:
                logger.warning("Graphify to_json refused to persist (shrink guard?)")
            entities = G.number_of_nodes()
            relationships = G.number_of_edges()
            state = self._load_state()
            state["last_ingestion"] = datetime.now().isoformat()
            state["entities"] = entities
            state["relationships"] = relationships
            self._save_state(state)
            return {"entities": entities, "relationships": relationships}
        except Exception as e:
            logger.error("Graphify ingestion failed: %s", e)
            return {"error": str(e)}

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
        """Query the knowledge graph and return structured, ranked results."""
        if not self.available:
            return []
        G = self._load_graph()
        if G is None or G.number_of_nodes() == 0:
            return []
        try:
            from graphify.serve import _score_query, _query_terms

            terms = _query_terms(query)
            if not terms:
                return []
            qs = _score_query(G, terms, collect_per_term_seeds=True)
            scored = qs.ranked[:10]
            if not scored:
                return []
            top = scored[0][0]
            results = []
            for score, nid in scored:
                d = G.nodes[nid]
                results.append({
                    "source": d.get("source_file", ""),
                    "insight": d.get("label", nid),
                    "text": d.get("label", nid),
                    "confidence": (float(score) / top) if top > 0 else 0.0,
                    "location": d.get("source_location", ""),
                    "community": d.get("community", 0),
                    "type": d.get("type", "node"),
                })
            state = self._load_state()
            state["queries"].append({
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "results": len(results)
            })
            self._save_state(state)
            return results
        except Exception as e:
            logger.error("Graphify query failed: %s", e)
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
