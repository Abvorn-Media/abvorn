"""Tests for MentionWatcher — polls Composio for mentions with dedup."""
import pytest
from unittest.mock import MagicMock, patch
from abvorn.engagement.watcher import MentionWatcher


def test_watcher_initializes():
    mw = MentionWatcher(composio_key="test", state=None)
    assert mw is not None
    assert mw.poll_interval == 900


def test_poll_returns_list():
    mw = MentionWatcher(composio_key="test", state=None)
    result = mw.poll()
    assert isinstance(result, list)


def test_poll_deduplicates():
    mw = MentionWatcher(composio_key="test", state=None)
    mw._replied_ids.add("dup_1")
    mw._raw_mentions = [{"id": "dup_1", "text": "This is an old mention we already replied to"}, {"id": "new_1", "text": "This is a brand new mention we should include"}]
    result = mw.poll()
    assert len(result) == 1
    assert result[0]["id"] == "new_1"


def test_filter_substantive_only():
    mw = MentionWatcher(composio_key="test", state=None)
    mw._raw_mentions = [
        {"id": "1", "text": "@abvorn nice!", "author": "user1"},
        {"id": "2", "text": "Does this work with Samsung TVs? I've been looking for something like this.", "author": "user2"},
        {"id": "3", "text": "lol", "author": "user3"},
    ]
    result = mw.poll()
    assert len(result) == 1
    assert result[0]["id"] == "2"


def test_no_key_returns_empty():
    mw = MentionWatcher(composio_key="", state=None)
    assert mw.poll() == []
