from __future__ import annotations

from typing import Any


def _fmt_num(x: Any) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.1f}"
    return str(x)


def build_slack_message(summary: str | None, metrics: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("*P2P HubSpot digest*")
    lines.append(f"_As of {metrics.get('generated_at_utc', '')} (UTC)_")
    lines.append("")
    if summary:
        lines.append(summary.strip())
        lines.append("")
    ov = metrics.get("overall") or {}
    lines.append("*Snapshot*")
    lines.append(
        f"• Deals in pipeline: {metrics.get('total_deals_in_pipeline', 0)} "
        f"| Reached Form signed: {metrics.get('deals_reached_form_signed', 0)} "
        f"| Reached Integration: {metrics.get('deals_reached_integration', 0)}"
    )
    lines.append(
        f"• Avg days (created→now): {_fmt_num(ov.get('avg_days_created_to_now'))} "
        f"(median {_fmt_num(ov.get('median_days_created_to_now'))})"
    )
    lines.append(
        f"• Avg days (Form signed→Integration, completed): "
        f"{_fmt_num(ov.get('avg_days_form_signed_to_integration_completed'))} "
        f"(median {_fmt_num(ov.get('median_days_form_signed_to_integration_completed'))})"
    )
    nx = metrics.get("nexxen_bucket") or {}
    nn = metrics.get("non_nexxen_bucket") or {}
    lines.append("")
    lines.append("*Nexxen vs non-Nexxen*")
    lines.append(
        f"• Nexxen: {nx.get('deal_count', 0)} deals | "
        f"avg form→integration {_fmt_num(nx.get('avg_days_form_signed_to_integration'))} d "
        f"({nx.get('completed_form_to_integration_count', 0)} completed)"
    )
    lines.append(
        f"• Non-Nexxen: {nn.get('deal_count', 0)} deals | "
        f"avg form→integration {_fmt_num(nn.get('avg_days_form_signed_to_integration'))} d "
        f"({nn.get('completed_form_to_integration_count', 0)} completed)"
    )
    lines.append("")
    lines.append("*Avg days Form signed→Integration by Demand Partner* (completed deals only)")
    by_p = metrics.get("by_partner") or {}
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
    return "\n".join(lines)
