"""n8n_bridge.py — Abvorn <-> n8n integration bridge.

Trigger n8n workflows via webhook paths and report connection status.
Defaults align with the real stack: n8n listens on port 5678 and the Abvorn
mobile server (the webhook target) listens on port 8080.

All calls are optional and never fatal — a missing n8n returns a failed
result dict instead of raising, matching the repo's integration convention.
"""

import json
import logging
import os
import socket
from datetime import datetime
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_N8N_HOST = "localhost"
DEFAULT_N8N_PORT = 5678
DEFAULT_ABVORN_WEBHOOK_BASE = "http://localhost:8080"

# Webhook paths this bridge can trigger on the n8n side. These must match
# the workflow's webhook node path (see n8n/workflows/*.json).
REFLECTION_WEBHOOK_PATH = "abvorn-reflection"
PUBLISH_WEBHOOK_PATH = "abvorn-publish"
GSC_ANALYSIS_WEBHOOK_PATH = "abvorn-gsc-analysis"
EVOLUTION_WEBHOOK_PATH = "abvorn-evolution"
VIDEO_RENDER_WEBHOOK_PATH = "abvorn-video-render"


class N8NBridge:
    """Trigger n8n workflows and report n8n health."""

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        self.host = host or os.getenv("N8N_HOST", DEFAULT_N8N_HOST)
        self.port = port if port is not None else int(
            os.getenv("N8N_PORT", str(DEFAULT_N8N_PORT))
        )
        self.base_url = f"http://{self.host}:{self.port}"
        self.api_key = os.getenv("N8N_API_KEY", "")
        self.webhook_base = os.getenv(
            "ABVORN_WEBHOOK_BASE", DEFAULT_ABVORN_WEBHOOK_BASE
        )
        self.headers = {
            "Content-Type": "application/json",
            "X-N8N-API-KEY": self.api_key,
        }

    # ── n8n → Abvorn (webhooks the workflows call back into) ──────────
    def abvorn_webhook_url(self, action: str) -> str:
        """URL the n8n workflows POST back to (the mobile server)."""
        return f"{self.webhook_base}/webhook/abvorn/{action}"

    # ── Abvorn → n8n (trigger workflow webhooks) ─────────────────────
    def trigger_workflow(self, webhook_path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST data to an n8n workflow webhook. Never raises."""
        url = f"{self.base_url}/webhook/{webhook_path}"
        try:
            response = requests.post(url, json=data, headers=self.headers, timeout=30)
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError:
                payload = {"text": response.text[:500]}
            return {"success": True, "data": payload}
        except Exception as e:
            logger.error("Workflow %s failed: %s", webhook_path, e)
            return {"success": False, "error": str(e)}

    def generate_reflection_workflow(self, content_id: str, platform: str) -> Dict[str, Any]:
        """Trigger the reflection pipeline in n8n."""
        return self.trigger_workflow(REFLECTION_WEBHOOK_PATH, {
            "content_id": content_id,
            "platform": platform,
            "timestamp": datetime.now().isoformat(),
        })

    def publish_workflow(self, content: Dict, platforms: list) -> Dict[str, Any]:
        """Trigger the content publishing pipeline in n8n."""
        return self.trigger_workflow(PUBLISH_WEBHOOK_PATH, {
            "content": content,
            "platforms": platforms,
            "timestamp": datetime.now().isoformat(),
        })

    def gsc_analysis_workflow(self, days: int = 7) -> Dict[str, Any]:
        """Trigger the GSC analytics pipeline in n8n."""
        return self.trigger_workflow(GSC_ANALYSIS_WEBHOOK_PATH, {
            "days": days,
            "timestamp": datetime.now().isoformat(),
        })

    def evolution_workflow(self, generation: int) -> Dict[str, Any]:
        """Trigger the evolution check in n8n."""
        return self.trigger_workflow(EVOLUTION_WEBHOOK_PATH, {
            "generation": generation,
            "timestamp": datetime.now().isoformat(),
        })

    def render_video_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger the MoneyPrinterTurbo render pipeline in n8n.

        The payload is a TaskVideoRequest-shaped dict (see
        abvorn.core.video_render.build_video_payload).
        """
        return self.trigger_workflow(VIDEO_RENDER_WEBHOOK_PATH, {
            "video": payload,
            "timestamp": datetime.now().isoformat(),
        })

    # ── Status ────────────────────────────────────────────────────────
    def health(self) -> Dict[str, Any]:
        """Report whether n8n is reachable on its health endpoint."""
        try:
            with socket.create_connection((self.host, self.port), timeout=3):
                pass
            return {
                "status": "connected",
                "n8n_url": self.base_url,
                "healthy": True,
            }
        except Exception as e:
            return {
                "status": "error",
                "n8n_url": self.base_url,
                "healthy": False,
                "error": str(e),
            }


def _healthz() -> Dict[str, Any]:
    """Synchronous healthz probe used by the dashboard (short timeout)."""
    bridge = get_n8n_bridge()
    try:
        response = requests.get(f"{bridge.base_url}/healthz", timeout=2)
        return {
            "status": "connected",
            "healthy": response.status_code == 200,
            "n8n_url": bridge.base_url,
        }
    except Exception:
        return {"status": "error", "healthy": False, "n8n_url": bridge.base_url}


_n8n = None


def get_n8n_bridge() -> N8NBridge:
    global _n8n
    if _n8n is None:
        _n8n = N8NBridge()
    return _n8n