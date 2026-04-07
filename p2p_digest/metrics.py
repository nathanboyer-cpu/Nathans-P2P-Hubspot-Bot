from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

CANONICAL_PARTNERS: tuple[str, ...] = (
    "Anzu",
    "Appstock",
    "Adspin/Mini mob",
    "Bidease",
    "Boldwin",
    "Brave",
    "Criteo",
    "Iion",
    "Illumin",
    "Index Exchange",
    "Limpid",
    "Magnite",
    "Media Net",
    "Nexxen",
    "Perion",
    "Pubmatic",
    "Se7en",
    "Sovrn",
    "Thunder Monetize",
    "Triplelift",
    "Yieldmo",
)

# HubSpot `p2p_partner` enumeration *stored values* (API) -> report bucket (see Settings → Properties)
HUBSPOT_P2P_STORED_VALUE_TO_CANONICAL: dict[str, str] = {
    "appstock": "Appstock",
    "boldwin": "Boldwin",
    "brave": "Brave",
    "criteo": "Criteo",
    "iion": "Iion",
    "illumin": "Illumin",
    "index": "Index Exchange",
    "limpid": "Limpid",
    "magnite": "Magnite",
    "media.net": "Media Net",
    "minimob/adspin": "Adspin/Mini mob",
    "nexxen": "Nexxen",
    "pubmatic": "Pubmatic",
    "se7en": "Se7en",
    "sovrn": "Sovrn",
    "thunder monetize": "Thunder Monetize",
    "triplelift": "Triplelift",
}


def _parse_hubspot_time(value: Any) -> datetime | None:
    """HubSpot search often returns dates as ISO8601 strings; batch/read may use epoch ms."""
    if value is None or value == "":
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        ms = int(float(s))
        if ms <= 0:
            return None
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        iso = s.replace("Z", "+00:00") if s.endswith("Z") else s
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _stage_entered_time(
    props: dict[str, Any],
    stage_id: str,
    date_entered_prop: str,
) -> datetime | None:
    """Prefer HubSpot v2 stage-entry timestamps (many portals only populate these)."""
    t = _parse_hubspot_time(props.get(f"hs_v2_date_entered_{stage_id}"))
    if t is not None:
        return t
    return _parse_hubspot_time(props.get(date_entered_prop))


def _days_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    if end < start:
        return None
    return (end - start).total_seconds() / 86400.0


def normalize_partner(raw: str | None) -> str:
    if raw is None:
        return "Other / blank"
    s = str(raw).strip()
    if not s:
        return "Other / blank"
    low = s.lower()
    if low in HUBSPOT_P2P_STORED_VALUE_TO_CANONICAL:
        return HUBSPOT_P2P_STORED_VALUE_TO_CANONICAL[low]
    for p in CANONICAL_PARTNERS:
        if p.lower() == low:
            return p
    return f"Other ({s})" if s else "Other / blank"


@dataclass
class PartnerBucket:
    deal_count: int = 0
    completed_form_to_integration_days: list[float] = field(default_factory=list)
    created_to_now_days: list[float] = field(default_factory=list)


@dataclass
class DigestMetrics:
    generated_at_utc: str
    pipeline_id: str
    form_stage_id: str
    integration_stage_id: str
    demand_partner_property: str
    hubspot_crm_view_id: str
    dealstage_filter_ids: tuple[str, ...]
    total_deals_in_pipeline: int
    deals_reached_form_signed: int
    deals_reached_integration: int
    overall_avg_days_created_to_now: float | None
    overall_median_days_created_to_now: float | None
    overall_avg_days_form_signed_to_integration_completed: float | None
    overall_median_days_form_signed_to_integration_completed: float | None
    by_partner: dict[str, dict[str, Any]]
    nexxen: dict[str, Any]
    non_nexxen: dict[str, Any]
    funnel_start_mode: str
    deal_lines_by_partner: dict[str, list[dict[str, Any]]]
    carry_usd_per_day: float


def _bucket_summary(b: PartnerBucket) -> dict[str, Any]:
    def avg_med(vals: list[float]) -> tuple[float | None, float | None]:
        if not vals:
            return None, None
        return statistics.mean(vals), statistics.median(vals)

    a_c, m_c = avg_med(b.created_to_now_days)
    a_fi, m_fi = avg_med(b.completed_form_to_integration_days)
    return {
        "deal_count": b.deal_count,
        "avg_days_created_to_now": a_c,
        "median_days_created_to_now": m_c,
        "avg_days_form_signed_to_integration": a_fi,
        "median_days_form_signed_to_integration": m_fi,
        "completed_form_to_integration_count": len(b.completed_form_to_integration_days),
    }


def compute_metrics(
    deals: list[dict[str, Any]],
    pipeline_id: str,
    form_stage_id: str,
    integration_stage_id: str,
    demand_partner_property: str,
    date_entered_form_prop: str,
    date_entered_integration_prop: str,
    *,
    hubspot_crm_view_id: str = "",
    dealstage_filter_ids: tuple[str, ...] = (),
    funnel_start_mode: str = "form_signed",
    carry_usd_per_day: float = 1000.0,
    include_form_signed_deal_breakdown: bool = False,
) -> DigestMetrics:
    now = datetime.now(timezone.utc)
    deal_lines_by_partner: dict[str, list[dict[str, Any]]] = defaultdict(list)

    buckets: dict[str, PartnerBucket] = {
        **{p: PartnerBucket() for p in CANONICAL_PARTNERS},
        "Other / blank": PartnerBucket(),
    }
    nexxen_b = PartnerBucket()
    non_nexxen_b = PartnerBucket()

    all_created_to_now: list[float] = []
    all_form_to_int_completed: list[float] = []

    reached_form = 0
    reached_int = 0

    for d in deals:
        props = d.get("properties") or {}
        created = _parse_hubspot_time(props.get("createdate"))
        if created is None:
            created = _parse_hubspot_time(props.get("hs_createdate"))
        t_form = _stage_entered_time(props, form_stage_id, date_entered_form_prop)
        t_int = _stage_entered_time(props, integration_stage_id, date_entered_integration_prop)

        partner_raw = props.get(demand_partner_property)
        partner = normalize_partner(partner_raw)
        if partner not in buckets:
            buckets[partner] = PartnerBucket()
        b = buckets[partner]
        b.deal_count += 1

        if created:
            dcn = _days_between(created, now)
            if dcn is not None:
                b.created_to_now_days.append(dcn)
                all_created_to_now.append(dcn)
                (nexxen_b if partner == "Nexxen" else non_nexxen_b).created_to_now_days.append(
                    dcn
                )

        if t_form is not None:
            reached_form += 1

        if t_int is not None:
            reached_int += 1

        t_funnel_start = created if funnel_start_mode == "created" else t_form
        if t_funnel_start is not None and t_int is not None:
            span = _days_between(t_funnel_start, t_int)
            if span is not None:
                b.completed_form_to_integration_days.append(span)
                all_form_to_int_completed.append(span)
                target = nexxen_b if partner == "Nexxen" else non_nexxen_b
                target.completed_form_to_integration_days.append(span)

        (nexxen_b if partner == "Nexxen" else non_nexxen_b).deal_count += 1

        if include_form_signed_deal_breakdown:
            ref = t_form if t_form is not None else created
            ref_label = "Form signed entered" if t_form is not None else "Deal created (fallback)"
            if ref is not None:
                days_in = _days_between(ref, now)
                if days_in is not None:
                    carry = int(round(days_in * carry_usd_per_day))
                    deal_lines_by_partner[partner].append(
                        {
                            "deal_id": str(d.get("id", "") or ""),
                            "dealname": str(props.get("dealname") or "Untitled deal"),
                            "reference_date_utc": ref.date().isoformat(),
                            "reference_label": ref_label,
                            "days_in_form_signed": round(days_in, 1),
                            "carry_estimate_usd": carry,
                        }
                    )

    def overall_avg_med(vals: list[float]) -> tuple[float | None, float | None]:
        if not vals:
            return None, None
        return statistics.mean(vals), statistics.median(vals)

    oa_c, om_c = overall_avg_med(all_created_to_now)
    oa_fi, om_fi = overall_avg_med(all_form_to_int_completed)

    by_partner: dict[str, dict[str, Any]] = {}
    for name in CANONICAL_PARTNERS:
        by_partner[name] = _bucket_summary(buckets[name])
    by_partner["Other / blank"] = _bucket_summary(buckets["Other / blank"])
    for k, v in sorted(buckets.items()):
        if k in by_partner:
            continue
        by_partner[k] = _bucket_summary(v)

    lines_sorted: dict[str, list[dict[str, Any]]] = {}
    if include_form_signed_deal_breakdown:
        for pname, rows in deal_lines_by_partner.items():
            if not rows:
                continue
            lines_sorted[pname] = sorted(
                rows, key=lambda r: (-float(r["days_in_form_signed"]), r["dealname"])
            )

    return DigestMetrics(
        generated_at_utc=now.isoformat(),
        pipeline_id=pipeline_id,
        form_stage_id=form_stage_id,
        integration_stage_id=integration_stage_id,
        demand_partner_property=demand_partner_property,
        hubspot_crm_view_id=hubspot_crm_view_id,
        dealstage_filter_ids=dealstage_filter_ids,
        total_deals_in_pipeline=len(deals),
        deals_reached_form_signed=reached_form,
        deals_reached_integration=reached_int,
        overall_avg_days_created_to_now=oa_c,
        overall_median_days_created_to_now=om_c,
        overall_avg_days_form_signed_to_integration_completed=oa_fi,
        overall_median_days_form_signed_to_integration_completed=om_fi,
        by_partner=by_partner,
        nexxen=_bucket_summary(nexxen_b),
        non_nexxen=_bucket_summary(non_nexxen_b),
        funnel_start_mode=funnel_start_mode,
        deal_lines_by_partner=lines_sorted,
        carry_usd_per_day=carry_usd_per_day,
    )


def metrics_to_dict(m: DigestMetrics) -> dict[str, Any]:
    return {
        "generated_at_utc": m.generated_at_utc,
        "pipeline_id": m.pipeline_id,
        "form_stage_id": m.form_stage_id,
        "integration_stage_id": m.integration_stage_id,
        "demand_partner_property": m.demand_partner_property,
        "hubspot_crm_view_id": m.hubspot_crm_view_id,
        "dealstage_filter_ids": list(m.dealstage_filter_ids),
        "funnel_start_mode": m.funnel_start_mode,
        "total_deals_in_pipeline": m.total_deals_in_pipeline,
        "deals_reached_form_signed": m.deals_reached_form_signed,
        "deals_reached_integration": m.deals_reached_integration,
        "overall": {
            "avg_days_created_to_now": m.overall_avg_days_created_to_now,
            "median_days_created_to_now": m.overall_median_days_created_to_now,
            "avg_days_form_signed_to_integration_completed": m.overall_avg_days_form_signed_to_integration_completed,
            "median_days_form_signed_to_integration_completed": m.overall_median_days_form_signed_to_integration_completed,
        },
        "by_partner": m.by_partner,
        "nexxen_bucket": m.nexxen,
        "non_nexxen_bucket": m.non_nexxen,
        "deal_lines_by_partner": m.deal_lines_by_partner,
        "carry_usd_per_day": m.carry_usd_per_day,
    }
