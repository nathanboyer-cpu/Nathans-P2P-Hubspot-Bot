from __future__ import annotations

from typing import Any

import httpx

from p2p_digest.config import Settings


class HubSpotClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._headers = {
            "Authorization": f"Bearer {settings.hubspot_token}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._settings.hubspot_api_base}{path}"

    def get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        with httpx.Client(timeout=60.0) as client:
            r = client.get(self._url(path), headers=self._headers, params=params)
            r.raise_for_status()
            return r.json()

    def post_json(self, path: str, body: dict[str, Any]) -> Any:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(self._url(path), headers=self._headers, json=body)
            r.raise_for_status()
            return r.json()

    def list_deal_pipelines(self) -> list[dict[str, Any]]:
        data = self.get_json("/crm/v3/pipelines/deals")
        return list(data.get("results", []))

    def resolve_pipeline_id(self) -> str:
        if self._settings.pipeline_id:
            return self._settings.pipeline_id
        hint = (self._settings.pipeline_label_hint or "").strip().lower()
        if not hint:
            raise ValueError(
                "Set HUBSPOT_PIPELINE_ID or HUBSPOT_PIPELINE_LABEL to select a deal pipeline."
            )
        for p in self.list_deal_pipelines():
            label = str(p.get("label", "")).strip().lower()
            pid = str(p.get("id", ""))
            if label == hint or hint in label or label in hint:
                return pid
        raise ValueError(f"No deal pipeline matched HUBSPOT_PIPELINE_LABEL={hint!r}")

    def resolve_stage_id(self, pipeline_id: str, label: str, explicit_id: str) -> str:
        if explicit_id:
            return explicit_id
        want = label.strip().lower()
        for p in self.list_deal_pipelines():
            if str(p.get("id")) != str(pipeline_id):
                continue
            for s in p.get("stages", []) or []:
                sl = str(s.get("label", "")).strip().lower()
                if sl == want or want in sl or sl in want:
                    return str(s.get("id"))
        raise ValueError(
            f"Could not resolve stage id for label {label!r} in pipeline {pipeline_id}. "
            "Set HUBSPOT_STAGE_FORM_SIGNED_ID and HUBSPOT_STAGE_INTEGRATION_ID."
        )

    def search_deals_in_pipeline(
        self,
        pipeline_id: str,
        properties: list[str],
        *,
        dealstage_ids: tuple[str, ...] = (),
        dealstage_eq: str | None = None,
        extra_filters: list[dict[str, object]] | None = None,
    ) -> list[dict[str, Any]]:
        """Paginated CRM search for deals in a pipeline (optional stage scope)."""
        filters: list[dict[str, object]] = [
            {
                "propertyName": "pipeline",
                "operator": "EQ",
                "value": pipeline_id,
            }
        ]
        if dealstage_eq:
            filters.append(
                {
                    "propertyName": "dealstage",
                    "operator": "EQ",
                    "value": dealstage_eq,
                }
            )
        elif dealstage_ids:
            filters.append(
                {
                    "propertyName": "dealstage",
                    "operator": "IN",
                    "values": list(dealstage_ids),
                }
            )
        if extra_filters:
            filters.extend(extra_filters)
        out: list[dict[str, Any]] = []
        after: str | None = None
        while True:
            body: dict[str, Any] = {
                "filterGroups": [{"filters": filters}],
                "properties": properties,
                "limit": 100,
            }
            if after:
                body["after"] = after
            data = self.post_json("/crm/v3/objects/deals/search", body)
            for row in data.get("results", []):
                out.append(row)
            paging = data.get("paging", {}) or {}
            next_after = (paging.get("next", {}) or {}).get("after")
            if not next_after:
                break
            after = str(next_after)
        return out


def resolved_pipeline_and_stages(settings: Settings) -> tuple[str, str, str]:
    client = HubSpotClient(settings)
    pipeline_id = client.resolve_pipeline_id()
    form_id = client.resolve_stage_id(
        pipeline_id, settings.stage_form_signed_label, settings.stage_form_signed_id
    )
    integ_id = client.resolve_stage_id(
        pipeline_id, settings.stage_integration_label, settings.stage_integration_id
    )
    return pipeline_id, form_id, integ_id


def deal_properties_for_run(settings: Settings, form_stage_id: str, integ_stage_id: str) -> list[str]:
    props = {
        "dealname",
        "dealstage",
        "pipeline",
        "createdate",
        "hs_createdate",
        "closedate",
        "hs_is_closed",
        settings.demand_partner_property,
        settings.date_entered_form_prop(form_stage_id),
        settings.date_entered_integration_prop(integ_stage_id),
        f"hs_v2_date_entered_{form_stage_id}",
        f"hs_v2_date_entered_{integ_stage_id}",
    }
    return sorted(props)
