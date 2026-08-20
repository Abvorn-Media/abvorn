"""video_render.py — Abvorn <-> MoneyPrinterTurbo (MPT) video rendering bridge.

Submit Colosseum-refined scripts or domination viral scripts to a
MoneyPrinterTurbo instance and poll for the rendered video. Mirrors the
n8n_bridge conventions: all calls are optional and never fatal — a missing
or unreachable MPT returns a failed result dict instead of raising.

MPT API (2026, FastAPI, harry0703/MoneyPrinterTurbo v1.3+):
    POST /api/v1/videos             submit a TaskVideoRequest
    GET  /api/v1/tasks              list tasks
    GET  /api/v1/tasks/{task_id}    query status (state: 1=complete, 4=processing, -1=failed)
    GET  /api/v1/download/{path}    download a finished video
    GET  /api/v1/stream/{path}      range streaming

Config (env):
    ABVORN_MPT_URL       base URL of the MPT instance (default http://localhost:8080)
    ABVORN_MPT_VOICE     edge-tts voice name (default en-US-AriaNeural-Female)
"""

import logging
import os
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_MPT_URL = "http://localhost:8080"
DEFAULT_VOICE = "en-US-AriaNeural-Female"

# MoneyPrinterTurbo v1.3+ places all API routes under /api/v1.
MPT_API_PREFIX = "/api/v1"

# MPT task states (app/models/const.py)
TASK_STATE_FAILED = -1
TASK_STATE_COMPLETE = 1
TASK_STATE_PROCESSING = 4

# n8n workflow webhook path that forwards a render request to MPT.
VIDEO_RENDER_WEBHOOK_PATH = "abvorn-video-render"

# Map our platform names to MPT VideoAspect values.
_PLATFORM_ASPECT = {
    "tiktok": "9:16",
    "reels": "9:16",
    "shorts": "9:16",
    "x": "9:16",
    "twitter": "9:16",
    "instagram": "1:1",
    "pinterest": "9:16",
    "youtube": "16:9",
    "linkedin": "16:9",
}


def platform_aspect(platform: str) -> str:
    """MPT aspect ratio for a platform name (defaults to portrait 9:16)."""
    return _PLATFORM_ASPECT.get((platform or "").lower(), "9:16")


def build_video_payload(
    source: Dict[str, Any],
    *,
    platform: str = "tiktok",
    subject: Optional[str] = None,
    terms: Optional[list] = None,
    aspect: Optional[str] = None,
    voice_name: Optional[str] = None,
    subtitle: bool = True,
) -> Dict[str, Any]:
    """Convert a Colosseum carousel or domination script into an MPT
    TaskVideoRequest payload.

    Accepts:
      - Colosseum conduct_debate() output: has ``slides`` dict with keys
        hook, problem, verdict, breakdown, comparison, call, plus
        ``product_name``.
      - Domination viral script: has ``script`` dict with hook/body/cta, or
        a list of slides (carousel/thread).
      - Any dict with hook/body/caption text.
    """
    video_script = _extract_script_text(source)
    if not video_script:
        video_script = subject or source.get("video_subject") or ""

    subject = subject or source.get("product_name") or source.get("video_subject") or (
        source.get("title") or ""
    )

    if not terms:
        raw = source.get("video_terms") or source.get("terms") or []
        if isinstance(raw, str):
            terms = [t.strip() for t in raw.split(",") if t.strip()]
        elif isinstance(raw, list):
            terms = [str(t) for t in raw][:10]
        else:
            terms = []
    if not terms and subject:
        terms = [subject[:50]]

    payload = {
        "video_subject": subject,
        "video_script": video_script,
        "video_terms": terms,
        "video_aspect": aspect or platform_aspect(platform),
        "video_concat_mode": "random",
        "video_clip_duration": 5,
        "video_count": 1,
        "video_source": "pexels",
        "voice_name": voice_name or os.getenv("ABVORN_MPT_VOICE", DEFAULT_VOICE),
        "voice_rate": 1.0,
        "bgm_type": "random",
        "bgm_volume": 0.2,
        "subtitle_enabled": subtitle,
        "paragraph_number": 1,
    }

    # Explicit material URLs (Pexels asset fetcher output) override the
    # provider search, mirroring MPT's video_materials field.
    materials = source.get("video_materials") or source.get("materials")
    if isinstance(materials, list) and materials:
        payload["video_materials"] = [
            {"provider": "pexels", "url": m["url"]}
            for m in materials[:10]
            if isinstance(m, dict) and m.get("url")
        ]

    return payload


def _extract_script_text(source: Dict[str, Any]) -> str:
    """Flatten Colosseum slides or domination scripts into voiceover text."""
    slides = source.get("slides")
    if isinstance(slides, dict):
        ordered = [
            slides.get(k, "") for k in ("hook", "problem", "verdict", "breakdown", "comparison", "call")
        ]
        text = ". ".join(s.strip() for s in ordered if s and str(s).strip())
        if text:
            return text[:1500]

    script = source.get("script")
    if isinstance(script, dict):
        parts = [script.get("hook", ""), script.get("body", ""), script.get("cta", "")]
        text = ". ".join(str(p).strip() for p in parts if p and str(p).strip())
        if text:
            return text[:1500]
    if isinstance(script, list):
        parts = [str(s) for s in script if str(s).strip()]
        if parts:
            return ". ".join(parts)[:1500]

    # Plain text fields
    for key in ("hook", "body", "caption", "video_script"):
        val = source.get(key)
        if val and str(val).strip():
            return str(val).strip()[:1500]
    return ""


def _public_task(task: Dict[str, Any], base_url: str) -> Dict[str, Any]:
    """Make task paths absolute URLs via the /download endpoint."""
    result = dict(task)
    for key in ("videos", "combined_videos"):
        items = task.get(key)
        if isinstance(items, list):
            result[key] = [_video_url(item, base_url) for item in items]
    return result


def _video_url(path_or_url: str, base_url: str) -> str:
    if not isinstance(path_or_url, str):
        return path_or_url
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    path = path_or_url.lstrip("/")
    # MPT serves finished videos from its static /tasks mount (task dir).
    if path.startswith("tasks/"):
        return f"{base_url.rstrip('/')}/{path}"
    return f"{base_url.rstrip('/')}{MPT_API_PREFIX}/download/{path}"


class VideoRenderer:
    """Submit and poll MoneyPrinterTurbo render tasks. Never raises."""

    def __init__(self, base_url: Optional[str] = None, timeout: int = 900):
        self.base_url = (base_url or os.getenv("ABVORN_MPT_URL", DEFAULT_MPT_URL)).rstrip("/")
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}

    # ── submit / poll ──────────────────────────────────────────────────
    def submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST /videos. Returns {success, task_id, data} or error dict."""
        try:
            response = requests.post(
                f"{self.base_url}{MPT_API_PREFIX}/videos",
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            task_id = ((data.get("data") or {}).get("task_id")) or (data.get("task_id"))
            if not task_id:
                return {"success": False, "error": "no task_id in response", "data": data}
            logger.info("MPT video task submitted: %s", task_id)
            return {"success": True, "task_id": task_id, "data": data}
        except Exception as e:
            logger.error("MPT submit failed: %s", e)
            return {"success": False, "error": str(e)}

    def status(self, task_id: str) -> Dict[str, Any]:
        """GET /tasks/{task_id}. Returns {success, task, state} or error dict."""
        try:
            response = requests.get(
                f"{self.base_url}{MPT_API_PREFIX}/tasks/{task_id}",
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            task = data.get("data") or {}
            return {"success": True, "task": _public_task(task, self.base_url), "state": task.get("state")}
        except Exception as e:
            logger.error("MPT status failed: %s", e)
            return {"success": False, "error": str(e)}

    def wait(self, task_id: str, poll_interval: float = 10.0) -> Dict[str, Any]:
        """Poll until the task completes or fails. Never raises."""
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            result = self.status(task_id)
            if not result["success"]:
                return result
            task = result["task"]
            state = task.get("state")
            if state == TASK_STATE_COMPLETE:
                return {"success": True, "task": task, "state": state, "completed": True}
            if state == TASK_STATE_FAILED:
                return {
                    "success": False,
                    "task": task,
                    "state": state,
                    "error": task.get("error") or task.get("failed_stage") or "render failed",
                }
            time.sleep(poll_interval)
        return {
            "success": False,
            "error": f"timed out after {self.timeout}s",
            "state": TASK_STATE_PROCESSING,
        }

    # ── convenience ────────────────────────────────────────────────────
    def render(self, source: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Submit a script/carousel and wait for the finished video."""
        payload = build_video_payload(source, **kwargs)
        submitted = self.submit(payload)
        if not submitted["success"]:
            return submitted
        result = self.wait(submitted["task_id"])
        result["task_id"] = submitted["task_id"]
        result["payload"] = payload
        return result

    def health(self) -> Dict[str, Any]:
        """Reachability probe (GET /tasks with page_size=1)."""
        try:
            response = requests.get(
                f"{self.base_url}{MPT_API_PREFIX}/tasks?page=1&page_size=1",
                headers=self.headers,
                timeout=5,
            )
            return {
                "status": "connected" if response.status_code == 200 else "error",
                "healthy": response.status_code == 200,
                "mpt_url": self.base_url,
            }
        except Exception as e:
            return {"status": "error", "healthy": False, "mpt_url": self.base_url, "error": str(e)}


_renderer: Optional[VideoRenderer] = None


def get_video_renderer(base_url: Optional[str] = None) -> VideoRenderer:
    """Singleton accessor."""
    global _renderer
    if _renderer is None or (base_url and base_url != _renderer.base_url):
        _renderer = VideoRenderer(base_url=base_url)
    return _renderer