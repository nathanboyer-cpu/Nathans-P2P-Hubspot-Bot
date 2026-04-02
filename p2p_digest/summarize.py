from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic

from p2p_digest.config import Settings


def _message_text(response: Any) -> str:
    parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def summarize_digest(settings: Settings, metrics: dict[str, Any]) -> str:
    client = Anthropic(api_key=settings.anthropic_api_key)
    body = json.dumps(metrics, indent=2)
    prompt = (
        "You write a concise daily operations summary for a revenue team. "
        "Use ONLY the JSON figures provided — do not invent numbers or partners. "
        "Cover: pipeline volume; how many deals reached Form signed vs Integration; "
        "overall time in pipeline (created→now) and form-signed→integration for completed deals; "
        "call out Demand Partner partners that stand out (fast/slow or high volume); "
        "compare Nexxen vs non-Nexxen buckets. "
        "Use short paragraphs and bullets. Plain text only, no markdown headings.\n\n"
        f"METRICS_JSON:\n{body}"
    )
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return _message_text(response)
