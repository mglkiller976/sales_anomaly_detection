"""Sales Anomaly Studio — Streamlit app around the detection engine.

Run:  streamlit run app.py   (or double-click run.bat / run.sh)
"""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))
from engine import RunConfig, describe_input, load_input, load_names, load_run, run as run_engine, save_run  # noqa: E402
from engine.calendar import PRESETS  # noqa: E402
from engine.model import LEVEL_LABEL  # noqa: E402

RUNS_DIR = APP_DIR / "runs"
DATA_DIR = APP_DIR / "data"
RUNS_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Sales Anomaly Studio", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

SEV_COLOR = {"critical": "#b91c1c", "high": "#d97706", "medium": "#2563eb", "low": "#6b7280", "info": "#9ca3af"}
SEV_ORDER = ["critical", "high", "medium", "low", "info"]
TYPE_LABEL = {"point_spike": "Spike", "point_drop": "Drop", "unexpected_zero": "Unexpected zero / closure", "level_shift": "Level change",
              "systemic_event": "Company-wide event", "company_closure": "Company closure", "data_gap": "Data gap", "repeated_day": "Repeated day",
              "unusual_mix": "Unusual category mix", "item_launch": "Item launch", "item_discontinued": "Item discontinued",
              "long_silence": "Long silence (branch dark)", "activity_shift": "Trading-frequency change"}


# ------------------------------------------------------------------------------- helpers
def fmt(v, digits=1) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:,.2f} B"
    if a >= 1e6:
        return f"{v / 1e6:,.{digits}f} M"
    if a >= 1e3:
        return f"{v / 1e3:,.0f} k"
    return f"{v:,.0f}"


def list_runs() -> list[dict]:
    out = []
    if not RUNS_DIR.exists():
        return out
    for p in sorted(RUNS_DIR.iterdir()):
        if (p / "meta.json").exists():
            try:
                m = json.loads((p / "meta.json").read_text(encoding="utf-8"))
                out.append({"dir": p, "name": m.get("name", p.name), "generated": m.get("generated_at", ""), "meta": m})
            except Exception:
                pass
    return sorted(out, key=lambda r: r["generated"], reverse=True)


def dir_size_mb(p: Path) -> float:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6


def rename_run(run_dir: Path, new_name: str) -> None:
    f = run_dir / "meta.json"
    m = json.loads(f.read_text(encoding="utf-8"))
    m["name"] = new_name.strip() or run_dir.name
    f.write_text(json.dumps(m, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def pick_file_dialog() -> str:
    """Native Windows 'choose file' dialog (the app runs on the user's own machine)."""
    ps = ("Add-Type -AssemblyName System.Windows.Forms; "
          "$d = New-Object System.Windows.Forms.OpenFileDialog; "
          "$d.Title = 'Choose a sales data file'; "
          "$d.Filter = 'Sales data (*.csv;*.gz;*.parquet)|*.csv;*.csv.gz;*.gz;*.parquet|All files (*.*)|*.*'; "
          "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $d.FileName }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True, timeout=600)
        return r.stdout.strip()
    except Exception:
        return ""


@st.cache_resource(show_spinner=False)
def get_run(run_dir: str, mtime: float):
    return load_run(Path(run_dir))


def current_run():
    runs = list_runs()
    if not runs:
        return None
    key = st.session_state.get("run_dir")
    chosen = next((r for r in runs if str(r["dir"]) == key), runs[0])
    st.session_state["run_dir"] = str(chosen["dir"])
    return get_run(str(chosen["dir"]), (chosen["dir"] / "meta.json").stat().st_mtime)


def anomalies_of(R, level: str, entity: str) -> pd.DataFrame:
    a = R["anomalies"]
    return a[(a["level"] == level) & (a["entity"] == entity)]


def series_figure(R, level: str, entity: str, center: pd.Timestamp | None = None, window: int = 120, logy: bool = False,
                  highlight_id: str | None = None, height: int = 380) -> go.Figure | None:
    s = R["store"].series(level, entity)
    if s is None:
        return None
    index = R["index"]; thr = float(R["meta"]["thresholds"].get(level, 4.0))
    a = s["amount"].astype(float); e = np.expm1(s["expected"].astype(float)); sg = s["sigma"].astype(float)
    life = s["lifetime"].astype(bool)
    a = np.where(life, a, np.nan)
    lo = np.expm1(s["expected"].astype(float) - thr * sg); hi = np.expm1(s["expected"].astype(float) + thr * sg)
    if center is not None and window:
        t = index.get_loc(center); i0, i1 = max(0, t - window), min(len(index), t + window + 1)
    else:
        i0, i1 = 0, len(index)
    x = index[i0:i1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.concatenate([x, x[::-1]]), y=np.concatenate([hi[i0:i1], lo[i0:i1][::-1]]), fill="toself",
                             fillcolor="rgba(37,99,235,0.12)", line=dict(width=0), hoverinfo="skip", name="expected band", showlegend=True))
    fig.add_trace(go.Scatter(x=x, y=e[i0:i1], mode="lines", line=dict(color="#2563eb", width=1.5), name="expected"))
    fig.add_trace(go.Scatter(x=x, y=a[i0:i1], mode="lines+markers", line=dict(color="#111827", width=1.3), marker=dict(size=3), name="actual",
                             hovertemplate="%{x|%Y-%m-%d}<br>actual %{y:,.0f}<extra></extra>"))
    cal = R["cal"]
    tags = cal["tag"].reindex(x).fillna("")
    ev = tags[tags != ""]
    if len(ev):
        fig.update_layout(shapes=[dict(type="line", x0=d, x1=d, xref="x", y0=0, y1=1, yref="paper",
                                       line=dict(color="rgba(120,120,120,0.25)", width=1)) for d in ev.index])
    an = anomalies_of(R, level, entity)
    an = an[an["type"].isin(["point_spike", "point_drop", "unexpected_zero", "level_shift", "systemic_event", "unusual_mix", "data_gap",
                             "long_silence", "activity_shift", "repeated_day"])]
    if len(an):
        ad = pd.to_datetime(an["date"])
        m = (ad >= x[0]) & (ad <= x[-1])
        an = an[m]; ad = ad[m]
        if len(an):
            pos = [index.get_loc(d) for d in ad]
            yv = [a[p] if np.isfinite(a[p]) else e[p] for p in pos]
            colors = [SEV_COLOR.get(sv, "#999") for sv in an["severity"]]
            sizes = [13 if hid == highlight_id else 8 for hid in an["id"]]
            fig.add_trace(go.Scatter(x=ad, y=yv, mode="markers", marker=dict(color=colors, size=sizes, line=dict(color="#fff", width=1)),
                                     name="anomalies", text=[f"{TYPE_LABEL.get(t, t)} · {sv}" for t, sv in zip(an["type"], an["severity"])],
                                     hovertemplate="%{x|%Y-%m-%d}<br>%{text}<extra></extra>"))
    if logy:
        fig.update_yaxes(type="log")
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.08, x=0),
                      hovermode="x unified", yaxis_title="MNT / day", template="plotly_white")
    return fig


def z_figure(R, level: str, entity: str, height: int = 160) -> go.Figure | None:
    s = R["store"].series(level, entity)
    if s is None:
        return None
    z = s["z"].astype(float); index = R["index"]
    fig = go.Figure(go.Bar(x=index, y=z, marker_color=np.where(z > 0, "#dc2626", "#1d4ed8"), name="z"))
    thr = float(R["meta"]["thresholds"].get(level, 4.0))
    fig.add_hline(y=thr, line=dict(color="#999", dash="dot")); fig.add_hline(y=-thr, line=dict(color="#999", dash="dot"))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white", yaxis_title="z", showlegend=False)
    return fig


def anomaly_table(df: pd.DataFrame) -> pd.DataFrame:
    t = df.copy()
    t["when"] = t["date"] + np.where(t["end_date"].fillna("") != "", " → " + t["end_date"].fillna("").str[5:], "")
    t["type"] = t["type"].map(lambda x: TYPE_LABEL.get(x, x))
    t["level"] = t["level"].map(lambda x: LEVEL_LABEL.get(x, x))
    t["actual"] = t["actual"].map(fmt); t["expected"] = t["expected"].map(fmt)
    t["ratio"] = t["ratio"].map(lambda v: "" if pd.isna(v) else f"{v:.2f}×")
    t["z"] = t["z"].map(lambda v: "" if pd.isna(v) else f"{v:+.1f}")
    t["priority"] = t["priority"].round(0).astype(int)
    t["echo"] = np.where(t["parent_id"].fillna("") != "", "echo", "")
    return t[["priority", "when", "level", "entity_name", "type", "severity", "scope", "actual", "expected", "ratio", "z", "echo", "id"]].rename(
        columns={"entity_name": "entity", "priority": "prio"})


def show_detail(R, row: pd.Series):
    level, entity = row["level"], row["entity"]
    st.markdown(f"#### {TYPE_LABEL.get(row['type'], row['type'])} · {row['entity_name']} · {row['date']}" + (f" → {row['end_date']}" if row["end_date"] else ""))
    st.markdown(f"<span style='background:{SEV_COLOR.get(row['severity'],'#999')};color:#fff;padding:2px 8px;border-radius:10px;font-size:12px'>{row['severity']}</span>"
                f"&nbsp; <span style='color:#6b7280;font-size:12px'>{LEVEL_LABEL.get(level, level)} · scope {row['scope'] or '—'} · priority {row['priority']:.0f} · id {row['id']}"
                + (f" · calendar {row['calendar_tag']}" if row["calendar_tag"] else "") + (" · recurs annually" if row["recurring_annual"] else "")
                + (f" · echo of {row['parent_id']}" if row["parent_id"] else "") + "</span>", unsafe_allow_html=True)
    st.write(row["reason"])
    if row["type"] == "activity_shift":
        st.caption("For trading-frequency changes 'actual' / 'expected' are the share of active days after / before the change.")
    if row["type"] == "data_gap":
        st.caption("'expected' is the revenue the dark branches would normally have posted over the gap.")
    c = st.columns(6)
    c[0].metric("actual", fmt(row["actual"]) if row["type"] != "activity_shift" else f"{row['actual']:.0%}")
    c[1].metric("expected", fmt(row["expected"]) if row["type"] != "activity_shift" else f"{row['expected']:.0%}")
    c[2].metric("ratio", "—" if pd.isna(row["ratio"]) else f"{row['ratio']:.2f}×"); c[3].metric("delta", fmt(row["delta_mnt"]))
    c[4].metric("z", "—" if pd.isna(row["z"]) else f"{row['z']:+.1f}"); c[5].metric("share of day", "—" if pd.isna(row["materiality"]) else f"{row['materiality'] * 100:.1f}%")
    cc = st.columns([3, 1])
    with cc[0]:
        w = st.radio("window", ["±45 d", "±120 d", "±1 y", "all"], index=1, horizontal=True, key=f"win_{row['id']}")
        win = {"±45 d": 45, "±120 d": 120, "±1 y": 365, "all": 0}[w]
        logy = st.checkbox("log scale", value=win == 0, key=f"log_{row['id']}")
    with cc[1]:
        if level in R["store"].levels() and st.button("Open in Explorer", key=f"ex_{row['id']}"):
            st.session_state["ex_level"] = level; st.session_state["ex_pick"] = entity; st.session_state["nav_page"] = "Explorer"; st.rerun()
    fig = series_figure(R, level, entity, pd.Timestamp(row["date"]), win, logy, highlight_id=row["id"])
    if fig is None:
        st.info("No stored series for this entity (below density thresholds).")
    else:
        st.plotly_chart(fig, width="stretch")
    try:
        drivers = json.loads(row["drivers"] or "[]")
    except Exception:
        drivers = []
    if drivers:
        d = pd.DataFrame(drivers)
        names = R["names"]
        if "entity" in d:
            d["entity"] = d["entity"].map(lambda e: " · ".join(names.get("item", {}).get(p, names.get("branch", {}).get(p, p)) for p in str(e).split("|")))
        for col in ["actual", "expected", "delta"]:
            if col in d:
                d[col] = d[col].map(fmt)
        if "z" in d:
            d["z"] = d["z"].map(lambda v: "" if v is None or pd.isna(v) else f"{v:+.1f}")
        st.caption("Drivers (largest contributors at the level below)")
        st.dataframe(d, hide_index=True, width="stretch")
    kids = R["anomalies"][R["anomalies"]["parent_id"] == row["id"]]
    if len(kids):
        st.caption(f"{len(kids)} lower-level records echo this one")
        st.dataframe(anomaly_table(kids).drop(columns=["echo"]), hide_index=True, width="stretch", height=min(300, 40 + 35 * len(kids)))


# ------------------------------------------------------------------------------- pages
def page_overview(R):
    m = R["meta"]; a = R["anomalies"]
    d = m["data"]
    st.subheader("Overview")
    srcn = m.get("source", {}).get("name")
    st.caption(f"**{m.get('name','')}**" + (f" · file `{srcn}`" if srcn else "") +
               f" · data {d['date_min']} → {d['date_max']} · {d['rows']:,} rows · {d['branches']} branches · {d['items']} items · "
               f"total {fmt(d['amount_total'])} MNT · sensitivity {m['config']['sensitivity']} · calendar {m['config']['calendar_preset']} · engine {m['engine']}")
    cnt = m["counts"]["by_severity"]
    cols = st.columns(6)
    for i, s in enumerate(SEV_ORDER):
        cols[i].metric(s, cnt.get(s, 0))
    cols[5].metric("series scored", sum(d["series_scored"].values()))
    # headline callouts
    gaps = a[a["type"] == "data_gap"]; closures = a[(a["type"] == "company_closure") & (a["severity"] == "critical")]
    if len(gaps):
        for r in gaps.itertuples():
            st.error(f"**Data gap** {r.date} → {r.end_date}: {r.reason}")
    if len(closures):
        st.warning("**Company-wide closures on non-holidays**: " + ", ".join(closures["date"].tolist()) + " — check for missing extracts / outages.")
    capped = [k for k, v in m.get("thresholds_clipped", {}).items() if v]
    if capped:
        st.caption("Note: at " + ", ".join(LEVEL_LABEL.get(k, k) for k in capped) + " the self-calibrated threshold hit its cap (2× floor) — this level is very noisy; use the sensitivity slider if you want more or fewer alerts there.")
    below = m.get("coverage", {}).get("below_50pct", [])
    if below:
        st.info("Series with under 50 % coverage (too sparse to judge): " + ", ".join(below))

    left, right = st.columns([2, 1])
    with left:
        st.markdown("**Company total — actual vs expected, with anomalies**")
        logy = st.checkbox("log scale", value=True, key="ov_log")
        st.plotly_chart(series_figure(R, "global", "ALL", None, 0, logy, height=360), width="stretch")
    with right:
        st.markdown("**Anomalies per month by severity**")
        t = a[~a["type"].isin(["item_launch", "item_discontinued"]) & (a["parent_id"].fillna("") == "")].copy()   # no echoes
        t["month"] = pd.to_datetime(t["date"]).dt.to_period("M").astype(str)
        piv = t.pivot_table(index="month", columns="severity", values="id", aggfunc="count", fill_value=0)
        fig = go.Figure()
        for s in SEV_ORDER[::-1]:
            if s in piv:
                fig.add_trace(go.Bar(x=piv.index, y=piv[s], name=s, marker_color=SEV_COLOR[s]))
        fig.update_layout(barmode="stack", height=360, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, width="stretch")

    st.markdown("**Top findings** (excluding echoes and lifecycle info)")
    top = a[(a["parent_id"].fillna("") == "") & ~a["type"].isin(["item_launch", "item_discontinued", "company_closure"])].head(15)
    for r in top.itertuples():
        with st.expander(f"{r.priority:.0f} · {r.date}{' → ' + r.end_date if r.end_date else ''} · {LEVEL_LABEL.get(r.level, r.level)} · {r.entity_name} · {TYPE_LABEL.get(r.type, r.type)} · {r.severity}"):
            show_detail(R, a.loc[a["id"] == r.id].iloc[0])

    st.markdown("**By level and type**")
    piv = a.pivot_table(index="level", columns="type", values="id", aggfunc="count", fill_value=0)
    piv.index = [LEVEL_LABEL.get(i, i) for i in piv.index]; piv.columns = [TYPE_LABEL.get(c, c) for c in piv.columns]
    st.dataframe(piv, width="stretch")


def page_anomalies(R):
    a = R["anomalies"]
    st.subheader("Anomaly explorer")
    f = st.columns([1.2, 1.4, 1, 1, 1, 1.4, 0.8])
    level = f[0].selectbox("Level", ["all"] + [l for l in LEVEL_LABEL if l in set(a["level"])], format_func=lambda x: LEVEL_LABEL.get(x, x))
    types = f[1].multiselect("Type", sorted(a["type"].unique(), key=lambda x: list(TYPE_LABEL).index(x) if x in TYPE_LABEL else 99), format_func=lambda x: TYPE_LABEL.get(x, x))
    sev = f[2].selectbox("Min severity", SEV_ORDER, index=1)
    idx = R["index"]
    dfrom = f[3].date_input("From", value=idx[0].date(), min_value=idx[0].date(), max_value=idx[-1].date())
    dto = f[4].date_input("To", value=idx[-1].date(), min_value=idx[0].date(), max_value=idx[-1].date())
    q = f[5].text_input("Search", placeholder="entity, id, text…")
    hide_echo = f[6].checkbox("hide echoes", value=True)
    scope = st.radio("Scope", ["any", "local", "systemic", "mixed"], horizontal=True)
    m = pd.Series(True, index=a.index)
    if level != "all":
        m &= a["level"] == level
    if types:
        m &= a["type"].isin(types)
    m &= a["severity"].map(lambda s: SEV_ORDER.index(s)) <= SEV_ORDER.index(sev)
    m &= (a["date"] >= str(dfrom)) & (a["date"] <= str(dto))
    if hide_echo:
        m &= a["parent_id"].fillna("") == ""
    if scope != "any":
        m &= a["scope"] == scope
    if q:
        ql = q.lower()
        m &= (a["entity_name"].str.lower().str.contains(ql, regex=False) | a["entity"].str.lower().str.contains(ql, regex=False)
              | a["reason"].str.lower().str.contains(ql, regex=False) | a["id"].str.lower().eq(ql))
    view = a[m]
    st.caption(f"{len(view):,} of {len(a):,} records — click a row for details")
    tbl = anomaly_table(view)
    ev = st.dataframe(tbl, hide_index=True, width="stretch", height=420, on_select="rerun", selection_mode="single-row",
                      column_config={"id": None})
    sel = ev.selection.rows if ev and ev.selection else []
    if sel:
        row = view.iloc[sel[0]]
        st.divider()
        show_detail(R, row)
    else:
        st.info("Select a row to see the explanation, drivers and the series chart.")


def page_explorer(R):
    st.subheader("Series explorer")
    store = R["store"]
    c = st.columns([1, 2, 1])
    lv = [l for l in LEVEL_LABEL if l in store.levels()]
    if st.session_state.get("ex_level") not in lv:
        st.session_state["ex_level"] = lv[0]
    level = c[0].selectbox("Level", lv, format_func=lambda x: LEVEL_LABEL.get(x, x), key="ex_level")
    ids = store.ids(level)
    names = R["names"]
    def lab(k):
        if level == "item":
            return f"{k} — {names.get('item', {}).get(k, '')}"
        if level == "branch_item":
            b, i = k.split("|", 1); return f"{b} · {names.get('item', {}).get(i, i)}"
        if level == "branch":
            return f"{k}" + (f" — {names['branch'][k]}" if names.get("branch", {}).get(k) else "")
        return k
    labels = [lab(k) for k in ids]
    default = 0
    if st.session_state.get("ex_pick") in ids:
        default = ids.index(st.session_state.pop("ex_pick"))
        st.session_state[f"ex_ent_{level}"] = default
    pick = c[1].selectbox("Entity", range(len(ids)), format_func=lambda i: labels[i], index=default if ids else None, key=f"ex_ent_{level}")
    if pick is None:
        st.info("nothing scored at this level"); return
    entity = ids[pick]
    win_lbl = c[2].selectbox("Window", ["all", "last 1 y", "last 180 d", "last 90 d"], key="ex_win")
    idx = R["index"]
    win = {"all": 0, "last 1 y": 365, "last 180 d": 180, "last 90 d": 90}[win_lbl]
    center = idx[-1] if win else None
    logy = st.checkbox("log scale", value=win == 0, key="ex_log")
    fig = series_figure(R, level, entity, center, win, logy, height=420)
    if fig is not None:
        st.plotly_chart(fig, width="stretch")
        st.plotly_chart(z_figure(R, level, entity), width="stretch")
    s = store.series(level, entity)
    if s is not None:
        cc = st.columns([1, 1, 2])
        wk = s["weekday_eff"].astype(float)
        cc[0].markdown("**Weekday profile** (× vs average)")
        cc[0].plotly_chart(go.Figure(go.Bar(x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], y=np.exp(wk - wk.mean()), marker_color="#2563eb"))
                           .update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white"), width="stretch")
        eff = R["effects"]
        e = eff[(eff["level"] == level) & (eff["entity"] == entity)] if len(eff) else pd.DataFrame()
        if len(e):
            cc[1].markdown("**Calendar effects** (multiplier)")
            e2 = e.sort_values("multiplier", ascending=False)[["tag", "multiplier", "years_observed"]].head(14)
            e2["multiplier"] = e2["multiplier"].map(lambda v: f"{v:.2f}×")
            cc[1].dataframe(e2, hide_index=True, height=300, width="stretch")
        elif level not in ("global", "branch", "category1"):
            cc[1].caption("Calendar effects are tabulated at company / branch / category-1 level (finer series inherit their parent's effect).")
        an = anomalies_of(R, level, entity).sort_values("date", ascending=False)
        cc[2].markdown(f"**Anomalies for this series** ({len(an)})")
        if len(an):
            t = anomaly_table(an)
            ev = cc[2].dataframe(t, hide_index=True, height=300, width="stretch", on_select="rerun", selection_mode="single-row", column_config={"id": None})
            if ev and ev.selection and ev.selection.rows:
                st.divider(); show_detail(R, an.iloc[ev.selection.rows[0]])


def page_calendar(R):
    st.subheader("Calendar & seasonality")
    eff = R["effects"]; auto = R["auto"]
    if len(eff) == 0:
        st.info("no calendar effects in this run"); return
    g = eff[eff["level"] == "global"].sort_values("tag")
    c = st.columns([1.2, 2])
    with c[0]:
        st.markdown("**Company-wide effect of each calendar day** (× a normal day)")
        t = g[["tag", "multiplier", "years_observed"]].copy()
        st.dataframe(t, hide_index=True, height=520, width="stretch",
                     column_config={"multiplier": st.column_config.ProgressColumn("multiplier", format="%.2f×", min_value=0.0, max_value=float(max(2.0, t["multiplier"].max()))),
                                    "years_observed": st.column_config.NumberColumn("years")})
    with c[1]:
        st.markdown("**Branch × event heatmap** (multiplier at the event day, offset 0 or the strongest offset)")
        b = eff[eff["level"] == "branch"].copy()
        b["event"] = b["tag"].str.replace(r"[+-]\d+$", "", regex=True)
        piv = b.groupby(["entity", "event"])["multiplier"].agg(lambda s: s.iloc[np.argmax(np.abs(np.log(s.values)))]).unstack()
        fig = go.Figure(go.Heatmap(z=np.log2(piv.values.astype(float)), x=piv.columns, y=piv.index, colorscale="RdBu_r", zmid=0, zmin=-2.5, zmax=2.5,
                                   text=np.round(piv.values.astype(float), 2), texttemplate="%{text}", textfont=dict(size=9),
                                   hovertemplate="%{y} · %{x}: %{text}×<extra></extra>", colorbar=dict(title="log2×")))
        if b["years_observed"].max() < 2:
            st.caption("Fewer than 2 years of history — branch-level event effects are not learned yet (they fall back to the company effect).")
        fig.update_layout(height=max(400, 16 * len(piv)), margin=dict(l=10, r=10, t=10, b=10), template="plotly_white")
        st.plotly_chart(fig, width="stretch")
    if len(auto):
        st.markdown("**Recurring days discovered from the data** (not in the preset calendar; treated as calendar days)")
        st.dataframe(auto, hide_index=True, width="stretch")
    st.markdown("**Weekday pattern by branch** (× branch average)")
    store = R["store"]
    ids = store.ids("branch")
    W = np.exp(store.matrix("branch", "weekday_eff").astype(float))
    W = W / W.mean(axis=1, keepdims=True)
    fig = go.Figure(go.Heatmap(z=W, x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], y=ids, colorscale="RdBu_r", zmid=1, text=np.round(W, 2),
                               hovertemplate="%{y} %{x}: %{text}×<extra></extra>"))
    fig.update_layout(height=max(400, 16 * len(ids)), margin=dict(l=10, r=10, t=10, b=10), template="plotly_white")
    st.plotly_chart(fig, width="stretch")


def page_quality(R):
    st.subheader("Data quality & coverage")
    a = R["anomalies"]; m = R["meta"]; d = m["data"]
    c = st.columns(5)
    c[0].metric("rows", f"{d['rows']:,}"); c[1].metric("trading days", f"{d['days']} / {d['calendar_days']}")
    c[2].metric("dropped rows (bad date/amount)", d.get("dropped_rows", 0)); c[3].metric("negative-amount rows", d.get("negative_rows", 0))
    c[4].metric("aggregated from lines", f"{d.get('aggregated_from', d['rows']):,}")
    st.markdown("**Data gaps (several branches dark at once)**")
    g = a[a["type"] == "data_gap"]
    if len(g):
        st.dataframe(anomaly_table(g).drop(columns=["echo"]), hide_index=True, width="stretch")
    else:
        st.write("none")
    st.markdown("**Company closures**")
    cl = a[a["type"] == "company_closure"][["date", "severity", "n_children", "calendar_tag", "reason"]].rename(columns={"n_children": "branches open"})
    st.dataframe(cl, hide_index=True, width="stretch", height=260)
    st.markdown("**Repeated days (identical lines to the previous day)**")
    rd = a[a["type"] == "repeated_day"]
    if len(rd):
        st.dataframe(anomaly_table(rd).drop(columns=["echo"]), hide_index=True, width="stretch")
    else:
        st.write("none")
    uni = m["data"].get("series_universe", {}); sc_ = m["data"]["series_scored"]
    st.caption("Series scored / existing: " + " · ".join(f"{LEVEL_LABEL.get(k, k)} {sc_[k]}/{uni.get(k, sc_[k])}" for k in sc_)
               + ". Sparse series (too few trading days) are not scored.")
    st.markdown("**Coverage — share of each branch's trading days that could be scored**")
    cov = m["coverage"]["share_of_active_days_scorable"].get("branch", {})
    cs = pd.Series(cov).sort_values()
    fig = go.Figure(go.Bar(x=cs.values, y=cs.index, orientation="h", marker_color=np.where(cs.values < 0.5, "#b91c1c", "#2563eb")))
    fig.update_layout(height=max(300, 16 * len(cs)), margin=dict(l=10, r=10, t=10, b=10), template="plotly_white", xaxis=dict(range=[0, 1], tickformat=".0%"))
    st.plotly_chart(fig, width="stretch")
    st.markdown("**Long closures / dark periods per branch (≥ 7 days)**")
    z = a[(a["level"] == "branch") & (((a["type"] == "unexpected_zero") & (a["n_children"] >= 7)) | (a["type"] == "long_silence"))]
    if len(z):
        st.dataframe(anomaly_table(z), hide_index=True, width="stretch")
    else:
        st.write("none")
    st.markdown("**Item lifecycle**")
    lc = a[a["type"].isin(["item_launch", "item_discontinued"])][["date", "type", "entity_name", "reason"]]
    st.dataframe(lc, hide_index=True, width="stretch", height=300)


def page_run():
    st.subheader("New scenario")
    st.caption("A *scenario* is one analysis of one data file. Every scenario you run is saved — see the **Scenarios** page.")

    st.markdown("##### 1 · Choose the data")
    tab_up, tab_disk, tab_demo = st.tabs(["📤 Upload a file", "📁 Choose from this computer", "🧪 Bundled demo data"])
    chosen_upload = None
    chosen_path = ""
    with tab_up:
        chosen_upload = st.file_uploader("Drag a file here, or click Browse", type=["csv", "gz", "parquet"],
                                         help="CSV, CSV.gz or Parquet with the columns DATE, BRANCH_ID, CATEGORY_1_ID, CATEGORY_2_ID, ITEM_ID, AMOUNT")
    with tab_disk:
        c = st.columns([1, 3])
        if c[0].button("📁 Browse…", width="stretch"):
            picked = pick_file_dialog()
            if picked:
                st.session_state["picked_path"] = picked
        chosen_path = c[1].text_input("File path", value=st.session_state.get("picked_path", ""), placeholder=r"e.g. D:\exports\sales_2026.csv")
        st.caption("Best for very large files — nothing is copied, the file is read where it sits.")
    with tab_demo:
        st.write("Analyse the synthetic demo dataset that ships with the app "
                 "(40 branches, 658 products, 2022→2026). Useful to see how everything works.")
        use_demo = st.checkbox("Use the demo dataset", value=False)
        if use_demo:
            chosen_path = str(DATA_DIR / "demo_sales.parquet")

    source_label = ""
    if chosen_upload is not None:
        source_label = f"{chosen_upload.name} ({chosen_upload.size / 1e6:.1f} MB)"
    elif chosen_path:
        pp = Path(chosen_path)
        source_label = f"{pp.name} ({pp.stat().st_size / 1e6:.1f} MB)" if pp.exists() else f"{chosen_path}  ⚠ not found"
    if source_label:
        st.success(f"Selected: **{source_label}**")
    else:
        st.info("Choose a file above (or the demo dataset) to continue.")

    st.markdown("##### 2 · Name this scenario")
    default_name = ""
    if chosen_upload is not None:
        default_name = Path(chosen_upload.name).stem
    elif chosen_path:
        default_name = Path(chosen_path).stem
    name = st.text_input("Scenario name", value=default_name, placeholder="e.g. 2026 H1 actuals, or Region North only",
                         help="Shown in the Scenarios list and in the run selector.")

    st.markdown("##### 3 · Settings")
    with st.expander("Detection settings (defaults are fine)", expanded=False):
        c = st.columns(4)
        sens = c[0].select_slider("Sensitivity", ["low", "medium", "high"], value="medium",
                                  help="How much to report. 'high' shows more, 'low' only the strongest deviations.")
        preset = c[1].selectbox("Holiday calendar", list(PRESETS), format_func=lambda k: PRESETS[k])
        auto_ev = c[2].checkbox("Discover recurring days from the data", value=True)
        causal = c[3].checkbox("Causal baselines (past days only)", value=False,
                               help="Forecast-style scoring. The default uses days on both sides, which is best for auditing history.")
        custom = st.file_uploader("Optional: your own event days (CSV with date,event[,offset_before,offset_after])",
                                  type=["csv"], key="custom_events")

    ready = (chosen_upload is not None) or bool(chosen_path)
    if st.button("▶  Run detection", type="primary", disabled=not ready, width="stretch"):
        try:
            with st.status("Working…", expanded=True) as status:
                t0 = time.time()
                print(f"[detect] ---- new scenario '{name}': source="
                      f"{'upload ' + chosen_upload.name if chosen_upload is not None else chosen_path}, "
                      f"sensitivity={sens}, calendar={preset} ----", flush=True)
                st.write("Reading the file…")
                if chosen_upload is not None:
                    raw = chosen_upload.getvalue()
                    df = load_input(raw, chosen_upload.name)
                    src = {"name": chosen_upload.name, "path": "(uploaded)", "size_mb": round(len(raw) / 1e6, 2)}
                else:
                    pp = Path(chosen_path)
                    if not pp.exists():
                        raise FileNotFoundError(f"{chosen_path} does not exist")
                    df = load_input(pp)
                    src = {"name": pp.name, "path": str(pp), "size_mb": round(pp.stat().st_size / 1e6, 2)}
                desc = describe_input(df)
                print(f"[detect] loaded {desc['rows']:,} rows, {desc['date_min']}..{desc['date_max']}, "
                      f"{desc['branches']} branches, {desc['items']} items", flush=True)
                st.write(f"**{desc['rows']:,} rows** · {desc['date_min']} → {desc['date_max']} · {desc['branches']} branches · "
                         f"{desc['items']} items · total {fmt(desc['amount_total'])}")
                if desc.get("dropped_rows"):
                    st.warning(f"{desc['dropped_rows']:,} rows had an unreadable date or amount and were skipped.")
                if desc["calendar_days"] < 120:
                    st.warning("Less than 120 days of data — baselines will be rough and calendar effects cannot be learned.")
                cev = pd.read_csv(custom) if custom is not None else None
                cfg = RunConfig(calendar_preset=preset, auto_events=auto_ev, sensitivity=sens, causal=causal, custom_events=cev)
                bar = st.progress(0.0, text="starting")

                def prog(f, msg):
                    bar.progress(min(max(f, 0.0), 1.0), text=msg)
                    print(f"[detect] {f:5.0%}  {msg}", flush=True)

                res = run_engine(df, cfg, load_names(DATA_DIR), prog)
                stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
                safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name or Path(src["name"]).stem)[:40].strip("_") or "scenario"
                out = RUNS_DIR / f"{stamp}_{safe}"
                save_run(res, out, name or f"{Path(src['name']).stem} ({desc['date_min']} → {desc['date_max']})", source=src)
                print(f"[detect] DONE in {time.time() - t0:.0f}s — {len(res.anomalies):,} records saved to runs/{out.name}", flush=True)
                status.update(label=f"Done in {time.time() - t0:.0f}s — {len(res.anomalies):,} records", state="complete")
            st.session_state["run_dir"] = str(out)
            st.session_state["nav_page"] = "Overview"
            st.session_state["flash"] = f"Scenario **{name or out.name}** saved — {len(res.anomalies):,} records in {time.time() - t0:.0f}s."
            st.session_state.pop("picked_path", None)
            get_run.clear()
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            print(f"[detect] FAILED: {exc}", flush=True)
            st.error(f"Run failed: {exc}")
            st.exception(exc)


def page_scenarios():
    st.subheader("Scenarios")
    runs = list_runs()
    if not runs:
        st.info("No scenarios yet — create one on the **New scenario** page.")
        return
    st.caption(f"{len(runs)} saved scenario(s). Every run you do is kept here with its data, settings and results.")
    rows = []
    for r in runs:
        m = r["meta"]; d = m.get("data", {}); c = m.get("counts", {}); sev = c.get("by_severity", {})
        rows.append({"scenario": r["name"], "run at": str(m.get("generated_at", ""))[:16].replace("T", " "),
                     "source file": m.get("source", {}).get("name", "—"),
                     "period": f"{d.get('date_min', '?')} → {d.get('date_max', '?')}",
                     "rows": d.get("rows", 0), "branches": d.get("branches", 0), "items": d.get("items", 0),
                     "findings": c.get("total", 0), "critical": sev.get("critical", 0), "high": sev.get("high", 0),
                     "sensitivity": m.get("config", {}).get("sensitivity", ""), "size MB": round(dir_size_mb(r["dir"]), 1),
                     "folder": r["dir"].name})
    tbl = pd.DataFrame(rows)
    cur = st.session_state.get("run_dir")
    pre = [i for i, r in enumerate(runs) if str(r["dir"]) == cur]
    ev = st.dataframe(tbl, hide_index=True, width="stretch", height=min(460, 80 + 36 * len(tbl)),
                      on_select="rerun", selection_mode="single-row",
                      column_config={"folder": None, "rows": st.column_config.NumberColumn(format="%d"),
                                     "findings": st.column_config.NumberColumn(format="%d")})
    sel = ev.selection.rows if ev and ev.selection else pre
    if not sel:
        st.info("Select a scenario to open, rename, export or delete it.")
        return
    r = runs[sel[0]]
    st.markdown(f"#### {r['name']}")
    m = r["meta"]; src = m.get("source", {})
    cc = st.columns(4)
    cc[0].metric("findings", m.get("counts", {}).get("total", 0))
    cc[1].metric("rows analysed", f"{m.get('data', {}).get('rows', 0):,}")
    cc[2].metric("run time", f"{m.get('elapsed_seconds', 0):.0f}s")
    cc[3].metric("folder size", f"{dir_size_mb(r['dir']):.0f} MB")
    st.caption(f"Source: `{src.get('path', '—')}`" + (f" · {src.get('size_mb')} MB" if src.get("size_mb") else "")
               + f" · settings: sensitivity {m.get('config', {}).get('sensitivity')}, calendar {m.get('config', {}).get('calendar_preset')}"
               + (", causal" if m.get("config", {}).get("causal") else "")
               + f" · engine {m.get('engine', '')} · folder `runs/{r['dir'].name}`")

    b = st.columns([1, 1, 1, 1, 2])
    if b[0].button("📂 Open", type="primary", width="stretch"):
        st.session_state["run_dir"] = str(r["dir"]); st.session_state["nav_page"] = "Overview"; st.rerun()
    ap = r["dir"] / "anomalies.csv"
    if ap.exists():
        b[1].download_button("⬇ anomalies.csv", ap.read_bytes(), file_name=f"{r['dir'].name}_anomalies.csv", width="stretch")
    rp = r["dir"] / "report.md"
    if rp.exists():
        b[2].download_button("⬇ report.md", rp.read_bytes(), file_name=f"{r['dir'].name}_report.md", width="stretch")
    with b[3].popover("✏ Rename", width="stretch"):
        nn = st.text_input("New name", value=r["name"], key=f"rn_{r['dir'].name}")
        if st.button("Save name", key=f"rnb_{r['dir'].name}"):
            rename_run(r["dir"], nn); get_run.clear(); st.rerun()
    with b[4].popover("🗑 Delete this scenario"):
        st.warning(f"Delete **{r['name']}** and its saved results? This cannot be undone.")
        if st.button("Yes, delete it", key=f"del_{r['dir'].name}"):
            shutil.rmtree(r["dir"], ignore_errors=True)
            if st.session_state.get("run_dir") == str(r["dir"]):
                st.session_state.pop("run_dir", None)
            get_run.clear(); st.rerun()

    if len(runs) > 1:
        st.markdown("##### Compare scenarios")
        comp = tbl[["scenario", "period", "rows", "findings", "critical", "high", "sensitivity"]]
        st.dataframe(comp, hide_index=True, width="stretch")


def page_export(R):
    st.subheader("Export")
    d = R["dir"]
    st.write(f"Run folder: `{d}`")
    for fname, label in [("anomalies.csv", "anomalies.csv — full table"), ("report.md", "report.md — summary report"),
                         ("calendar_effects.csv", "calendar_effects.csv"), ("calendar.csv", "calendar.csv — event days used"),
                         ("auto_events.csv", "auto_events.csv — recurring days discovered from the data")]:
        p = d / fname
        if p.exists():
            st.download_button(label, p.read_bytes(), file_name=fname, key=f"dl_{fname}")
    st.markdown("---")
    st.markdown((d / "report.md").read_text(encoding="utf-8") if (d / "report.md").exists() else "no report")


# ------------------------------------------------------------------------------- main
def main():
    st.sidebar.title("📈 Sales Anomaly Studio")
    runs = list_runs()
    if runs:
        opts = {str(r["dir"]): f"{r['name']}  ·  {r['generated'][:16].replace('T', ' ')}" for r in runs}
        cur = st.session_state.get("run_dir", str(runs[0]["dir"]))
        if cur not in opts:
            cur = str(runs[0]["dir"])
        pick = st.sidebar.selectbox("Scenario", list(opts), index=list(opts).index(cur), format_func=lambda k: opts[k],
                                    help="Every analysis you run is saved as a scenario. Manage them on the Scenarios page.")
        st.session_state["run_dir"] = pick
    pages = ["Overview", "Anomalies", "Explorer", "Calendar & seasonality", "Data quality", "New scenario", "Scenarios", "Export"]
    want = st.session_state.get("nav_page", "Overview" if runs else "New scenario")
    page = st.sidebar.radio("Page", pages, index=pages.index(want) if want in pages else 0)
    st.session_state["nav_page"] = page
    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))
    if st.sidebar.button("➕  New scenario", width="stretch"):
        st.session_state["nav_page"] = "New scenario"; st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.caption("Every anomaly is judged against its own calendar-aware baseline; thresholds self-calibrate to the dataset. "
                       "Echoes are lower-level repeats of a higher-level finding.")
    if page == "New scenario":
        page_run(); return
    if page == "Scenarios":
        page_scenarios(); return
    R = current_run()
    if R is None:
        st.info("No scenario yet — go to **New scenario** to analyse a data file."); return
    {"Overview": page_overview, "Anomalies": page_anomalies, "Explorer": page_explorer, "Calendar & seasonality": page_calendar,
     "Data quality": page_quality, "Export": page_export}[page](R)


main()
