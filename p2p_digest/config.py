from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise ValueError(f"Missing required environment variable: {name}")
    return v


def _opt(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    hubspot_token: str
    anthropic_api_key: str
    slack_webhook_url: str
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

    @classmethod
    def load(cls) -> Settings:
        hubspot_token = _req("HUBSPOT_ACCESS_TOKEN")
        demand_partner_property = _opt("HUBSPOT_DEMAND_PARTNER_PROPERTY", "demand_partner")
        pipeline_id = _opt("HUBSPOT_PIPELINE_ID", "")
        stage_form_signed_id = _opt("HUBSPOT_STAGE_FORM_SIGNED_ID", "")
        stage_integration_id = _opt("HUBSPOT_STAGE_INTEGRATION_ID", "")
        stage_form_signed_label = _opt("HUBSPOT_STAGE_FORM_SIGNED_LABEL", "Form signed")
        stage_integration_label = _opt("HUBSPOT_STAGE_INTEGRATION_LABEL", "Integration")
        pipeline_label_hint = _opt("HUBSPOT_PIPELINE_LABEL", "")
        anthropic_api_key = _opt("ANTHROPIC_API_KEY", "")
        slack_webhook_url = _opt("SLACK_WEBHOOK_URL", "")
        anthropic_model = _opt("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        hubspot_api_base = _opt("HUBSPOT_API_BASE", "https://api.hubapi.com").rstrip("/")
        date_entered_form_property_override = _opt("HUBSPOT_DATE_ENTERED_FORM_SIGNED_PROP", "")
        date_entered_integration_property_override = _opt(
            "HUBSPOT_DATE_ENTERED_INTEGRATION_PROP", ""
        )

        return cls(
            hubspot_token=hubspot_token,
            anthropic_api_key=anthropic_api_key,
            slack_webhook_url=slack_webhook_url,
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
        )

    def date_entered_form_prop(self, stage_id: str) -> str:
        if self.date_entered_form_property_override:
            return self.date_entered_form_property_override
        return f"hs_date_entered_{stage_id}"

    def date_entered_integration_prop(self, stage_id: str) -> str:
        if self.date_entered_integration_property_override:
            return self.date_entered_integration_property_override
        return f"hs_date_entered_{stage_id}"
