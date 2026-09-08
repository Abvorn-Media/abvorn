"""Regression tests for bounded PDF extraction in abvorn.brain.scanner.

A pathological PDF (broken xref that makes pypdf rebuild tables forever) must
never hang a brain refresh. extract_text() caps wall-clock time and remembers
failed paths for the rest of the process.
"""

import pytest
import time

from abvorn.brain import scanner


@pytest.fixture(autouse=True)
def _reset_failures():
    scanner._EXTRACT_FAILURES.clear()
    yield
    scanner._EXTRACT_FAILURES.clear()


def test_extract_text_returns_extracted_text(monkeypatch):
    def _fake_worker(pdf_path, limit):
        return "pages worth of text"

    monkeypatch.setattr(scanner, "_extract_pdf_text", _fake_worker)
    assert scanner.extract_text("books/guide.pdf", timeout=5) == "pages worth of text"


def test_extract_text_swallows_exceptions(monkeypatch):
    def _boom(pdf_path, limit):
        raise RuntimeError("corrupt pdf")

    monkeypatch.setattr(scanner, "_extract_pdf_text", _boom)
    assert scanner.extract_text("books/broken.pdf", timeout=5) == ""


def test_extract_text_timeout_returns_empty_and_skips_next_time(monkeypatch):
    started = []

    def _slow(pdf_path, limit):
        started.append(pdf_path)
        time.sleep(60)

    monkeypatch.setattr(scanner, "_extract_pdf_text", _slow)

    # First call: the worker is abandoned after `timeout` and "" is returned.
    assert scanner.extract_text("books/hanging.pdf", timeout=0.05) == ""

    # The path is remembered, so the second call returns instantly WITHOUT
    # spawning the worker again (this is what stops a refresh from re-blocking).
    assert scanner.extract_text("books/hanging.pdf", timeout=5) == ""
    assert len(started) == 1