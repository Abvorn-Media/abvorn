# abvorn/core/pulse_engine.py
"""
The Pulse Engine — Temporal Influence Graph for Abvorn.

Models how concepts flow through the Colosseum over time using NetworkX.
Nodes = concepts (debate strategy angles, emotional drivers, product names,
puritan violations, verdict labels). Edges = co-occurrence inside a debate.

Edge weights decay with age so influence reflects recent history, not just
volume. Completely optional: every method degrades gracefully to empty
results when there is no debate data or the graph has not been built yet.

Runs on CPU (Oracle ARM friendly); no GPU required.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    _HAS_NETWORKX = True
except Exception:  # pragma: no cover - import guard
    nx = None
    _HAS_NETWORKX = False

try:
    import numpy as _np
    _HAS_NUMPY = True
except Exception:  # pragma: no cover - import guard
    _np = None
    _HAS_NUMPY = False

try:
    from networkx.algorithms.community import louvain_communities
    _HAS_LOUVAIN = True
except Exception:
    _HAS_LOUVAIN = False


class PulseEngine:
    """
    Builds a temporal influence graph from Colosseum debates.

    Nodes = concepts, Edges = co-occurrence + flow. Edge weights decay over
    time so influence tracks what is rising/falling rather than what simply
    happened the most in the past.
    """

    def __init__(self, debates_dir: Path = None, decay_days: int = 30):
        self.debates_dir = Path(debates_dir or "data/debates")
        self.graph = nx.Graph() if _HAS_NETWORKX else None
        self.concept_index: Dict[str, int] = {}
        self.node_counter = 0
        self.last_build: Optional[datetime] = None
        self.decay_days = int(decay_days)
        self.debates_processed = 0
        self._built = False

    # ── concept extraction ──────────────────────────────────────────────

    @staticmethod
    def _extract_concepts(debate: Dict[str, Any]) -> List[str]:
        """Extract a small, high-signal set of concepts from a debate log.

        Matches the real structure written by Colosseum._ingest_debate:
        strategy, puritan_critique, final_verdict, product.
        """
        concepts: List[str] = []

        # Strategy: angle + emotional driver are the creative thesis.
        strategy = debate.get("strategy", {}) or {}
        if isinstance(strategy, dict):
            for key in ("angle", "emotional_driver", "target_audience"):
                val = strategy.get(key)
                if val and isinstance(val, str):
                    concepts.append(val.strip().lower())

        # Puritan critique: violations are named trust/quality failures.
        puritan = debate.get("puritan_critique", {}) or {}
        if isinstance(puritan, dict):
            violations = puritan.get("violations", [])
            if isinstance(violations, list):
                for v in violations:
                    if isinstance(v, str) and v.strip():
                        concepts.append(v.strip().lower())

        # Final verdict hook: the winning narrative line.
        verdict = debate.get("final_verdict", {}) or {}
        if isinstance(verdict, dict):
            hook = verdict.get("hook")
            if hook and isinstance(hook, str):
                concepts.append("hook:" + hook.strip().lower()[:60])
            label = verdict.get("verdict_label")
            if label and isinstance(label, str):
                concepts.append("label:" + label.strip().lower())

        # Product: links debates to the physical subject being reviewed.
        product = debate.get("product")
        if product and isinstance(product, str):
            concepts.append("product:" + product.strip().lower())

        # Dedupe, drop empties, cap per-debate contribution.
        seen = set()
        out = []
        for c in concepts:
            if not c or len(c) < 4:
                continue
            if c in seen:
                continue
            seen.add(c)
            out.append(c)
        return out[:20]

    # ── graph construction ──────────────────────────────────────────────

    @staticmethod
    def _debate_time(path: Path) -> datetime:
        """Best-effort debate timestamp: JSON `timestamp` field > file mtime."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            ts = raw.get("timestamp")
            if ts:
                parsed = datetime.fromisoformat(str(ts))
                if parsed.year > 2000:
                    return parsed
        except Exception:
            pass
        try:
            return datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            return datetime.now()

    def _get_or_create_node(self, concept: str) -> Optional[int]:
        if not _HAS_NETWORKX or self.graph is None:
            return None
        if concept not in self.concept_index:
            node_id = self.node_counter
            self.concept_index[concept] = node_id
            self.graph.add_node(node_id, label=concept)
            self.node_counter += 1
        return self.concept_index[concept]

    def build_from_debates(self, lookback_days: Optional[int] = None) -> Dict[str, Any]:
        """
        Build or refresh the graph from recent debate logs.

        Returns stats; never raises. Empty debate dir -> empty graph.
        """
        lookback = self.decay_days if lookback_days is None else int(lookback_days)
        empty = {"nodes": 0, "edges": 0, "debates_processed": 0, "built": True}

        if not _HAS_NETWORKX:
            logger.warning("Pulse Engine: NetworkX not installed; graph disabled.")
            empty["built"] = False
            return empty

        self.debates_dir.mkdir(parents=True, exist_ok=True)
        debate_files = list(self.debates_dir.glob("*.json"))
        if not debate_files:
            logger.info("Pulse Engine: no debate files found; graph stays empty.")
            self.graph = nx.Graph()
            self.concept_index = {}
            self.node_counter = 0
            self.last_build = datetime.now()
            self.debates_processed = 0
            self._built = True
            return empty

        # Only debates inside the lookback window.
        cutoff = datetime.now() - timedelta(days=lookback)
        recent = []
        for f in debate_files:
            mtime = self._debate_time(f)
            if mtime > cutoff:
                recent.append(f)
        # Newest first for deterministic tie-breaking.
        recent.sort(key=self._debate_time, reverse=True)

        co_occurrence: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for f in recent:
            try:
                debate = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Pulse Engine: failed to parse {f.name}: {e}")
                continue
            concepts = self._extract_concepts(debate)
            for i, c1 in enumerate(concepts):
                for c2 in concepts[i + 1:]:
                    if c1 != c2:
                        co_occurrence[c1][c2] += 1.0

        self.graph = nx.Graph()
        self.concept_index = {}
        self.node_counter = 0

        for c1, edges in co_occurrence.items():
            n1 = self._get_or_create_node(c1)
            if n1 is None:
                continue
            for c2, weight in edges.items():
                n2 = self._get_or_create_node(c2)
                if n2 is None:
                    continue
                if self.graph.has_edge(n1, n2):
                    self.graph[n1][n2]["weight"] += weight
                else:
                    self.graph.add_edge(n1, n2, weight=weight)

        self.last_build = datetime.now()
        self.debates_processed = len(recent)
        self._built = True

        logger.info(
            "Pulse Engine: built graph from %d debates (%d nodes, %d edges)",
            len(recent),
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
        )
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "debates_processed": len(recent),
            "built": True,
        }

    # ── analytics ───────────────────────────────────────────────────────

    @staticmethod
    def _pagerank_numpy(graph, alpha: float = 0.85, max_iter: int = 100,
                        tol: float = 1e-6) -> Dict[int, float]:
        """Pure-numpy PageRank fallback (no scipy required).

        networkx 3.6 dispatches ``nx.pagerank`` to scipy by default, which may
        be absent on slim/ARM installs. This reimplements the classic power
        iteration so influence scoring works anywhere numpy is available.
        """
        n = graph.number_of_nodes()
        if n == 0:
            return {}
        order = list(graph.nodes())
        index = {node: i for i, node in enumerate(order)}
        # Build the (column-stochastic) transition matrix from edge weights.
        out_weight = {node: 0.0 for node in order}
        col = {i: 0.0 for i in range(n)}
        for u, v, data in graph.edges(data=True):
            w = float(data.get("weight", 1.0))
            out_weight[u] += w
            col[index[v]] += w
        A = _np.zeros((n, n))
        for u, v, data in graph.edges(data=True):
            w = float(data.get("weight", 1.0))
            if out_weight[u] > 0:
                A[index[v], index[u]] = w / out_weight[u]
            else:
                A[index[v], index[u]] = 0.0
        # Dangling nodes distribute uniformly.
        for node, i in index.items():
            if out_weight.get(node, 0.0) == 0.0:
                A[:, i] = 1.0 / n
        r = _np.full(n, 1.0 / n)
        for _ in range(max_iter):
            # Dangling columns already distribute uniformly (set in A above),
            # so the power iteration below is stochastic and converges.
            r_new = alpha * (A @ r) + (1.0 - alpha) / n
            err = _np.abs(r_new - r).sum()
            r = r_new
            if err < n * tol:
                break
        return {node: float(r[i]) for node, i in index.items()}

    def _rank(self, graph) -> Dict[int, float]:
        """PageRank over `graph`, preferring networkx, falling back to numpy."""
        try:
            return dict(nx.pagerank(graph, weight="weight"))
        except Exception as nx_err:
            if not _HAS_NUMPY or graph.number_of_nodes() == 0:
                raise nx_err
            logger.debug("Pulse Engine: nx.pagerank failed (%s); using numpy fallback", nx_err)
            return self._pagerank_numpy(graph)

    def get_influential_concepts(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """PageRank: the most central concepts in the current graph."""
        if not self._built or not _HAS_NETWORKX or self.graph is None or self.graph.number_of_nodes() == 0:
            return []
        try:
            pr = self._rank(self.graph)
        except Exception as e:
            logger.error(f"Pulse Engine: PageRank failed: {e}")
            return []
        ranked = sorted(pr.items(), key=lambda x: x[1], reverse=True)
        results = []
        for node_id, score in ranked[:top_n]:
            label = self.graph.nodes[node_id].get("label", str(node_id))
            results.append({"concept": label, "influence_score": round(float(score), 6), "node_id": int(node_id)})
        return results

    def get_bridge_concepts(self) -> List[Dict[str, Any]]:
        """Concepts that connect otherwise-separate clusters.

        Uses betweenness centrality, then labels each result with its
        community so the caller can tell what it is bridging.
        """
        if not self._built or not _HAS_NETWORKX or self.graph is None or self.graph.number_of_nodes() < 3:
            return []
        try:
            betweenness = nx.betweenness_centrality(self.graph, weight="weight")
        except Exception as e:
            logger.error(f"Pulse Engine: betweenness failed: {e}")
            return []

        # Community label per node (best-effort; Louvain may be absent).
        node_to_community: Dict[int, int] = {}
        if _HAS_LOUVAIN:
            try:
                communities = louvain_communities(self.graph, weight="weight")
                for idx, comm in enumerate(communities):
                    for node in comm:
                        node_to_community[int(node)] = idx
            except Exception as e:
                logger.warning(f"Pulse Engine: Louvain failed ({e}); bridges unlabeled.")

        bridges = []
        for node_id, score in betweenness.items():
            if score > 0.01:
                label = self.graph.nodes[node_id].get("label", str(node_id))
                bridges.append({
                    "concept": label,
                    "bridge_score": round(float(score), 6),
                    "community": node_to_community.get(int(node_id), -1),
                })
        bridges.sort(key=lambda x: x["bridge_score"], reverse=True)
        return bridges[:10]

    def get_temporal_shift(self, days: int = 7) -> Dict[str, Any]:
        """
        Compare the graph's influence profile now vs. `days` ago.

        Returns {rising, falling, stable} concept lists. Best-effort: when
        either window has too few debates the lists come back empty.
        """
        if not _HAS_NETWORKX:
            return {"rising": [], "falling": [], "stable": []}
        try:
            now = datetime.now()
            cutoff_old = now - timedelta(days=max(1, int(days) * 2))
            cutoff_recent = now - timedelta(days=int(days))
            files = list(self.debates_dir.glob("*.json")) if self.debates_dir.exists() else []

            old = []
            recent = []
            for f in files:
                mtime = self._debate_time(f)
                if mtime > cutoff_recent:
                    recent.append(f)
                elif mtime > cutoff_old:
                    old.append(f)
            if not recent or not old:
                return {"rising": [], "falling": [], "stable": []}

            def _influence(files_subset: List[Path]) -> Dict[str, float]:
                g = nx.Graph()
                co = defaultdict(lambda: defaultdict(float))
                for f in files_subset:
                    try:
                        debate = json.loads(f.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    concepts = self._extract_concepts(debate)
                    for i, c1 in enumerate(concepts):
                        for c2 in concepts[i + 1:]:
                            if c1 != c2:
                                co[c1][c2] += 1.0
                idx = {}
                cnt = 0
                for c1, edges in co.items():
                    if c1 not in idx:
                        idx[c1] = cnt
                        g.add_node(cnt, label=c1)
                        cnt += 1
                    for c2, w in edges.items():
                        if c2 not in idx:
                            idx[c2] = cnt
                            g.add_node(cnt, label=c2)
                            cnt += 1
                        n1, n2 = idx[c1], idx[c2]
                        if g.has_edge(n1, n2):
                            g[n1][n2]["weight"] += w
                        else:
                            g.add_edge(n1, n2, weight=w)
                if g.number_of_nodes() == 0:
                    return {}
                try:
                    pr = self._rank(g)
                except Exception:
                    return {}
                return {g.nodes[n].get("label", str(n)): float(score) for n, score in pr.items()}

            old_pr = _influence(old)
            recent_pr = _influence(recent)
            if not old_pr or not recent_pr:
                return {"rising": [], "falling": [], "stable": []}

            rising, falling, stable = [], [], []
            for concept, score in recent_pr.items():
                prev = old_pr.get(concept, 0.0)
                if prev == 0.0:
                    delta = score
                else:
                    delta = (score - prev) / max(prev, 1e-9)
                if delta > 0.15:
                    rising.append({"concept": concept, "delta": round(delta, 3)})
                elif delta < -0.15:
                    falling.append({"concept": concept, "delta": round(delta, 3)})
                else:
                    stable.append({"concept": concept, "delta": round(delta, 3)})

            rising.sort(key=lambda x: x["delta"], reverse=True)
            falling.sort(key=lambda x: x["delta"])
            return {
                "rising": rising[:10],
                "falling": falling[:10],
                "stable": stable[:10],
            }
        except Exception as e:
            logger.error(f"Pulse Engine: temporal shift failed: {e}")
            return {"rising": [], "falling": [], "stable": []}

    # ── state ───────────────────────────────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        """Summary used for logging, dashboards, and genome capture."""
        return {
            "nodes": self.graph.number_of_nodes() if self.graph is not None else 0,
            "edges": self.graph.number_of_edges() if self.graph is not None else 0,
            "last_build": self.last_build.isoformat() if self.last_build else None,
            "debates_processed": self.debates_processed,
            "built": self._built,
            "networkx": _HAS_NETWORKX,
            "louvain": _HAS_LOUVAIN,
        }


# Singleton
_pulse: Optional[PulseEngine] = None


def get_pulse_engine() -> PulseEngine:
    global _pulse
    if _pulse is None:
        _pulse = PulseEngine()
    return _pulse
