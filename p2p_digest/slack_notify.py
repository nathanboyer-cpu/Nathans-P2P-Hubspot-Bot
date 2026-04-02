from __future__ import annotations

import httpx


def post_slack_webhook(webhook_url: str, text: str) -> None:
    payload = {"text": text}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(webhook_url, json=payload)
        r.raise_for_status()
