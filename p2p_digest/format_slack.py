from __future__ import annotations

from typing import Any


def _slack_plain(text: str, max_len: int = 100) -> str:
    s = str(text).replace("&", "and").replace("<", "").replace(">", "")
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def _fmt_usd(n: int) -> str:
    return f"${n:,}"


def _fmt_num(x: Any) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.1f}"
    return str(x)


def _funnel_span_label(metrics: dict[str, Any]) -> str:
    mode = (metrics.get("funnel_start_mode") or "form_signed").lower()
    if mode == "created":
        return "Deal created→Integration"
    return "Form signed→Integration"


def build_slack_message(summary: str | None, metrics: dict[str, Any]) -> str:
    lines: list[str] = []
    span_lbl = _funnel_span_label(metrics)
    lines.append("*P2P HubSpot digest*")
    lines.append(f"_As of {metrics.get('generated_at_utc', '')} (UTC)_")
    view_id = metrics.get("hubspot_crm_view_id") or ""
    stage_ids = metrics.get("dealstage_filter_ids") or []
    deal_scope = (metrics.get("deal_scope_mode") or "").lower()
    if deal_scope == "form_signed_column":
        lines.append(
            "_Scope: deals whose **current stage** is **Form signed** (that board column only)._"
        )
    elif view_id:
        lines.append(
            f"_Board/view id `{view_id}` — HubSpot has no public “query by view” API; "
            f"deals use pipeline + dealstage IN ({len(stage_ids)} stage ids)._"
        )
    elif stage_ids:
        lines.append(
            f"_Deal scope: `dealstage` IN {len(stage_ids)} configured stage ids (see `.env`)._"
        )
    lines.append("")
    if summary:
        lines.append(summary.strip())
        lines.append("")
    ov = metrics.get("overall") or {}
    lines.append("*Snapshot*")
    lines.append(
        f"• Deals in scope: {metrics.get('total_deals_in_pipeline', 0)} "
        f"| Reached Form signed: {metrics.get('deals_reached_form_signed', 0)} "
        f"| Reached Integration: {metrics.get('deals_reached_integration', 0)}"
    )
    lines.append(
        f"• Avg days (created→now): {_fmt_num(ov.get('avg_days_created_to_now'))} "
        f"(median {_fmt_num(ov.get('median_days_created_to_now'))})"
    )
    lines.append(
        f"• Avg days ({span_lbl}, completed): "
        f"{_fmt_num(ov.get('avg_days_form_signed_to_integration_completed'))} "
        f"(median {_fmt_num(ov.get('median_days_form_signed_to_integration_completed'))})"
    )
    nx = metrics.get("nexxen_bucket") or {}
    nn = metrics.get("non_nexxen_bucket") or {}
    lines.append("")
    lines.append("*Nexxen vs non-Nexxen*")
    lines.append(
        f"• Nexxen: {nx.get('deal_count', 0)} deals | "
        f"avg days ({span_lbl}): {_fmt_num(nx.get('avg_days_form_signed_to_integration'))} d "
        f"({nx.get('completed_form_to_integration_count', 0)} completed)"
    )
    lines.append(
        f"• Non-Nexxen: {nn.get('deal_count', 0)} deals | "
        f"avg days ({span_lbl}): {_fmt_num(nn.get('avg_days_form_signed_to_integration'))} d "
        f"({nn.get('completed_form_to_integration_count', 0)} completed)"
    )
    lines.append("")
    by_p = metrics.get("by_partner") or {}
    deal_lines = metrics.get("deal_lines_by_partner") or {}
    rate = float(metrics.get("carry_usd_per_day") or 1000)
    if deal_scope == "form_signed_column":
        lines.append("*By P2P Partner* (deals currently in Form signed)")
        lines.append(
            f"_Per deal: reference date = Form signed entered when HubSpot has it, else deal created. "
            f"Days = time in this column (now − reference). Est. carry = days × {_fmt_usd(int(rate))}/day._"
        )
        prow: list[tuple[str, int, str]] = []
        for name, b in by_p.items():
            if not isinstance(b, dict):
                continue
            n = int(b.get("deal_count") or 0)
            if n == 0:
                continue
            prow.append(
                (name, n, _fmt_num(b.get("avg_days_created_to_now")))
            )
        prow.sort(key=lambda t: (-t[1], t[0]))
        for name, n, avg_c in prow[:40]:
            lines.append(f"• *{_slack_plain(name, 80)}* — {n} deals | avg days created→now {avg_c}")
            rows = deal_lines.get(name) if isinstance(deal_lines, dict) else None
            if isinstance(rows, list) and rows:
                sub = sum(int(r.get("carry_estimate_usd") or 0) for r in rows)
                for r in rows:
                    if not isinstance(r, dict):
                        continue
                    dn = _slack_plain(str(r.get("dealname") or ""), 90)
                    dref = r.get("reference_date_utc") or "n/a"
                    dlbl = str(r.get("reference_label") or "")
                    dd = r.get("days_in_form_signed")
                    dc = int(r.get("carry_estimate_usd") or 0)
                    lines.append(
                        f"    ◦ `{dn}` — {dref} ({dlbl}) | {dd} d in column | est. {_fmt_usd(dc)}"
                    )
                lines.append(f"    _Partner subtotal (est. carry): {_fmt_usd(sub)}_")
        if isinstance(deal_lines, dict):
            grand = sum(
                int(r.get("carry_estimate_usd") or 0)
                for rows in deal_lines.values()
                if isinstance(rows, list)
                for r in rows
                if isinstance(r, dict)
            )
            if grand:
                lines.append(f"*Total est. carry (Form signed, all listed deals):* {_fmt_usd(grand)}")
        lines.append("")
    lines.append(f"*Avg days {span_lbl} by P2P Partner* (completed deals only)")
    rows: list[tuple[str, int, str]] = []
    for name, b in by_p.items():
        if not isinstance(b, dict):
            continue
        n = int(b.get("completed_form_to_integration_count") or 0)
        if n == 0:
            continue
        rows.append((name, n, _fmt_num(b.get("avg_days_form_signed_to_integration"))))
    rows.sort(key=lambda t: (-t[1], t[0]))
    for name, n, avg in rows[:40]:
        lines.append(f"• {name}: {avg} d (n={n})")
    if deal_scope == "form_signed_column" and not rows:
        lines.append("_No deals in this batch have reached Integration yet (expected while scoped to Form signed)._")
    return "\n".join(lines)
