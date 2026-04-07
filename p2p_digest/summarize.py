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
            "Partner = P2P Partner property (demand_partner_property). "
            "deal_lines_by_partner lists each deal: days_in_form_signed, carry_estimate_usd, sla_emoji (hours in Form signed), "
            "last_hubspot_activity_at_utc, days_since_last_hubspot_activity (from HubSpot deal fields in "
            "hubspot_last_activity_properties — not full message threads). "
        )
    mode = (metrics.get("funnel_start_mode") or "form_signed").lower()
    if mode == "created":
        funnel_phrase = (
            "For completed deals, the JSON may use deal *created* through Integration entered "
            "(overall.avg_days_form_signed_to_integration_completed)."
        )
    else:
        funnel_phrase = (
            "For completed deals, the span is Form signed through Integration entered "
            "(overall.avg_days_form_signed_to_integration_completed)."
        )

    structure = """
You MUST structure your reply in this exact order, using these section titles as plain text lines (no # markdown):

1) EXECUTIVE SUMMARY
   2–4 sentences on pipeline health, biggest risks, and total carry picture.

2) PRIORITIES AND ACTIONS BY PARTNER
   For every partner name that appears as a key in deal_lines_by_partner with at least one deal:
   - Print the partner name alone on its own line in Slack mrkdwn bold, e.g. *Nexxen* or *Magnite* (asterisks around the exact name).
   - Order partners by overall urgency: prefer partners with higher total carry, older deals in Form signed, more 🔴/🟡 deals, and staler last_hubspot_activity (higher days_since_last_hubspot_activity or null activity).
   - Under each partner, use bullets for concrete ACTIONS (who to contact, what to do). Use exact dealname strings from JSON when naming deals.
   - "Partner" in outreach means the demand-side P2P partner (e.g. Nexxen, Magnite). "Publisher" or "app side" means the counterparty implied by the deal name (studio/game/app) when obvious — do not invent company names not hinted in dealname.
   - Recommend specific touch types only (e.g. email partner AM, Slack publisher, schedule integration check-in) — do not fabricate email addresses or quotes.

3) TOP CROSS-CUTTING ACTIONS TODAY
   3–7 bullets: the single most important follow-ups across all partners, prioritized by time in column and money at risk.

Rules: Use ONLY figures and deal names from the JSON. If last activity is null, say so and still recommend outreach. Section titles (1–3) stay plain text. Elsewhere use short paragraphs and bullets; only allowed mrkdwn is *bold* for partner heading lines in section 2; no other markdown.
"""

    prompt = (
        "You write a concise daily operations brief for a revenue team working P2P integrations.\n"
        f"{structure}\n"
        "Use ONLY the JSON — do not invent numbers, partners, or deals.\n"
        f"{scope_note}"
        f"Also briefly cover: volume, Form signed vs Integration counts, created→now and {funnel_phrase} "
        "inside the executive summary where relevant. Compare Nexxen vs non-Nexxen only using JSON.\n\n"
        f"METRICS_JSON:\n{body}"
    )
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return _message_text(response)
