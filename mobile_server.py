"""Abvorn Mobile Server — PWA-backed AI command center accessible from phone."""

import os, sys, json, subprocess, logging, shlex, asyncio, re
from pathlib import Path
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from abvorn.core.secrets import load_secrets
from abvorn.core.models import ModelRouter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("mobile_server")

PROJECT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = PROJECT_DIR / "mobile_server" / "static"
HISTORY_FILE = PROJECT_DIR / "mobile_server" / "chat_history.json"

secrets = load_secrets()
router = ModelRouter(secrets, timeout=25)

app = FastAPI(title="Abvorn Mobile Server", version="1.0.0")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

chat_history = []
if HISTORY_FILE.exists():
    try:
        chat_history = json.loads(HISTORY_FILE.read_text())
    except Exception:
        chat_history = []

SYSTEM_PROMPT = r"""You are Abvorn's AI, embedded in a product review content ecosystem. You run on a Windows machine in C:\Users\Jean Mare\Documents\Default Project.

You have direct access to:
1. The full project codebase (Python files, HTML templates, docs)
2. Command execution (run any shell command in the project directory)
3. File reading/writing capabilities

PROJECT CONTEXT:
- We build an API-free content ecosystem for Abvorn product reviews
- 10 niches: wireless-headphones, gaming-mice, 4k-monitors, laptops, streaming-devices, mechanical-keyboards, wireless-earbuds, fitness-trackers, webcams, smart-home
- Core AI signals: CI (Contrarian Index), EAS (Emotional Arc Score), SSI (Silent Signal Index), RV (Regret Velocity)
- NDC 2.0 pipeline with ChromaDB knowledge base and analytics bridge
- All AI via free Kilo Gateway models (Qwen, Gemini, Groq, DeepSeek)
- Content builds to docs/ folder, deployable to GitHub Pages
- The user is in China — prefer providers that work well there (Qwen/dashscope, DeepSeek)

When the user asks you to do something:
1. If it's a question, answer from your knowledge
2. If it's a command or task, explain what you'll do, then execute it
3. Show command output clearly
4. Ask clarifying questions when needed

Keep responses concise and action-oriented. You can run python scripts, read/write files, and manage the project."""


class ChatMessage(BaseModel):
    message: str
    stream: bool = False


class CommandRequest(BaseModel):
    command: str
    cwd: Optional[str] = None


class FileRequest(BaseModel):
    path: str
    content: Optional[str] = None


@app.get("/")
async def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
async def health():
    h = router.health()
    return {
        "status": "ok" if h["healthy"] else "degraded",
        "providers": h,
        "project": "Abvorn Content Ecosystem",
        "niches": ["wireless-headphones", "gaming-mice", "4k-monitors", "laptops",
                   "streaming-devices", "mechanical-keyboards", "wireless-earbuds",
                   "fitness-trackers", "webcams", "smart-home"],
        "chat_history": len(chat_history),
    }


@app.get("/api/providers")
async def provider_stats():
    return {"providers": router.get_stats()}


def _call_ai_subprocess(prompt: str) -> str:
    """Call AI in a subprocess with hard timeout. Kills if hung."""
    import subprocess as sp, sys
    script = '''
import json, sys
sys.path.insert(0, r"''' + PROJECT_DIR.as_posix() + '''")
from abvorn.core.secrets import load_secrets
from abvorn.core.models import ModelRouter
s = load_secrets()
r = ModelRouter(s, timeout=20)
resp = r.ask("''' + prompt.replace('"', '\\"').replace("'", "\\'") + '''", system="''' + SYSTEM_PROMPT.replace('"', '\\"').replace("'", "\\'") + '''")
print(json.dumps({"response": resp or ""}))
'''
    try:
        p = sp.run([sys.executable, '-c', script], capture_output=True, text=True,
                    timeout=90, cwd=str(PROJECT_DIR))
        if p.returncode == 0 and p.stdout:
            data = json.loads(p.stdout.strip())
            return data.get("response", "")
        logger.warning(f"AI subprocess failed: {p.stderr[:200]}")
        return ""
    except sp.TimeoutExpired:
        logger.warning("AI subprocess timed out (>90s)")
        return ""
    except Exception as e:
        logger.warning(f"AI subprocess error: {e}")
        return ""


@app.post("/api/chat")
async def chat(msg: ChatMessage):
    chat_history.append({"role": "user", "content": msg.message, "timestamp": datetime.now().isoformat()})
    logger.info(f"Chat request: {msg.message[:50]}")
    response_text = _call_ai_subprocess(msg.message)
    if not response_text:
        response_text = "All AI providers unavailable or timed out. Check network/firewall — DeepSeek, Qwen, and GLM should work from China."
    chat_history.append({"role": "assistant", "content": response_text, "timestamp": datetime.now().isoformat()})
    while len(chat_history) > 200:
        chat_history.pop(0)
    try:
        HISTORY_FILE.write_text(json.dumps(chat_history, indent=2, ensure_ascii=False))
    except Exception:
        pass
    return {"response": response_text, "history_count": len(chat_history)}


@app.post("/api/exec")
async def execute(cmd: CommandRequest):
    cwd = cmd.cwd or str(PROJECT_DIR)
    safe_path = Path(cwd).resolve()
    if not str(safe_path).startswith(str(PROJECT_DIR)):
        return JSONResponse({"error": "Command path outside project directory"}, status_code=403)
    dangerous = ["rm -rf", "format", "del /f", "rd /s", "shutdown", "restart-computer"]
    for d in dangerous:
        if d.lower() in cmd.command.lower():
            return JSONResponse({"error": f"Dangerous command blocked: {d}"}, status_code=403)
    try:
        result = subprocess.run(
            cmd.command, shell=True, capture_output=True, text=True,
            cwd=str(safe_path), timeout=120,
        )
        output = result.stdout or ""
        if result.stderr:
            output += "\n--- STDERR ---\n" + result.stderr
        if result.returncode != 0:
            output += f"\n--- EXIT CODE: {result.returncode} ---"
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode, "output": output}
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "Command timed out after 120s"}, status_code=408)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/read")
async def read_file(req: FileRequest):
    path = Path(req.path)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    path = path.resolve()
    if not str(path).startswith(str(PROJECT_DIR)):
        return JSONResponse({"error": "Path outside project directory"}, status_code=403)
    if not path.exists():
        return JSONResponse({"error": "Path not found"}, status_code=404)
    if path.is_dir():
        items = []
        for entry in sorted(path.iterdir()):
            items.append({
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else 0,
                "modified": datetime.fromtimestamp(entry.stat().st_mtime).isoformat(),
            })
        return {"type": "directory", "path": str(path), "items": items}
    try:
        content = path.read_text(encoding="utf-8")
        return {"type": "file", "path": str(path), "content": content, "size": path.stat().st_size}
    except Exception as e:
        return JSONResponse({"error": f"Cannot read file: {e}"}, status_code=500)


@app.post("/api/write")
async def write_file(req: FileRequest):
    path = Path(req.path)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    path = path.resolve()
    if not str(path).startswith(str(PROJECT_DIR)):
        return JSONResponse({"error": "Path outside project directory"}, status_code=403)
    if req.content is None:
        return JSONResponse({"error": "No content provided"}, status_code=400)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(req.content, encoding="utf-8")
        return {"status": "ok", "path": str(path), "size": len(req.content)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/history")
async def get_history(limit: int = 50):
    return {"history": chat_history[-limit:]}


@app.post("/api/history/clear")
async def clear_history():
    chat_history.clear()
    try:
        HISTORY_FILE.write_text("[]")
    except Exception:
        pass
    return {"status": "ok"}


if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"\n  Abvorn Mobile Server running!")
    print(f"  Local:   http://localhost:8080")
    print(f"  Network: http://{local_ip}:8080")
    print(f"  Open on your phone browser to access the PWA.\n")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
