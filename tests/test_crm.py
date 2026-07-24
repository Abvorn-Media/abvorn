import pytest, tempfile
from pathlib import Path
from abvorn.crm.subscriber import SubscriberDB


def test_add_and_get_subscriber():
    with tempfile.TemporaryDirectory() as tmp:
        db = SubscriberDB(Path(tmp) / "crm.db")
        db.add_subscriber("test@example.com", "persona_1", "wireless headphones")
        subs = db.get_subscribers("wireless headphones")
        assert len(subs) == 1
        assert subs[0]["email"] == "test@example.com"
        db.close()


def test_track_open():
    with tempfile.TemporaryDirectory() as tmp:
        db = SubscriberDB(Path(tmp) / "crm.db")
        db.add_subscriber("test@example.com", "persona_1", "niche")
        db.track_open("test@example.com")
        sub = db.get_subscribers("niche")[0]
        assert sub["last_open_at"] is not None
        db.close()


def test_get_sequence():
    with tempfile.TemporaryDirectory() as tmp:
        db = SubscriberDB(Path(tmp) / "crm.db")
        db.save_sequence("wireless headphones", "persona_1", [
            {"day": 1, "subject": "Test", "body": "Body"}
        ])
        seq = db.get_sequence("wireless headphones", "persona_1")
        assert len(seq) == 1
        assert seq[0]["subject"] == "Test"
        db.close()


def test_track_click():
    with tempfile.TemporaryDirectory() as tmp:
        db = SubscriberDB(Path(tmp) / "crm.db")
        db.add_subscriber("test@example.com", "p1", "niche")
        db.track_click("test@example.com")
        sub = db.get_subscribers("niche")[0]
        assert sub["last_click_at"] is not None
        db.close()