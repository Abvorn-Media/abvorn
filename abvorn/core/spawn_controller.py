"""spawn_controller.py — Abvorn Core Spawning (Multi-Core).

Leader-Follower orchestration so multiple Relentless Core instances do not
conflict. A shared state file tracks leadership, followers, heartbeats and
distributed tasks.
"""

import json
import socket
import time
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class SpawnController:
    def __init__(self, state_file: str = "data/spawn_state.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.instance_id = f"{socket.gethostname()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
        self.role = "follower"
        self.leader_id = None
        self.heartbeat_interval = 30
        self.leader_timeout = 60

    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {"leader": None, "followers": [], "last_heartbeat": None}

    def _save_state(self, state: dict):
        self.state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')

    def register(self) -> str:
        state = self._load_state()
        now = datetime.now().isoformat()

        if state.get("leader") and state.get("last_heartbeat"):
            try:
                last_heartbeat = datetime.fromisoformat(state["last_heartbeat"])
            except Exception:
                last_heartbeat = datetime.min
            if (datetime.now() - last_heartbeat).total_seconds() < self.leader_timeout:
                self.role = "follower"
                self.leader_id = state["leader"]
                if self.instance_id not in state["followers"]:
                    state["followers"].append(self.instance_id)
                logger.info("Registered as FOLLOWER (leader: %s)", self.leader_id)
            else:
                self.role = "leader"
                self.leader_id = self.instance_id
                state["leader"] = self.instance_id
                state["followers"] = []
                state["last_heartbeat"] = now
                logger.info("Registered as LEADER (dead leader detected)")
        else:
            self.role = "leader"
            self.leader_id = self.instance_id
            state["leader"] = self.instance_id
            state["followers"] = []
            state["last_heartbeat"] = now
            logger.info("Registered as LEADER (first instance)")

        self._save_state(state)
        return self.role

    def heartbeat(self):
        if self.role == "leader":
            state = self._load_state()
            state["last_heartbeat"] = datetime.now().isoformat()
            self._save_state(state)

    def get_followers(self) -> List[str]:
        state = self._load_state()
        return state.get("followers", [])

    def assign_task(self, task: Dict[str, Any]) -> Optional[str]:
        if self.role != "leader":
            return None
        followers = self.get_followers()
        if not followers:
            return None
        assigned_follower = followers[0]
        task_file = Path(f"data/tasks/{assigned_follower}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text(json.dumps({
            "assigned_to": assigned_follower,
            "task": task,
            "assigned_at": datetime.now().isoformat(),
            "status": "pending"
        }, indent=2), encoding='utf-8')
        return assigned_follower

    def get_my_task(self) -> Optional[Dict]:
        if self.role != "follower":
            return None
        task_dir = Path("data/tasks")
        if not task_dir.exists():
            return None
        task_files = list(task_dir.glob(f"{self.instance_id}_*.json"))
        for tf in sorted(task_files):
            data = json.loads(tf.read_text(encoding='utf-8'))
            if data.get("status") == "pending":
                return data
        return None

    def complete_task(self, task_id: str):
        task_dir = Path("data/tasks")
        if not task_dir.exists():
            return
        for tf in task_dir.glob("*.json"):
            data = json.loads(tf.read_text(encoding='utf-8'))
            if data.get("id") == task_id:
                data["status"] = "completed"
                data["completed_at"] = datetime.now().isoformat()
                tf.write_text(json.dumps(data, indent=2), encoding='utf-8')
                break

    def run_heartbeat_loop(self):
        import threading

        def _heartbeat():
            while True:
                try:
                    self.heartbeat()
                except Exception as e:
                    logger.warning("Heartbeat failed: %s", e)
                time.sleep(self.heartbeat_interval)

        thread = threading.Thread(target=_heartbeat, daemon=True)
        thread.start()

    def get_state(self) -> dict:
        return self._load_state()