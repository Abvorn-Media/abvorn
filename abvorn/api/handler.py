"""Simple HTTP request handler for the subscribe API."""

import json
from urllib.parse import parse_qs
from .subscribe import handle_subscribe

def lambda_handler(event: dict, context=None, db_path=None) -> dict:
    """AWS Lambda / API Gateway compatible handler.
    event should have: body (JSON string or dict), or queryStringParameters."""
    try:
        if isinstance(event.get("body"), str):
            data = json.loads(event["body"])
        elif isinstance(event.get("body"), dict):
            data = event["body"]
        elif event.get("queryStringParameters"):
            data = event["queryStringParameters"]
        else:
            data = {}
    except (json.JSONDecodeError, TypeError):
        return {"statusCode": 400, "body": json.dumps({"status": "error", "message": "Invalid JSON"})}

    result = handle_subscribe(data, db_path=db_path)
    if result["status"] == "ok":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result)
        }
    return {
        "statusCode": 400,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result)
    }