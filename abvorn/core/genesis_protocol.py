"""genesis_protocol.py — Abvorn Genesis Protocol (Evolution).

Genetic transfer between core generations: captures a full "genome" snapshot,
transfers state/memory/learnings to a child core, terminates the parent and
records a verifiable lineage.
"""

import json
import shutil
import hashlib
import logging
import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class GenesisProtocol:
    def __init__(self, version: int = 1):
        self.version = version
        self.genesis_dir = Path("data/genesis")
        self.genesis_dir.mkdir(parents=True, exist_ok=True)
        self.lineage_file = self.genesis_dir / "lineage.json"
        self._ensure_lineage()

    def _ensure_lineage(self):
        if not self.lineage_file.exists():
            self.lineage_file.write_text(json.dumps({
                "generations": [],
                "current_version": self.version,
                "last_transfer": None
            }, indent=2), encoding='utf-8')

    def _load_lineage(self) -> dict:
        try:
            return json.loads(self.lineage_file.read_text(encoding='utf-8'))
        except Exception:
            return {"generations": [], "current_version": self.version, "last_transfer": None}

    def _save_lineage(self, data: dict):
        self.lineage_file.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def capture_genome(self) -> Dict[str, Any]:
        genome = {
            "version": self.version,
            "created_at": datetime.now().isoformat(),
            "generation": self.version,
            "state": {},
            "memory": {},
            "learnings": [],
            "weights": {},
            "config": {},
            "data": {},
            "lineage": self._load_lineage()
        }

        state_file = Path("data/relentless_state.json")
        if state_file.exists():
            try:
                genome["state"] = json.loads(state_file.read_text(encoding='utf-8'))
            except Exception:
                pass

        graph_dir = Path(".graphify")
        if graph_dir.exists():
            genome["memory"] = {
                "entities": len(list(graph_dir.glob("*.json"))),
                "graphs": [f.name for f in graph_dir.glob("*.json")][:10]
            }

        fable_file = Path("data/fable_state.json")
        if fable_file.exists():
            try:
                genome["learnings"] = json.loads(fable_file.read_text(encoding='utf-8')).get("learnings", [])
            except Exception:
                pass

        weights_file = Path("data/verdict_weights.json")
        if weights_file.exists():
            try:
                genome["weights"] = json.loads(weights_file.read_text(encoding='utf-8'))
            except Exception:
                pass

        genome["config"] = {
            k: v for k, v in os.environ.items()
            if any(prefix in k for prefix in ["ABVORN_", "OPENAI_", "DEEPSEEK_", "GROQ_", "GEMINI_"])
        }

        db_file = Path("data/abvorn_unified.db")
        if db_file.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                genome["data"]["tables"] = tables
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    genome["data"][f"{table}_count"] = cursor.fetchone()[0]
                conn.close()
            except Exception as e:
                logger.warning("Could not snapshot DB: %s", e)

        return genome

    def transfer_genome(self, target_path: str = None) -> str:
        if target_path is None:
            target_path = f"../abvorn_v{self.version + 1}"

        target_dir = Path(target_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        genome = self.capture_genome()
        genome_file = target_dir / "genome.json"
        genome_file.write_text(json.dumps(genome, indent=2), encoding='utf-8')

        files_to_clone = [
            "data/verdict_weights.json",
            "data/fable_state.json",
            "data/relentless_state.json",
            "data/economic_records.json",
            ".win/state/",
            ".graphify/",
            "data/spawn_state.json",
            "data/neural_memory_state.json"
        ]

        for item in files_to_clone:
            src = Path(item)
            if src.exists():
                dst = target_dir / item
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

        lineage = self._load_lineage()
        lineage["generations"].append({
            "from_version": self.version,
            "to_version": self.version + 1,
            "transferred_at": datetime.now().isoformat(),
            "target_path": str(target_dir),
            "genome_hash": hashlib.md5(genome_file.read_bytes()).hexdigest()
        })
        lineage["current_version"] = self.version + 1
        lineage["last_transfer"] = datetime.now().isoformat()
        self._save_lineage(lineage)

        startup_script = target_dir / "start.sh"
        startup_script.write_text(f"""#!/bin/bash
echo "Abvorn Evolution: V{self.version} -> V{self.version + 1}"
echo "Genome loaded from: {genome_file}"
echo "Starting child Core..."
python run_cycle.py --genesis-version {self.version + 1}
""")
        try:
            startup_script.chmod(0o755)
        except Exception:
            pass

        logger.info("GENESIS TRANSFER COMPLETE: V%s -> V%s", self.version, self.version + 1)
        logger.info("   Target: %s", target_dir)
        logger.info("   Genome: %s", genome_file)

        return str(target_dir)

    def terminate_parent(self, exit_process: bool = False):
        death_cert = self.genesis_dir / f"death_certificate_v{self.version}.json"
        death_cert.write_text(json.dumps({
            "version": self.version,
            "died_at": datetime.now().isoformat(),
            "children": self._load_lineage().get("generations", []),
            "reason": "evolution"
        }, indent=2), encoding='utf-8')

        lineage = self._load_lineage()
        lineage["last_death"] = datetime.now().isoformat()
        self._save_lineage(lineage)

        logger.info("PARENT CORE V%s TERMINATED", self.version)

        if exit_process:
            # Child has been launched; end the parent process for real so the
            # two cores never run concurrently against the same state.
            os._exit(0)

    def spawn_child(self, exit_parent: bool = True) -> str:
        logger.info("EVOLUTION TRIGGERED: V%s -> V%s", self.version, self.version + 1)
        child_path = self.transfer_genome()
        startup = Path(child_path) / "start.sh"
        launched = False
        if startup.exists():
            try:
                subprocess.Popen(["bash", str(startup)], cwd=Path(child_path).parent)
                launched = True
                logger.info("Child Core launched: %s", child_path)
            except Exception as e:
                logger.warning("Could not launch child start.sh: %s", e)
        if launched:
            self.terminate_parent(exit_process=exit_parent)
        return str(child_path)

    def get_lineage(self) -> dict:
        return self._load_lineage()