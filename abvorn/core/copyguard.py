"""copyguard.py — pre-publish copy gate backed by a self-hosted LanguageTool server.

Every piece of user-facing copy (social posts, emails, product pages) is run
through a local LanguageTool HTTP server before it is published, mirroring the
existing encoding guard in src.deployment.write_checked — but for human
language instead of byte encoding.

Policy (matches how the mojibake guard is structured as a hard blocker):
  - social posts and emails: HARD BLOCK on blocking-severity issues
    (misspellings and grammar errors) before they are posted or sent;
  - pages: REPORT ONLY — issues are logged as warnings, never raised, because
    long LLM-generated articles carry too many false positives to hard-block.

Rules for safety:
  - The server is unreachable -> the gate FAILS OPEN (logs a warning, does not
    block publishing) so an infra hiccup never stops a publish cycle.
  - ABVORN_COPYGUARD=off / 0 / false / no disables the gate entirely.
  - Product model numbers (Dell S2725QS) and other known-good tokens are
    redacted before checking and never counted as issues.
  - data/copyguard_ignore.txt: one per line — a LanguageTool ruleId to ignore,
    or /regex/ to redact arbitrary spans from the checked text.
"""

import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

logger = logging.getLogger("abvorn.core.copyguard")

SERVER_URL = os.environ.get("ABVORN_LT_URL", "http://127.0.0.1:8081/v2/check")
LANGUAGE = "en-US"

REQUEST_TIMEOUT = 3.0
AVAILABILITY_REFRESH = 60.0
MAX_CHUNK = 50_000

# Blocking severity: misspellings and grammar errors. Generated copy that trips
# these should not reach an audience; everything else is report-only.
_BLOCKING_ISSUE_TYPES = {"misspelling", "grammar"}
# Matches are also blocking when the rule is explicitly a typo/grammar rule and
# no issueType was set by the installed grammar.
_BLOCKING_CATEGORIES = {"TYPOS", "GRAMMAR"}

# Product/model-number-like tokens are redacted ('S2725QS', 'LG 27UP650K-W', ...)
# so real brand/model references never read as typos.
REDACT_PATTERNS = [
    re.compile(r"\b[A-Za-z]{2,8}[A-Za-z0-9-]*\s\d{2,5}[A-Za-z0-9-]*\b"),
    re.compile(r"\b[A-Za-z]{0,2}\d{2,5}[A-Za-z0-9-]*\b"),
]

IGNORE_FILE = Path("data/copyguard_ignore.txt")


class CopyGateError(RuntimeError):
    """Raised when copy fails the block-mode gate."""


@dataclass
class GateResult:
    ok: bool
    blocking: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def enabled() -> bool:
    val = os.environ.get("ABVORN_COPYGUARD", "").strip().lower()
    return val not in {"0", "false", "off", "no"}


def _env_ignore_rules() -> set[str]:
    """Parse data/copyguard_ignore.txt: ruleIds or /regex/ redactions."""
    rules: set[str] = set()
    try:
        for line in IGNORE_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rules.add(line)
    except OSError:
        pass
    return rules


def _redact(text: str, ignore_entries: set[str]) -> str:
    text = text.replace("\x00", "")
    for entry in sorted(ignore_entries, key=len, reverse=True):
        if entry.startswith("/") and entry.endswith("/") and len(entry) > 2:
            try:
                text = re.sub(entry[1:-1], " ", text)
            except re.error:
                continue
        else:
            text = text.replace(entry, " ")
    for pat in REDACT_PATTERNS:
        text = pat.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text)


def html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return html
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ")
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return html


def _chunks(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK:
        return [text] if text.strip() else []
    out = []
    while len(text) > MAX_CHUNK:
        cut = text.rfind(" ", 0, MAX_CHUNK)
        if cut <= 0:
            cut = MAX_CHUNK
        piece = text[:cut].strip()
        if piece:
            out.append(piece)
        text = text[cut:].strip()
    if text.strip():
        out.append(text.strip())
    return out


class _Availability:
    _known: bool | None = None
    _at = 0.0

    @classmethod
    def available(cls) -> bool:
        now = time.monotonic()
        if cls._known is None or now - cls._at > AVAILABILITY_REFRESH:
            try:
                resp = requests.get(SERVER_URL, timeout=REQUEST_TIMEOUT)
                cls._known = resp.status_code < 500
            except requests.RequestException:
                cls._known = False
            cls._at = now
            if not cls._known:
                logger.warning(
                    "copyguard: LanguageTool at %s unreachable — gate is FAILING "
                    "OPEN (copy will not be checked)",
                    SERVER_URL.replace("/v2/check", ""),
                )
        return bool(cls._known)


def check_text(text: str, *, ignore: set[str] | None = None) -> list[dict]:
    """Run text through LanguageTool. Returns a list of issue dicts."""
    if not _Availability.available():
        return []
    ignore_entries = _env_ignore_rules() if ignore is None else ignore
    cleaned = _redact(text, ignore_entries)
    issues: list[dict] = []
    for chunk in _chunks(cleaned):
        if not chunk.strip():
            continue
        try:
            resp = requests.post(
                SERVER_URL,
                data={"language": LANGUAGE, "text": chunk},
                timeout=REQUEST_TIMEOUT * 4,
            )
        except requests.RequestException as e:
            logger.warning("copyguard: check request failed: %s", e)
            _Availability._known = False
            break
        if resp.status_code != 200:
            logger.warning("copyguard: server returned %s", resp.status_code)
            continue
        payload = resp.json()
        for m in payload.get("matches", []):
            rule = m.get("rule", {})
            issues.append({
                "rule": rule.get("id", "?"),
                "category": (rule.get("category", {}) or {}).get("id", "?"),
                "issue_type": rule.get("issueType", ""),
                "message": m.get("message", ""),
                "replacement": (m.get("replacements") or [{}])[0].get("value", ""),
                "context": (m.get("context", {}) or {}).get("text", ""),
            })
    return issues


def is_blocking(issue: dict, ignore_rules: set[str] | None = None) -> bool:
    if ignore_rules is None:
        ignore_rules = _env_ignore_rules()
    if issue["rule"] in ignore_rules:
        return False
    return (
        issue["issue_type"] in _BLOCKING_ISSUE_TYPES
        or issue["category"] in _BLOCKING_CATEGORIES
    )


def gate_copy(text: str, label: str, *, mode: str = "report") -> GateResult:
    """Gate a piece of copy before it is published.

    mode="block": ok=False when blocking-severity issues exist.
    mode="report": always ok=True; issues are logged as warnings.
    """
    if not text.strip() or not enabled():
        return GateResult(ok=True)
    issues = check_text(text)
    ignore_rules = _env_ignore_rules()
    blocking = [i for i in issues if is_blocking(i, ignore_rules)]

    def _fmt(i: dict) -> str:
        msg = i["message"] or f"rule {i['rule']}"
        if i.get("replacement"):
            msg += f' — suggestion: "{i["replacement"]}"'
        if i.get("context"):
            msg += f' (context: "...{i["context"]}...")'
        return f"[{i['rule']}] {msg}"

    if blocking and mode == "block":
        for i in blocking:
            logger.error("copyguard BLOCKED %s: %s", label, _fmt(i))
        return GateResult(ok=False, blocking=blocking, issues=issues)

    for i in issues:
        logger.warning("copyguard %s: %s", label, _fmt(i))
    return GateResult(ok=True, blocking=[], issues=issues)


def ensure_server(max_wait: float = 60.0) -> bool:
    """Start the self-hosted LanguageTool server if it is not already running."""
    if _Availability.available():
        return True
    script = Path("scripts/start_languagetool_server.cmd")
    if not script.exists():
        return False
    try:
        subprocess.Popen(
            ["cmd", "/c", str(script), "spawn"],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except OSError as e:
        logger.warning("copyguard: could not launch LanguageTool server: %s", e)
        return False
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        time.sleep(2)
        if _Availability.available():
            return True
    logger.warning("copyguard: LanguageTool server did not come up in %.0fs", max_wait)
    return False