"""Tests for canonical Search Console property selection (fake service only)."""

import logging

import pytest

from abvorn.core import gsc_client
from abvorn.core.gsc_client import GSCClient

OVERRIDE_ENV = "ABVORN_GSC_PROPERTY"  # literal on purpose: locks in the public env var name


class _FakeSites:
    def __init__(self, entries):
        self._entries = entries

    def list(self):
        return self

    def execute(self):
        return {"siteEntry": self._entries}


class _FakeService:
    def __init__(self, entries):
        self._entries = entries

    def sites(self):
        return _FakeSites(self._entries)


def _entry(url, permission="siteOwner"):
    return {"siteUrl": url, "permissionLevel": permission}


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv(OVERRIDE_ENV, raising=False)


def _client(monkeypatch, tmp_path, entries):
    """Build a real GSCClient whose service is a fake; no credentials are used."""
    creds = tmp_path / "dummy.json"
    creds.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gsc_client, "_apply_system_proxy", lambda: None)
    monkeypatch.setattr(
        gsc_client.service_account.Credentials,
        "from_service_account_file",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(gsc_client, "build", lambda *args, **kwargs: _FakeService(entries))
    return GSCClient(str(creds))


def test_override_selects_existing_property_exactly(monkeypatch, tmp_path, caplog):
    entries = [
        _entry("https://foo.github.io/"),
        _entry("sc-domain:abvorn.com"),
        _entry("https://abvorn.com/blog/"),
    ]
    monkeypatch.setenv(OVERRIDE_ENV, "https://abvorn.com/blog/")

    with caplog.at_level(logging.INFO, logger=gsc_client.logger.name):
        client = _client(monkeypatch, tmp_path, entries)

    assert client.enabled is True
    assert client.property_url == "https://abvorn.com/blog/"
    assert "GSC property selected: https://abvorn.com/blog/" in caplog.text


def test_missing_override_warns_and_falls_through(monkeypatch, tmp_path, caplog):
    entries = [_entry("https://foo.github.io/"), _entry("sc-domain:abvorn.com")]
    monkeypatch.setenv(OVERRIDE_ENV, "sc-domain:missing.example")

    with caplog.at_level(logging.WARNING, logger=gsc_client.logger.name):
        client = _client(monkeypatch, tmp_path, entries)

    assert client.enabled is True
    assert client.property_url == "sc-domain:abvorn.com"
    assert client.property_url != "sc-domain:missing.example"
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_listed_but_unverified_override_warns_and_falls_through(
    monkeypatch, tmp_path, caplog
):
    """A canonical but unverified override must never be queried (design #4)."""
    entries = [
        _entry("sc-domain:abvorn.com", permission="siteUnverifiedUser"),
        _entry("https://abvorn.com/reviews/", permission="siteOwner"),
    ]
    monkeypatch.setenv(OVERRIDE_ENV, "sc-domain:abvorn.com")

    with caplog.at_level(logging.WARNING, logger=gsc_client.logger.name):
        client = _client(monkeypatch, tmp_path, entries)

    assert client.enabled is True
    assert client.property_url == "https://abvorn.com/reviews/"
    assert client.property_url != "sc-domain:abvorn.com"
    assert any(
        "unverified" in r.getMessage().lower()
        and OVERRIDE_ENV in r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.WARNING
    )
    assert not any(
        "not available to this service account" in r.getMessage()
        for r in caplog.records
    )


def test_domain_property_beats_github_io_listed_first(monkeypatch, tmp_path, caplog):
    entries = [_entry("https://foo.github.io/"), _entry("sc-domain:abvorn.com")]

    with caplog.at_level(logging.WARNING, logger=gsc_client.logger.name):
        client = _client(monkeypatch, tmp_path, entries)

    assert client.property_url == "sc-domain:abvorn.com"
    assert not any("host mismatch" in r.getMessage().lower() for r in caplog.records)


def test_https_abvorn_url_beats_github_io(monkeypatch, tmp_path, caplog):
    entries = [
        _entry("https://foo.github.io/"),
        _entry("https://abvorn.com/reviews/laptops/"),
    ]

    with caplog.at_level(logging.WARNING, logger=gsc_client.logger.name):
        client = _client(monkeypatch, tmp_path, entries)

    assert client.property_url == "https://abvorn.com/reviews/laptops/"
    assert not any("host mismatch" in r.getMessage().lower() for r in caplog.records)


@pytest.mark.parametrize(
    "property_id",
    [
        "https://www.abvorn.com/",
        "http://abvorn.com/",
        "https://foo.github.io/",
    ],
)
def test_noncanonical_selection_warns_host_mismatch(
    monkeypatch, tmp_path, caplog, property_id
):
    with caplog.at_level(logging.INFO, logger=gsc_client.logger.name):
        client = _client(monkeypatch, tmp_path, [_entry(property_id)])

    assert client.property_url == property_id
    assert f"GSC property selected: {property_id}" in caplog.text
    assert any(
        "host mismatch" in r.getMessage().lower()
        for r in caplog.records
        if r.levelno >= logging.WARNING
    )


def test_noncanonical_verified_list_keeps_first_entry_fallback(monkeypatch, tmp_path):
    entries = [
        _entry("https://one.github.io/"),
        _entry("https://two.github.io/"),
    ]
    client = _client(monkeypatch, tmp_path, entries)
    assert client.property_url == "https://one.github.io/"


def test_empty_property_list_disables_client(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, [])
    assert client.enabled is False
    assert client.property_url is None
