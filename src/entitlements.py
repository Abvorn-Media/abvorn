#!/usr/bin/env python3
"""
entitlements.py — The Entitlements Framework

Centralized, auditable permission system for AI agent actions.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Entitlement:
    def __init__(
        self,
        name: str,
        description: str,
        allowed_roles: List[str],
        resource: str,
        action: str,
    ):
        self.name = name
        self.description = description
        self.allowed_roles = allowed_roles
        self.resource = resource
        self.action = action


class EntitlementsFramework:
    """
    Centralized, auditable entitlements system.
    """

    def __init__(self, policies_path: str = "data/entitlements"):
        self.policies_path = Path(policies_path)
        self.policies_path.mkdir(parents=True, exist_ok=True)
        self.policies: Dict[str, Entitlement] = {}
        self.user_policies: Dict[str, List[str]] = {
            "system": ["publish", "edit", "delete", "approve", "expand", "pause", "scale",
                        "refine", "optimize", "add_features", "increase_frequency",
                        "reduce_scope", "halt_expansion", "stop_all", "invest", "maintain",
                        "optimize_providers", "increase_frequency", "refine_content"],
            "admin": ["publish", "edit", "delete", "approve", "expand", "pause", "scale",
                       "refine", "optimize", "add_features", "increase_frequency",
                       "reduce_scope", "halt_expansion", "stop_all", "invest", "maintain",
                       "optimize_providers", "increase_frequency", "refine_content"],
        }
        self.audit_log: List[Dict[str, Any]] = []
        self._load_policies()

    def _load_policies(self):
        for f in self.policies_path.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for name, policy_data in data.items():
                    self.policies[name] = Entitlement(
                        name=name,
                        description=policy_data.get("description", ""),
                        allowed_roles=policy_data.get("allowed_roles", []),
                        resource=policy_data.get("resource", ""),
                        action=policy_data.get("action", ""),
                    )
                logger.info(f"Loaded {len(data)} policies from {f.name}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load {f.name}: {e}")

    def register(self, entitlement: Entitlement) -> None:
        self.policies[entitlement.name] = entitlement
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        path = self.policies_path / f"{entitlement.name}_{timestamp}.json"
        path.write_text(
            json.dumps(
                {
                    entitlement.name: {
                        "description": entitlement.description,
                        "allowed_roles": entitlement.allowed_roles,
                        "resource": entitlement.resource,
                        "action": entitlement.action,
                    }
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        logger.info(f"Entitlement registered: {entitlement.name}")

    def grant(self, user: str, permission: str) -> None:
        if user not in self.user_policies:
            self.user_policies[user] = []
        if permission not in self.user_policies[user]:
            self.user_policies[user].append(permission)
        logger.info(f"Permission granted: {user} -> {permission}")
        self._log_change("grant", user, permission)

    def revoke(self, user: str, permission: str) -> None:
        if user in self.user_policies and permission in self.user_policies[user]:
            self.user_policies[user].remove(permission)
        logger.info(f"Permission revoked: {user} -> {permission}")
        self._log_change("revoke", user, permission)

    def check(self, user: str, action: str, resource: Optional[str] = None) -> bool:
        if user in ("system", "admin"):
            self._log_check(user, action, resource, True)
            self._write_audit(user, action, resource, True)
            return True

        user_perms = self.user_policies.get(user, [])
        allowed = action in user_perms
        self._log_check(user, action, resource, allowed)
        self._write_audit(user, action, resource, allowed)
        return allowed

    def audit(self) -> List[Dict[str, Any]]:
        return self.audit_log

    def _log_check(self, user: str, action: str, resource: Optional[str], allowed: bool) -> None:
        self.audit_log.append(
            {
                "type": "check",
                "timestamp": datetime.now().isoformat(),
                "user": user,
                "action": action,
                "resource": resource,
                "allowed": allowed,
            }
        )

    def _log_change(self, change_type: str, user: str, permission: str) -> None:
        self.audit_log.append(
            {
                "type": change_type,
                "timestamp": datetime.now().isoformat(),
                "user": user,
                "permission": permission,
            }
        )

    def _write_audit(self, user: str, action: str, resource: Optional[str], allowed: bool) -> None:
        os.makedirs("data", exist_ok=True)
        with open("data/audit.log", "a") as f:
            f.write(
                f"{datetime.now().isoformat()} | user={user} | action={action} "
                f"| resource={resource or ''} | allowed={allowed}\n"
            )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_policies": len(self.policies),
            "total_users": len(self.user_policies),
            "total_audit_entries": len(self.audit_log),
            "allowed_checks": sum(1 for e in self.audit_log if e.get("allowed")),
            "denied_checks": sum(1 for e in self.audit_log if not e.get("allowed")),
        }


def create_entitlements_framework() -> EntitlementsFramework:
    return EntitlementsFramework()


if __name__ == "__main__":
    entitlements = create_entitlements_framework()
    entitlements.register(
        Entitlement(
            name="publish_content",
            description="Publish generated content",
            allowed_roles=["admin", "editor", "pipeline"],
            resource="content",
            action="publish",
        )
    )
    result = entitlements.check("system", "publish", "content")
    print(f"Permission check result: {result}")
    print(f"Stats: {entitlements.get_stats()}")