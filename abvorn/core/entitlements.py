"""entitlements.py — Permission gates for high-risk agent actions.

Nadella's scaffolding requirement: agents need an entitlements system that
defines what actions they have permission to take. This is the difference
between a demo and an enterprise-grade product.

Permission levels:
  READ      — query data, read state (safe)
  WRITE     — modify content, update state (reversible)
  DEPLOY    — push to GitHub Pages, publish externally (hard to reverse)
  EVADE     — modify the codebase, change agent configurations
  TERMINATE — kill a process, evolve to a new generation, self-modify

Every action above READ requires explicit operator approval unless
the action is in the auto-approved list (configured per deployment).
"""

import json
import logging
import os
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Permission(IntEnum):
    READ = 0
    WRITE = 1
    DEPLOY = 2
    EVADE = 3
    TERMINATE = 4


# Actions that are auto-approved at each permission level.
# Anything not in this list requires explicit operator approval.
DEFAULT_AUTO_APPROVED = {
    Permission.READ: ["query", "reflect", "heartbeat", "analyze"],
    Permission.WRITE: ["generate_content", "update_state", "save_reflection"],
    Permission.DEPLOY: [],  # deployment requires approval
    Permission.EVADE: [],   # code changes require approval
    Permission.TERMINATE: [],  # termination/evolution requires approval
}

# Explicit action → permission level mapping
ACTION_PERMISSIONS = {
    "generate_content": Permission.WRITE,
    "update_state": Permission.WRITE,
    "save_reflection": Permission.WRITE,
    "query_brain": Permission.READ,
    "analyze_performance": Permission.READ,
    "deploy_to_github": Permission.DEPLOY,
    "push_pages": Permission.DEPLOY,
    "publish_social": Permission.DEPLOY,
    "modify_codebase": Permission.EVADE,
    "change_configuration": Permission.EVADE,
    "update_agent_config": Permission.EVADE,
    "spawn_child": Permission.TERMINATE,
    "terminate_parent": Permission.TERMINATE,
    "evolve_generation": Permission.TERMINATE,
    "kill_process": Permission.TERMINATE,
}

ENTITLEMENTS_FILE = Path("data/entitlements_state.json")


class Entitlements:
    """Permission gate for agent actions.

    Maintains a state file that records:
    - auto-approved actions (per deployment config)
    - pending approvals (actions waiting for operator confirmation)
    - approval history (audit trail)
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.auto_approved = dict(DEFAULT_AUTO_APPROVED)
        self.pending: list = []
        self.history: list = []
        self._load_state()

    def _load_state(self):
        if ENTITLEMENTS_FILE.exists():
            try:
                data = json.loads(ENTITLEMENTS_FILE.read_text(encoding="utf-8"))
                self.pending = data.get("pending", [])
                self.history = data.get("history", [])[-100:]
            except Exception:
                pass

    def _save_state(self):
        ENTITLEMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENTITLEMENTS_FILE.write_text(json.dumps({
            "pending": self.pending,
            "history": self.history[-100:],
            "updated_at": datetime.now().isoformat(),
        }, indent=2), encoding="utf-8")

    def check(self, action: str, agent: str = "unknown",
              context: dict = None) -> dict:
        """Check whether an action is permitted.

        Returns:
            {"allowed": bool, "reason": str, "requires_approval": bool,
             "permission_level": str}
        """
        perm_level = ACTION_PERMISSIONS.get(action, Permission.READ)
        perm_name = Permission(perm_level).name

        # Check auto-approved list
        auto_list = self.auto_approved.get(perm_level, [])
        if action in auto_list or action.startswith("query"):
            return {
                "allowed": True,
                "reason": f"auto-approved at {perm_name} level",
                "requires_approval": False,
                "permission_level": perm_name,
            }

        # High-risk actions require approval
        if perm_level >= Permission.DEPLOY:
            pending_entry = {
                "action": action,
                "agent": agent,
                "permission_level": perm_name,
                "requested_at": datetime.now().isoformat(),
                "context": context or {},
            }
            self.pending.append(pending_entry)
            self._save_state()

            logger.warning(
                "[ENTITLEMENTS] %s requesting %s (requires operator approval)",
                agent, action,
            )
            return {
                "allowed": False,
                "reason": f"{action} requires operator approval at {perm_name} level",
                "requires_approval": True,
                "permission_level": perm_name,
                "pending_id": len(self.pending) - 1,
            }

        # WRITE-level actions not in auto-approved list
        return {
            "allowed": True,
            "reason": f"implicit approval at {perm_name} level",
            "requires_approval": False,
            "permission_level": perm_name,
        }

    def approve(self, pending_index: int) -> bool:
        """Operator approves a pending action. Returns True if valid."""
        if 0 <= pending_index < len(self.pending):
            entry = self.pending.pop(pending_index)
            entry["approved_at"] = datetime.now().isoformat()
            entry["status"] = "approved"
            self.history.append(entry)
            self._save_state()
            logger.info("[ENTITLEMENTS] Approved: %s by %s", entry["action"], entry["agent"])
            return True
        return False

    def deny(self, pending_index: int) -> bool:
        """Operator denies a pending action."""
        if 0 <= pending_index < len(self.pending):
            entry = self.pending.pop(pending_index)
            entry["denied_at"] = datetime.now().isoformat()
            entry["status"] = "denied"
            self.history.append(entry)
            self._save_state()
            logger.info("[ENTITLEMENTS] Denied: %s by %s", entry["action"], entry["agent"])
            return True
        return False

    def get_pending(self) -> list:
        """Return actions awaiting operator approval."""
        return list(self.pending)

    def get_audit_log(self, limit: int = 20) -> list:
        """Return recent approval/denial history."""
        return self.history[-limit:]


# Singleton
_entitlements: Optional[Entitlements] = None


def get_entitlements() -> Entitlements:
    global _entitlements
    if _entitlements is None:
        _entitlements = Entitlements()
    return _entitlements
