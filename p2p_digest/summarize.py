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
    scope = (metrics.get("deal_scope_mode") or "").lower()
    scope_note = ""
    if scope == "form_signed_column":
        scope_note = (
            "The dataset is scoped to deals currently in the Form signed stage only. "
            "Partner splits use the P2P Partner deal property (see demand_partner_property in JSON); mention counts and age. "
        )
    mode = (metrics.get("funnel_start_mode") or "form_signed").lower()
    if mode == "created":
        funnel_phrase = (
            "For completed deals, the JSON uses deal *created* date through Integration entered "
            "(see overall.avg_days_form_signed_to_integration_completed — label is historical). "
            "Do not mention Form signed for that span unless referring to deals_reached_form_signed."
        )
    else:
        funnel_phrase = (
            "For completed deals, the span is Form signed through Integration entered "
            "(overall.avg_days_form_signed_to_integration_completed)."
        )
    prompt = (
        "You write a concise daily operations summary for a revenue team. "
        "Use ONLY the JSON figures provided — do not invent numbers or partners. "
        f"{scope_note}"
        f"Cover: pipeline volume; how many deals reached Form signed vs Integration; "
        f"overall time in pipeline (created→now); {funnel_phrase} "
        "Call out P2P Partner buckets that stand out (fast/slow or high volume); "
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
