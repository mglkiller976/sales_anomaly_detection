"""Markdown report for a run."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .detect import fmt_mnt


def build_report(res) -> str:
    s = res.summary; a = res.anomalies
    L = ["# Sales anomaly report", "",
         f"Engine `{s['engine']}` · generated {s['generated_at'][:16]} · data {s['data']['date_min']}..{s['data']['date_max']} "
         f"({s['data']['days']} trading days, {s['data']['rows']:,} rows, {fmt_mnt(s['data']['amount_total'])} MNT) · "
         f"sensitivity **{s['config']['sensitivity']}**, calendar **{s['config']['calendar_preset']}**"
         + (", auto-discovered recurring days" if s['config']['auto_events'] else "") + f" · {s['elapsed_seconds']}s", ""]
    L += ["## Headline numbers", "",
          f"* {s['counts']['total']} records — " + ", ".join(f"{k}: {v}" for k, v in s["counts"]["by_severity"].items()),
          "* by type: " + ", ".join(f"{k}: {v}" for k, v in s["counts"]["by_type"].items()),
          "* by level: " + ", ".join(f"{k}: {v}" for k, v in s["counts"]["by_level"].items()),
          "* effective |z| thresholds (self-calibrated): " + ", ".join(f"{k} {v}{' (capped)' if s.get('thresholds_clipped', {}).get(k) else ''}" for k, v in s["thresholds"].items()),
          "* series scored / existing: " + ", ".join(f"{k} {v}/{s['data'].get('series_universe', {}).get(k, v)}" for k, v in s["data"]["series_scored"].items()), ""]
    L += ["## Top 40 by priority", "", "| # | date | level | entity | type | sev | scope | actual | expected | ratio | z | reason |", "|---|---|---|---|---|---|---|---:|---:|---:|---:|---|"]
    top = a[~a["type"].isin(["item_launch", "item_discontinued"])].head(40)
    for i, r in enumerate(top.itertuples(), 1):
        L.append(f"| {i} | {r.date}{'→' + str(r.end_date) if r.end_date else ''} | {r.level} | {r.entity_name} | {r.type} | {r.severity} | {r.scope or ''} | "
                 f"{fmt_mnt(r.actual)} | {fmt_mnt(r.expected)} | {r.ratio:.2f} | {r.z:+.1f} | {str(r.reason).replace('|', '/')} |"
                 if pd.notna(r.z) and pd.notna(r.ratio) else
                 f"| {i} | {r.date}{'→' + str(r.end_date) if r.end_date else ''} | {r.level} | {r.entity_name} | {r.type} | {r.severity} | {r.scope or ''} | "
                 f"{fmt_mnt(r.actual)} | {fmt_mnt(r.expected)} |  |  | {str(r.reason).replace('|', '/')} |")
    L += ["", "## Company-wide / systemic events", ""]
    sys_ = a[a["type"].isin(["systemic_event"])]
    L += ["none"] if sys_.empty else [f"* **{r.date}** ({r.direction}, {r.n_children} branches): {r.reason}" for r in sys_.itertuples()]
    L += ["", "## Company closures that are NOT known holidays", ""]
    cc = a[(a["type"] == "company_closure") & (a["severity"] == "critical")]
    L += ["none"] if cc.empty else [f"* {r.date}: {r.reason}" for r in cc.itertuples()]
    L += ["", "## Learned calendar effects (company total, multiplier vs. a normal day)", "", "| event day | multiplier | years |", "|---|---:|---:|"]
    g = res.calendar_effects[res.calendar_effects["level"] == "global"].sort_values("tag") if len(res.calendar_effects) else pd.DataFrame()
    for r in g.itertuples():
        L.append(f"| {r.tag} | {r.multiplier:.2f}× | {r.years_observed} |")
    if len(res.auto_events):
        L += ["", "Recurring days discovered from the data (not in the preset calendar): " +
              ", ".join(f"{r.month_day} ({r.multiplier:.2f}×, {r.years} yrs)" for r in res.auto_events.itertuples())]
    L += ["", "## Coverage", "",
          "Share of each branch's trading days that could be scored: " +
          ", ".join(f"{k} {v:.0%}" for k, v in sorted(s["coverage"]["share_of_active_days_scorable"].get("branch", {}).items())),
          "", "Series below 50 % coverage (treat their silence as *not checked*): " + (", ".join(s["coverage"]["below_50pct"]) or "none")]
    L += ["", "## Data-quality flags", ""]
    dq = a[a["type"].isin(["repeated_day"]) | a["reason"].str.contains("data-entry", na=False)]
    L += ["none"] if dq.empty else [f"* {r.date} · {r.entity_name} · {r.type}: {r.reason}" for r in dq.head(30).itertuples()]
    L += ["", "## Method (short)", "",
          "Each daily series (company, branch, category, branch×category, item, branch×item) is modelled on log1p(AMOUNT) of its trading days as "
          "local level (leave-one-out median of ±14 surrounding non-event days, widened automatically for sparse series) + weekday + day-of-month "
          "+ calendar-event effect (built-in holiday preset + your custom events + recurring days discovered from the data; each effect learned "
          "leave-one-year-out with the parent series as fallback). Residuals are scaled by a rolling MAD that cannot collapse. Alert thresholds "
          "are self-calibrated per level to a target alert rate (sensitivity). Each point anomaly is split into local vs company-wide (peer-adjusted z). "
          "Zero days are judged against a leave-one-out open probability; level changes come from robust binary segmentation of the weekly, "
          "calendar- and season-adjusted series; branch alerts co-occurring company-wide roll up into one systemic record and lower-level echoes are demoted."]
    return "\n".join(L) + "\n"


def write_report(res, out_dir: Path) -> None:
    (Path(out_dir) / "report.md").write_text(build_report(res), encoding="utf-8")
