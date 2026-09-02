"""abvorn_evolution_check.py — Lightweight replacement for the n8n evolution-check workflow.

Replicates the flow from n8n/workflows/abvorn-evolution-check.json:
  1. POST to mobile server /webhook/abvorn/evolution_check
  2. Check should_evolve flag
  3. If true, trigger evolution (placeholder — logs the event)

Run standalone or via Windows Task Scheduler (weekly).
"""

import json
import logging
import sys
import urllib.request
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("var/evolution_check.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("evolution_check")

MOBILE_SERVER = "http://127.0.0.1:8080"
EVOLUTION_ENDPOINT = f"{MOBILE_SERVER}/webhook/abvorn/evolution_check"
EVOLUTION_LOG = "data/evolution_journal.json"


def check_evolution() -> dict:
    """Call the mobile server's evolution_check endpoint."""
    log.info("POST %s", EVOLUTION_ENDPOINT)
    req = urllib.request.Request(
        EVOLUTION_ENDPOINT,
        data=json.dumps({}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode())
        log.info("Response: %s", json.dumps(result, indent=2)[:500])
        return result
    except Exception as e:
        log.error("evolution_check failed: %s", e)
        return {"success": False, "error": str(e)}


def trigger_evolution(lineage: dict) -> dict:
    """Placeholder for actual evolution trigger. Logs the event."""
    log.info("Evolution triggered — lineage: %s", json.dumps(lineage)[:300])
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": "evolution_check_triggered",
        "lineage": lineage,
    }
    try:
        with open(EVOLUTION_LOG, "r", encoding="utf-8") as f:
            journal = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        journal = []
    journal.append(entry)
    with open(EVOLUTION_LOG, "w", encoding="utf-8") as f:
        json.dump(journal, f, indent=2, ensure_ascii=False)
    log.info("Logged evolution event to %s", EVOLUTION_LOG)
    return entry


def main():
    log.info("=== Evolution check started ===")
    result = check_evolution()

    if not result.get("success"):
        log.warning("evolution_check returned success=false: %s", result)
        return

    should_evolve = result.get("should_evolve", False)
    lineage = result.get("lineage", {})

    if should_evolve:
        log.info("should_evolve=True — triggering evolution")
        trigger_evolution(lineage)
    else:
        log.info("should_evolve=False — skipping (generations=%s)", lineage.get("generations", []))

    log.info("=== Evolution check complete ===")


if __name__ == "__main__":
    main()
