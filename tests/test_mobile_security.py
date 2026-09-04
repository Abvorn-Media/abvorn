"""Regression tests for mobile server security hardening (S3 exec + S5 write).

Shell execution and arbitrary writes are masked unless ABVORN_ALLOW_EXEC=1 and
a token are set, and those flags are read at import time. So we set them at
module scope BEFORE mobile_server is first imported.
"""

import os

os.environ["ABVORN_ALLOW_EXEC"] = "1"
os.environ["ABVORN_API_TOKEN"] = "test-token"

import mobile_server
from fastapi.testclient import TestClient

CLIENT = TestClient(mobile_server.app)
AUTH = {"Authorization": "Bearer test-token"}


def test_exec_runs_simple_command_without_shell():
    resp = CLIENT.post("/api/exec", json={"command": "python --version"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["returncode"] == 0
    assert "python" in body["stdout"].lower()


def test_exec_rejects_empty_command():
    resp = CLIENT.post("/api/exec", json={"command": "   "}, headers=AUTH)
    assert resp.status_code == 400


def test_write_allows_normal_file(tmp_path):
    resp = CLIENT.post("/api/write", json={"path": "notes/security_test.txt", "content": "hi"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_write_blocks_protected_secret_files():
    # Overwriting credential/config stores must be rejected (S5).
    for protected in [".env", "secrets.json", "config.yaml", "requirements.txt"]:
        resp = CLIENT.post("/api/write", json={"path": protected, "content": "pwned"}, headers=AUTH)
        assert resp.status_code == 403, f"{protected} was not protected: {resp.status_code}"


def test_exec_denylist_blocks_destructive_command():
    # Denylist is defense-in-depth; destructive patterns must still be rejected.
    resp = CLIENT.post("/api/exec", json={"command": "rm -rf /"}, headers=AUTH)
    assert resp.status_code == 403
