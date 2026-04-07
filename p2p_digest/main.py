from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from p2p_digest.config import Settings
from p2p_digest.format_slack import build_slack_message
from p2p_digest.hubspot_client import HubSpotClient, deal_properties_for_run, resolved_pipeline_and_stages
from p2p_digest.metrics import compute_metrics, metrics_to_dict
from p2p_digest.slack_notify import post_slack
from p2p_digest.summarize import summarize_digest


def _hubspot_partner_filters(settings: Settings) -> list[dict[str, object]]:
    """Optional search filters on the P2P partner property."""
    prop = settings.demand_partner_property
    out: list[dict[str, object]] = []
    if settings.hubspot_require_p2p_partner:
        out.append({"propertyName": prop, "operator": "HAS_PROPERTY"})
    if settings.hubspot_p2p_partner_filter_values:
        out.append(
            {
                "propertyName": prop,
                "operator": "IN",
                "values": list(settings.hubspot_p2p_partner_filter_values),
            }
        )
    return out


def _search_extra_filters(settings: Settings) -> list[dict[str, object]]:
    return list(settings.hubspot_extra_filters) + _hubspot_partner_filters(settings)


def _slack_configured(settings: Settings) -> bool:
    return bool(settings.slack_webhook_url) or bool(
        settings.slack_bot_token and settings.slack_channel_id
    )


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
    parser.add_argument(
        "--test-slack",
        action="store_true",
        help="Post a short test message to Slack only (no HubSpot or Claude).",
    )
    args = parser.parse_args()

    if args.test_slack and args.dry_run:
        print("Do not combine --test-slack with --dry-run.", file=sys.stderr)
        return 1

    if args.test_slack:
        try:
            settings = Settings.load(require_hubspot_token=False)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        if not _slack_configured(settings):
            print(
                "Configure SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID for --test-slack.",
                file=sys.stderr,
            )
            return 1
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        text = (
            f"*P2P HubSpot digest bot — connectivity test*\n"
            f"If you see this in `#hubspot-signed-integrating-tracker`, Slack delivery works.\n"
            f"_Sent at {ts}_"
        )
        try:
            post_slack(settings, text)
        except Exception as e:
            print(f"Slack post failed: {e}", file=sys.stderr)
            return 1
        print("Posted test message to Slack.", file=sys.stderr)
        return 0

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
    scope = settings.hubspot_deal_scope
    try:
        if scope == "form_signed_column":
            deals = client.search_deals_in_pipeline(
                pipeline_id,
                props,
                dealstage_eq=form_id,
                extra_filters=_search_extra_filters(settings),
            )
            stage_scope: tuple[str, ...] = (form_id,)
        elif scope == "entire_pipeline":
            deals = client.search_deals_in_pipeline(
                pipeline_id,
                props,
                extra_filters=_search_extra_filters(settings),
            )
            stage_scope = ()
        else:
            deals = client.search_deals_in_pipeline(
                pipeline_id,
                props,
                dealstage_ids=settings.hubspot_dealstage_ids,
                extra_filters=_search_extra_filters(settings),
            )
            stage_scope = settings.hubspot_dealstage_ids
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
        hubspot_crm_view_id=settings.hubspot_crm_view_id,
        dealstage_filter_ids=stage_scope,
        funnel_start_mode=settings.hubspot_funnel_start,
        carry_usd_per_day=settings.form_signed_carry_usd_per_day,
        include_form_signed_deal_breakdown=(
            settings.hubspot_deal_scope == "form_signed_column"
        ),
    )
    payload = metrics_to_dict(digest)
    payload["deal_scope_mode"] = scope

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    if not _slack_configured(settings):
        print(
            "Configure Slack: SLACK_WEBHOOK_URL, or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID "
            "(unless --dry-run).",
            file=sys.stderr,
        )
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
        post_slack(settings, text)
    except Exception as e:
        print(f"Slack post failed: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
