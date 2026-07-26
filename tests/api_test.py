"""Tests for subscribe API — handler and form generation."""

import json
from pathlib import Path


class TestHandleSubscribe:
    def test_subscribe_valid(self, tmp_path):
        from abvorn.api.subscribe import handle_subscribe
        db_path = tmp_path / "test_crm.db"
        result = handle_subscribe({"name": "Alice", "email": "alice@test.com", "niche": "laptop"}, db_path=db_path)
        assert result["status"] == "ok"
        assert result["email"] == "alice@test.com"
        assert result["niche"] == "laptop"

    def test_subscribe_missing_email(self, tmp_path):
        from abvorn.api.subscribe import handle_subscribe
        db_path = tmp_path / "test_crm.db"
        result = handle_subscribe({"name": "Bob"}, db_path=db_path)
        assert result["status"] == "error"
        assert "email" in result["message"].lower()

    def test_subscribe_invalid_email(self, tmp_path):
        from abvorn.api.subscribe import handle_subscribe
        db_path = tmp_path / "test_crm.db"
        result = handle_subscribe({"name": "Bob", "email": "notanemail"}, db_path=db_path)
        assert result["status"] == "error"

    def test_subscribe_missing_name(self, tmp_path):
        from abvorn.api.subscribe import handle_subscribe
        db_path = tmp_path / "test_crm.db"
        result = handle_subscribe({"email": "bob@test.com"}, db_path=db_path)
        assert result["status"] == "error"
        assert "name" in result["message"].lower()

    def test_subscribe_stores_in_db(self, tmp_path):
        from abvorn.api.subscribe import handle_subscribe
        from abvorn.crm.subscriber import SubscriberDB
        db_path = tmp_path / "test_crm.db"
        handle_subscribe({"name": "Charlie", "email": "charlie@test.com", "niche": "tv"}, db_path=db_path)
        db = SubscriberDB(db_path)
        subs = db.get_subscribers(niche="tv")
        emails = [s["email"] for s in subs]
        assert "charlie@test.com" in emails

    def test_subscribe_default_niche(self, tmp_path):
        from abvorn.api.subscribe import handle_subscribe
        db_path = tmp_path / "test_crm.db"
        result = handle_subscribe({"name": "Diana", "email": "diana@test.com"}, db_path=db_path)
        assert result["status"] == "ok"
        assert result["niche"] == "tech"

    def test_subscribe_form_html(self):
        from abvorn.api.subscribe import subscribe_form_html
        html = subscribe_form_html()
        assert isinstance(html, str)
        assert "subscribe-box" in html
        assert "subscribe-form" in html
        assert "sub-name" in html
        assert "sub-email" in html
        assert "sub-niche" in html
        assert "Never miss a review" in html


class TestLambdaHandler:
    def test_lambda_handler_valid(self, tmp_path):
        from abvorn.api.handler import lambda_handler
        db_path = tmp_path / "crm.db"
        event = {
            "body": json.dumps({"name": "Eve", "email": "eve@test.com", "niche": "monitor"})
        }
        result = lambda_handler(event, db_path=db_path)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "ok"

    def test_lambda_handler_missing_fields(self, tmp_path):
        from abvorn.api.handler import lambda_handler
        event = {"body": json.dumps({})}
        result = lambda_handler(event)
        assert result["statusCode"] == 400

    def test_lambda_handler_invalid_json(self):
        from abvorn.api.handler import lambda_handler
        event = {"body": "not json"}
        result = lambda_handler(event)
        assert result["statusCode"] == 400

    def test_lambda_handler_dict_body(self, tmp_path):
        from abvorn.api.handler import lambda_handler
        event = {"body": {"name": "Frank", "email": "frank@test.com", "niche": "smart home"}}
        result = lambda_handler(event)
        assert result["statusCode"] == 200

    def test_lambda_handler_query_string(self, tmp_path):
        from abvorn.api.handler import lambda_handler
        event = {"queryStringParameters": {"name": "Grace", "email": "grace@test.com", "niche": "tv"}}
        result = lambda_handler(event)
        assert result["statusCode"] == 200