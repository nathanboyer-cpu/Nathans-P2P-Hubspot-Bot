from __future__ import annotations

import argparse
import json
import sys

from p2p_digest.config import Settings
from p2p_digest.format_slack import build_slack_message
from p2p_digest.hubspot_client import HubSpotClient, deal_properties_for_run, resolved_pipeline_and_stages
from p2p_digest.metrics import compute_metrics, metrics_to_dict
from p2p_digest.slack_notify import post_slack_webhook
from p2p_digest.summarize import summarize_digest


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily P2P HubSpot digest → Slack")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print metrics JSON only; do not call Claude or Slack.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip Claude; post structured snapshot only (requires Slack unless --dry-run).",
    )
    args = parser.parse_args()

    try:
        settings = Settings.load()
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        pipeline_id, form_id, integ_id = resolved_pipeline_and_stages(settings)
    except Exception as e:
        print(f"HubSpot pipeline/stage resolution failed: {e}", file=sys.stderr)
        return 1

    props = deal_properties_for_run(settings, form_id, integ_id)
    client = HubSpotClient(settings)
    try:
        deals = client.search_deals_in_pipeline(pipeline_id, props)
    except Exception as e:
        print(f"HubSpot search failed: {e}", file=sys.stderr)
        return 1

    date_form = settings.date_entered_form_prop(form_id)
    date_int = settings.date_entered_integration_prop(integ_id)
    digest = compute_metrics(
        deals,
        pipeline_id,
        form_id,
        integ_id,
        settings.demand_partner_property,
        date_form,
        date_int,
    )
    payload = metrics_to_dict(digest)

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    if not settings.slack_webhook_url:
        print("SLACK_WEBHOOK_URL is required unless --dry-run.", file=sys.stderr)
        return 1

    summary: str | None = None
    if not args.no_llm:
        if not settings.anthropic_api_key:
            print("ANTHROPIC_API_KEY is required unless --no-llm.", file=sys.stderr)
            return 1
        try:
            summary = summarize_digest(settings, payload)
        except Exception as e:
            print(f"Claude summarization failed: {e}", file=sys.stderr)
            return 1

    text = build_slack_message(summary, payload)
    try:
        post_slack_webhook(settings.slack_webhook_url, text)
    except Exception as e:
        print(f"Slack post failed: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
