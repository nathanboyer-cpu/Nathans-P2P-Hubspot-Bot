from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Resolve project root (folder containing .env) regardless of cwd; override so a
# pre-set empty env var cannot block values from .env.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)


def _req(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise ValueError(f"Missing required environment variable: {name}")
    return v


def _opt(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _parse_dealstage_ids(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    parts = re.split(r"[\s,]+", raw.strip())
    return tuple(p for p in parts if p)


def _parse_csv_trimmed(raw: str) -> tuple[str, ...]:
    """Comma-separated values (preserves dots in values e.g. Media.net)."""
    if not raw.strip():
        return ()
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def _truthy_env(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _parse_extra_filters_json(raw: str) -> list[dict[str, object]]:
    if not raw.strip():
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("HUBSPOT_EXTRA_FILTERS_JSON must be a JSON array of filter objects.")
    out: list[dict[str, object]] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each entry in HUBSPOT_EXTRA_FILTERS_JSON must be an object.")
        out.append(item)
    return out


@dataclass(frozen=True)
class Settings:
    hubspot_token: str
    anthropic_api_key: str
    slack_webhook_url: str
    slack_bot_token: str
    slack_channel_id: str
    slack_dm_channel_id: str
    demand_partner_property: str
    pipeline_id: str
    stage_form_signed_id: str
    stage_integration_id: str
    stage_form_signed_label: str
    stage_integration_label: str
    pipeline_label_hint: str
    anthropic_model: str
    hubspot_api_base: str
    date_entered_form_property_override: str
    date_entered_integration_property_override: str
    hubspot_crm_view_id: str
    hubspot_dealstage_ids: tuple[str, ...]
    hubspot_extra_filters: list[dict[str, object]]
    hubspot_funnel_start: str
    hubspot_deal_scope: str
    hubspot_require_p2p_partner: bool
    hubspot_p2p_partner_filter_values: tuple[str, ...]

    @classmethod
    def load(cls, *, require_hubspot_token: bool = True) -> Settings:
        if require_hubspot_token:
            hubspot_token = _req("HUBSPOT_ACCESS_TOKEN")
        else:
            hubspot_token = _opt("HUBSPOT_ACCESS_TOKEN", "")
        demand_partner_property = _opt("HUBSPOT_DEMAND_PARTNER_PROPERTY", "p2p_partner")
        pipeline_id = _opt("HUBSPOT_PIPELINE_ID", "")
        stage_form_signed_id = _opt("HUBSPOT_STAGE_FORM_SIGNED_ID", "")
        stage_integration_id = _opt("HUBSPOT_STAGE_INTEGRATION_ID", "")
        stage_form_signed_label = _opt("HUBSPOT_STAGE_FORM_SIGNED_LABEL", "Form signed")
        stage_integration_label = _opt("HUBSPOT_STAGE_INTEGRATION_LABEL", "Integration")
        pipeline_label_hint = _opt("HUBSPOT_PIPELINE_LABEL", "")
        anthropic_api_key = _opt("ANTHROPIC_API_KEY", "")
        slack_webhook_url = _opt("SLACK_WEBHOOK_URL", "")
        slack_bot_token = _opt("SLACK_BOT_TOKEN", "")
        slack_channel_id = _opt("SLACK_CHANNEL_ID", "")
        slack_dm_channel_id = _opt("SLACK_DM_CHANNEL_ID", "")
        anthropic_model = _opt("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        hubspot_api_base = _opt("HUBSPOT_API_BASE", "https://api.hubapi.com").rstrip("/")
        date_entered_form_property_override = _opt("HUBSPOT_DATE_ENTERED_FORM_SIGNED_PROP", "")
        date_entered_integration_property_override = _opt(
            "HUBSPOT_DATE_ENTERED_INTEGRATION_PROP", ""
        )
        hubspot_crm_view_id = _opt("HUBSPOT_CRM_VIEW_ID", "")
        hubspot_dealstage_ids = _parse_dealstage_ids(_opt("HUBSPOT_DEALSTAGE_IDS", ""))
        extra_raw = _opt("HUBSPOT_EXTRA_FILTERS_JSON", "")
        try:
            hubspot_extra_filters = _parse_extra_filters_json(extra_raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid HUBSPOT_EXTRA_FILTERS_JSON: {e}") from e
        funnel = _opt("HUBSPOT_FUNNEL_START_DATE", "form_signed").lower()
        if funnel not in ("form_signed", "created"):
            raise ValueError(
                "HUBSPOT_FUNNEL_START_DATE must be 'form_signed' or 'created' "
                "(start of the span to Integration for completed deals)."
            )
        hubspot_funnel_start = funnel
        scope = _opt("HUBSPOT_DEAL_SCOPE", "stages_in_list").lower()
        if scope not in ("form_signed_column", "stages_in_list", "entire_pipeline"):
            raise ValueError(
                "HUBSPOT_DEAL_SCOPE must be one of: form_signed_column, stages_in_list, entire_pipeline"
            )
        hubspot_deal_scope = scope
        hubspot_require_p2p_partner = _truthy_env(_opt("HUBSPOT_REQUIRE_P2P_PARTNER", ""))
        hubspot_p2p_partner_filter_values = _parse_csv_trimmed(
            _opt("HUBSPOT_P2P_PARTNER_VALUES", "")
        )

        return cls(
            hubspot_token=hubspot_token,
            anthropic_api_key=anthropic_api_key,
            slack_webhook_url=slack_webhook_url,
            slack_bot_token=slack_bot_token,
            slack_channel_id=slack_channel_id,
            slack_dm_channel_id=slack_dm_channel_id,
            demand_partner_property=demand_partner_property,
            pipeline_id=pipeline_id,
            stage_form_signed_id=stage_form_signed_id,
            stage_integration_id=stage_integration_id,
            stage_form_signed_label=stage_form_signed_label,
            stage_integration_label=stage_integration_label,
            pipeline_label_hint=pipeline_label_hint,
            anthropic_model=anthropic_model,
            hubspot_api_base=hubspot_api_base,
            date_entered_form_property_override=date_entered_form_property_override,
            date_entered_integration_property_override=date_entered_integration_property_override,
            hubspot_crm_view_id=hubspot_crm_view_id,
            hubspot_dealstage_ids=hubspot_dealstage_ids,
            hubspot_extra_filters=hubspot_extra_filters,
            hubspot_funnel_start=hubspot_funnel_start,
            hubspot_deal_scope=hubspot_deal_scope,
            hubspot_require_p2p_partner=hubspot_require_p2p_partner,
            hubspot_p2p_partner_filter_values=hubspot_p2p_partner_filter_values,
        )

    def date_entered_form_prop(self, stage_id: str) -> str:
        if self.date_entered_form_property_override:
            return self.date_entered_form_property_override
        return f"hs_date_entered_{stage_id}"

    def date_entered_integration_prop(self, stage_id: str) -> str:
        if self.date_entered_integration_property_override:
            return self.date_entered_integration_property_override
        return f"hs_date_entered_{stage_id}"
