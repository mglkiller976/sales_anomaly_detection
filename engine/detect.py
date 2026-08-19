"""Turn scored panels into typed, explained anomaly records."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .model import LEVELS, LEVEL_LABEL, PARENT_LEVEL, CHILD_LEVEL, Panel, Scored

try:
    from sklearn.ensemble import IsolationForest
except Exception:  # pragma: no cover
    IsolationForest = None


@dataclass
class DetectConfig:
    sensitivity: str = "medium"           # low | medium | high  (scales the target alert rates)
    # z floors per level (never alert below these) and target alert rates (share of scorable days)
    z_floor: dict = field(default_factory=lambda: {"global": 3.5, "branch": 4.0, "category1": 4.0, "category2": 4.0,
                                                   "branch_category": 4.5, "item": 4.5, "branch_item": 5.0})
    rate: dict = field(default_factory=lambda: {"global": 0.02, "branch": 0.010, "category1": 0.010, "category2": 0.008,
                                                "branch_category": 0.004, "item": 0.005, "branch_item": 0.0015})
    spike_ratio: float = 1.5
    drop_ratio: float = 0.67
    fine_spike_ratio: float = 2.5
    fine_drop_ratio: float = 0.4
    materiality_floor: float = 1e-4        # |delta| >= this share of the median company day
    fine_materiality_floor: float = 3e-4
    warmup_days: int = 21
    zero_open_prob: float = 0.9
    zero_min_series_share: float = 1e-4    # median active-day amount >= share of median company day
    systemic_min: int = 4
    systemic_share: float = 0.2
    iso_contamination: float = 0.005
    max_per_series: int = 0

    def rate_multiplier(self) -> float:
        return {"low": 0.5, "medium": 1.0, "high": 2.0}.get(self.sensitivity, 1.0)


def fmt_mnt(v: float) -> str:
    if v is None or not np.isfinite(v):
        return "n/a"
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:,.2f}B"
    if a >= 1e6:
        return f"{v / 1e6:,.1f}M"
    if a >= 1e3:
        return f"{v / 1e3:,.0f}k"
    return f"{v:,.0f}"


def entity_label(level: str, key: str, names: dict) -> str:
    if level == "global":
        return "Company total"
    if level == "item":
        return names.get("item", {}).get(key, key)
    if level == "branch_item":
        b, i = key.split("|", 1)
        return f"{names.get('branch', {}).get(b, b)} · {names.get('item', {}).get(i, i)}"
    if level == "branch_category":
        b, c = key.split("|", 1)
        return f"{names.get('branch', {}).get(b, b)} · category {c}"
    if level.startswith("category"):
        return f"category {key}"
    return names.get("branch", {}).get(key, key)


def who(level: str, key: str, names: dict) -> str:
    lbl = entity_label(level, key, names)
    return lbl if level == "global" else f"{LEVEL_LABEL[level]} {lbl}"


def severity_for(z: float, ratio: float, level: str) -> str:
    az = abs(z)
    extreme = ratio >= 3.0 or ratio <= 1 / 3
    strong = ratio >= 2.0 or ratio <= 0.5
    huge = ratio >= 6.0 or ratio <= 1 / 6
    if level in ("global", "branch", "category1"):
        if (az >= 8 and strong) or (az >= 6 and extreme):
            return "critical"
        return "high" if (az >= 5.5 or strong) else "medium"
    if level in ("category2", "branch_category", "item"):
        if (az >= 10 and extreme) or (az >= 7 and huge):
            return "critical"
        return "high" if (az >= 7 or extreme) else "medium"
    if az >= 12 and huge:
        return "critical"
    return "high" if (az >= 8 and extreme) else "medium"


def calibrate_thresholds(scored: dict[str, Scored], cfg: DetectConfig) -> dict[str, float]:
    """Effective |z| threshold per level = max(floor, empirical quantile at the target alert rate).
    This adapts the detector to the noise level of whatever dataset is loaded."""
    mult = cfg.rate_multiplier()
    out, clipped = {}, {}
    for level, sc in scored.items():
        z = np.abs(sc.z[sc.scorable])
        floor = cfg.z_floor.get(level, 4.0)
        lo = floor / (1.15 if cfg.sensitivity == "high" else 1.0)
        n_days = int(sc.scorable.any(axis=0).sum())
        if z.size < 200 or n_days < 120:                     # too little independent history: use the floor
            out[level] = lo; clipped[level] = False
            continue
        rate = min(0.2, cfg.rate.get(level, 0.005) * mult)
        q = float(np.quantile(z, 1 - rate))
        out[level] = float(np.clip(q, lo, 2.0 * floor))          # adaptive, but never absurdly strict
        clipped[level] = bool(q > 2.0 * floor)
    return out, clipped


class Detector:
    def __init__(self, cfg: DetectConfig, index: pd.DatetimeIndex, cal: pd.DataFrame, names: dict, global_amount: np.ndarray):
        self.cfg = cfg; self.index = index; self.cal = cal; self.names = names
        self.global_amount = global_amount
        gm = global_amount[global_amount > 0]
        self.global_median_day = float(np.median(gm)) if gm.size else 1.0
        self.tags = cal["tag"].to_numpy()
        self.records: list[dict] = []
        self._id = 0
        self.thresholds: dict[str, float] = {}

    def new_id(self) -> str:
        self._id += 1
        return f"A{self._id:06d}"

    def _base(self, level, key, t, typ, direction, severity, **kw) -> dict:
        r = {"id": self.new_id(), "date": self.index[t].date().isoformat(), "end_date": "", "level": level, "entity": key,
             "entity_name": entity_label(level, key, self.names), "type": typ, "direction": direction, "severity": severity,
             "actual": np.nan, "expected": np.nan, "lower": np.nan, "upper": np.nan, "ratio": np.nan, "delta_mnt": np.nan,
             "z": np.nan, "z_peer": np.nan, "scope": "", "materiality": np.nan, "calendar_tag": self.tags[t],
             "recurring_annual": 0, "parent_id": "", "n_children": 0, "drivers": "[]", "reason": "", "_s": -1, "_t": int(t)}
        r.update(kw)
        return r

    # ------------------------------------------------------------------ point anomalies
    def point_anomalies(self, sc: Scored, children: Scored | None, thr: float) -> list[dict]:
        cfg = self.cfg; level = sc.panel.level; index = self.index
        S, T = sc.z.shape
        A = sc.panel.amount
        exp_mnt = np.expm1(sc.expected)
        ratio = A / np.maximum(exp_mnt, 1.0)
        delta = A - exp_mnt
        fine = level in ("branch_item", "branch_category")
        sp, dr = (cfg.fine_spike_ratio, cfg.fine_drop_ratio) if fine else (cfg.spike_ratio, cfg.drop_ratio)
        min_delta = (cfg.fine_materiality_floor if fine else cfg.materiality_floor) * self.global_median_day
        cand = sc.scorable & (np.abs(sc.z) >= thr) & ((ratio >= sp) | (ratio <= dr)) & (np.abs(delta) >= min_delta)
        days_since_first = np.arange(T)[None, :] - sc.first[:, None]
        cand &= ~((days_since_first < cfg.warmup_days) & (sc.z < 0))
        min_other = 2 if level in ("item", "branch_item", "branch_category", "category2") else 1
        thin = (self.tags != "")[None, :] & (sc.event_nother < min_other)
        cand &= ~(thin & (np.abs(sc.z) < thr + 3))
        # peer-adjusted z: how much of the deviation is specific to this series vs shared by its peers that day
        with np.errstate(all="ignore"):
            peer_med = np.nanmedian(np.where(sc.scorable, sc.z, np.nan), axis=0) if S >= 5 else np.zeros(T)
        peer_med = np.where(np.isfinite(peer_med), peer_med, 0.0)
        z_local = sc.z - peer_med[None, :]
        md = index.strftime("%m-%d").to_numpy(); years = index.year.to_numpy()
        recs = []
        for s, t in zip(*np.nonzero(cand)):
            z = float(sc.z[s, t]); r = float(ratio[s, t]); key = sc.panel.ids[s]
            direction = "spike" if z > 0 else "drop"
            gap = np.abs((index - index[t]).days) % 365
            same = np.flatnonzero((np.isin(md, [md[t]]) | (np.minimum(gap, 365 - gap) <= 1)) & (years != years[t]))
            oz = sc.z[s, same]
            recurring = int(np.sum((np.sign(oz) == np.sign(z)) & (np.abs(oz) >= 3.0)) >= 2)
            drivers = self.drivers(sc, s, t, children)
            sev = severity_for(z, r, level)
            if self.tags[t] and (thin[s, t] or fine or level == "item") and sev == "critical":
                sev = "high"
            gm = float(self.global_amount[t]) if self.global_amount[t] > 0 else np.nan
            mat = abs(float(delta[s, t])) / gm if np.isfinite(gm) else np.nan
            zp = float(z_local[s, t]) if S >= 5 else np.nan
            if level in ("branch_item", "branch_category"):
                scope = "n/a"
            elif S >= 5:
                pm = float(peer_med[t])
                if abs(pm) >= 2.0 and abs(zp) < thr * 0.5:
                    scope = "systemic"
                elif abs(pm) >= 2.0:
                    scope = "mixed"
                else:
                    scope = "local"
            else:
                scope = "n/a"
            reason = (f"{who(level, key, self.names)}: {fmt_mnt(float(A[s, t]))} on {index[t].date()} ({index[t].day_name()}) "
                      f"vs expected {fmt_mnt(float(exp_mnt[s, t]))} — {r:.2f}× ({'+' if delta[s, t] >= 0 else ''}{fmt_mnt(float(delta[s, t]))}), z={z:+.1f}")
            if self.tags[t]:
                reason += f"; calendar: {self.tags[t]} (effect already in the baseline)"
            if scope == "systemic":
                reason += "; peers moved the same way — company-wide, not specific to this series"
            elif scope == "mixed":
                reason += "; partly company-wide, partly specific"
            if recurring:
                reason += "; similar deviation recurs on this date in other years"
            if r >= 20 or (r <= 0.05 and A[s, t] > 0):
                reason += "; magnitude suggests a posting / data-entry error — verify the source lines"
            if drivers:
                reason += ". Drivers: " + "; ".join(f"{self.short(d['entity'])} {'+' if d['delta'] >= 0 else ''}{fmt_mnt(d['delta'])}" for d in drivers[:3])
            recs.append(self._base(level, key, t, f"point_{direction}", direction, sev,
                                   actual=float(A[s, t]), expected=float(exp_mnt[s, t]),
                                   lower=float(np.expm1(sc.expected[s, t] - thr * sc.sigma[s, t])),
                                   upper=float(np.expm1(sc.expected[s, t] + thr * sc.sigma[s, t])),
                                   ratio=r, delta_mnt=float(delta[s, t]), z=z, z_peer=zp, scope=scope, materiality=mat,
                                   recurring_annual=recurring, drivers=json.dumps(drivers, ensure_ascii=False), reason=reason, _s=int(s)))
        return recs

    def short(self, entity: str) -> str:
        parts = entity.split("|")
        nm = self.names
        if len(parts) == 2:
            b, x = parts
            return f"{nm.get('branch', {}).get(b, b)}·{nm.get('item', {}).get(x, x)}"
        return nm.get("item", {}).get(entity, nm.get("branch", {}).get(entity, entity))

    def drivers(self, sc: Scored, s: int, t: int, children: Scored | None) -> list[dict]:
        if children is None:
            return []
        link = children.panel.driver_idx.get(sc.panel.level, children.panel.parent_idx)
        if link is None:
            return []
        rows = np.flatnonzero(link == s)
        if rows.size == 0:
            return []
        act = children.panel.amount[rows, t]
        exp = np.expm1(children.expected[rows, t])
        exp = np.where(np.isfinite(exp), exp, act)
        po = children.p_open[rows, t]
        routine_absent = (act <= 0) & ~(np.isfinite(po) & (po >= 0.5))    # a child that is often closed on this weekday
        exp = np.where(routine_absent, act, exp)
        d = act - exp
        sign = np.sign(float(sc.panel.amount[s, t] - np.expm1(sc.expected[s, t]))) if np.isfinite(sc.expected[s, t]) else 0.0
        same = (np.sign(d) == sign) if sign else np.ones_like(d, dtype=bool)
        order = np.lexsort((-np.abs(d), ~same))[:5]
        out = []
        for j in order:
            if abs(d[j]) < 1.0:
                continue
            zc = children.z[rows[j], t]
            out.append({"entity": children.panel.ids[rows[j]], "actual": float(act[j]), "expected": float(exp[j]),
                        "delta": float(d[j]), "z": float(zc) if np.isfinite(zc) else None})
        return out

    # ------------------------------------------------------------------ zero episodes
    def zero_episodes(self, sc: Scored, global_active_share: np.ndarray) -> list[dict]:
        cfg = self.cfg; level = sc.panel.level; index = self.index
        A = sc.panel.amount; active = A > 0; S, T = A.shape
        med_amt = np.nanmedian(np.where(active, A, np.nan), axis=1)
        unexpected = (~active) & sc.lifetime & (sc.p_open >= cfg.zero_open_prob) & (global_active_share >= 0.5)[None, :]
        unexpected &= (np.arange(T)[None, :] - sc.first[:, None]) >= cfg.warmup_days
        min_len = {"branch": 1, "category1": 1, "category2": 2, "branch_category": 2, "item": 2, "branch_item": 3}.get(level, 1)
        what = {"branch": "branch closed / no sales posted", "item": "item not sold anywhere", "branch_item": "item not sold at this branch",
                "branch_category": "category not sold at this branch", "category1": "category not sold", "category2": "sub-category not sold"}.get(level, "no sales")
        recs = []
        for s in range(S):
            if not (med_amt[s] >= cfg.zero_min_series_share * self.global_median_day):
                continue
            row = unexpected[s]
            if not row.any():
                continue
            t = 0
            while t < T:
                if not row[t]:
                    t += 1; continue
                start = t; k = t + 1
                while k < T and (~active[s, k]) and sc.lifetime[s, k]:   # the whole inactive run
                    k += 1
                end = k - 1
                length = end - start + 1
                if length < min_len or (level in ("item", "branch_item") and float(np.nanmean(sc.p_open[s, start:end + 1])) < 0.95):
                    t = k; continue
                e_seg = np.expm1(sc.expected[s, start:end + 1])
                exp_loss = float(np.nansum(e_seg) + med_amt[s] * np.sum(~np.isfinite(e_seg)))   # baseline is NaN deep inside a gap
                if not np.isfinite(exp_loss) or exp_loss <= 0:
                    exp_loss = float(med_amt[s] * length)
                sev = "critical" if length >= 7 else "high" if length >= 3 else "medium"
                if level in ("item", "branch_item") and length < 3:
                    sev = "low"
                key = sc.panel.ids[s]
                reason = (f"{who(level, key, self.names)}: {what} for {length} day(s) from {index[start].date()} although it is normally "
                          f"active on these weekdays (p(open)≈{np.nanmean(sc.p_open[s, start:end + 1]):.2f}); expected ≈{fmt_mnt(exp_loss)}")
                if self.tags[start]:
                    tag = self.tags[start]
                    others = np.flatnonzero((self.tags == tag) & (self.index.year != index[start].year))
                    closed_other = int(np.sum(~active[s, others] & sc.lifetime[s, others])); n_other = int(np.sum(sc.lifetime[s, others]))
                    if n_other and closed_other >= max(1, math.ceil(0.5 * n_other)):
                        sev = "info"
                        reason += f"; calendar: {tag} — also closed on this day in {closed_other} of {n_other} other years (recurring holiday closure)"
                    else:
                        reason += f"; calendar: {tag}"
                recs.append(self._base(level, key, start, "unexpected_zero", "drop", sev, end_date=index[end].date().isoformat(),
                                       actual=0.0, expected=exp_loss, ratio=0.0, delta_mnt=-exp_loss, n_children=length, reason=reason, _s=int(s),
                                       materiality=exp_loss / max(float(np.nansum(self.global_amount[start:end + 1])), 1.0)))
                t = k
        return recs

    # ------------------------------------------------------------------ level shifts (change points)
    def level_shifts(self, sc: Scored, cps: list[dict]) -> list[dict]:
        level = sc.panel.level; index = self.index; T = len(index)
        recs = []
        for c in cps:
            s, t = c["s"], min(c["t"], T - 1)
            if not sc.lifetime[s, t]:
                continue
            ratio_adj = math.exp(c["shift_log"]); ratio_raw = math.exp(c["shift_log"] + c["seasonal_log"])
            direction = "spike" if c["shift_log"] > 0 else "drop"
            sev = "critical" if (abs(c["shift_log"]) >= math.log(2.0) and c["weeks_after"] >= 8) else "high" if abs(c["shift_log"]) >= math.log(1.6) else "medium"
            key = sc.panel.ids[s]
            reason = (f"{who(level, key, self.names)}: level change around {index[t].date()} — the following weeks run "
                      f"{ratio_raw:.2f}× the preceding weeks (median trading day {fmt_mnt(c['before_raw'])} → {fmt_mnt(c['after_raw'])})")
            if abs(c["seasonal_log"]) >= 0.05:
                reason += f"; the usual change at this time of year is {math.exp(c['seasonal_log']):.2f}×, so the unusual part is {ratio_adj:.2f}×"
            reason += f"; new level held for {c['weeks_after']} weeks; t={c['t_stat']:+.1f}"
            end = min(T - 1, t + 7 * min(c["weeks_after"], 8) - 1)
            recs.append(self._base(level, key, t, "level_shift", direction, sev, end_date=index[end].date().isoformat(),
                                   actual=c["after_raw"], expected=c["before_raw"], ratio=ratio_adj,
                                   delta_mnt=(c["after_raw"] - c["before_raw"]) * 28 if np.isfinite(c["after_raw"]) and np.isfinite(c["before_raw"]) else np.nan,
                                   z=c["t_stat"], n_children=c["weeks_after"], reason=reason, _s=int(s)))
        return recs


    # ------------------------------------------------------------------ trading-frequency changes
    def activity_shifts(self, sc: Scored) -> list[dict]:
        from .model import find_activity_shifts
        level = sc.panel.level; index = self.index; T = len(index); recs = []
        for c in find_activity_shifts(sc, None):
            s, t = c["s"], min(c["t"], T - 1)
            key = sc.panel.ids[s]
            direction = "spike" if c["after"] > c["before"] else "drop"
            delta = c["after"] - c["before"]
            sev = "high" if abs(delta) >= 0.5 else "medium"
            end = min(T - 1, t + 7 * min(c["weeks_after"], 8) - 1)
            reason = (f"{who(level, key, self.names)}: trading frequency changed around {index[t].date()} — active on {c['before']:.0%} of days "
                      f"in the 8 weeks before vs {c['after']:.0%} after ({'+' if delta > 0 else ''}{delta * 100:.0f} pp); held for {c['weeks_after']} weeks")
            recs.append(self._base(level, key, t, "activity_shift", direction, sev, end_date=index[end].date().isoformat(),
                                   actual=c["after"], expected=c["before"], ratio=(c["after"] / c["before"]) if c["before"] > 0 else np.nan,
                                   n_children=c["weeks_after"], reason=reason, _s=int(s)))
        return recs


# =========================================================================== extra detectors
def company_closures(det: Detector, panels: dict[str, Panel], scored: dict[str, Scored], branch_active_share: np.ndarray) -> list[dict]:
    g = scored["global"]; index = det.index; recs = []
    years = index.year.to_numpy()
    for t in np.flatnonzero((branch_active_share < 0.5) & g.lifetime[0]):
        tag = det.tags[t]; hol = bool(det.cal["is_holiday"].iloc[t])
        n_open = int((panels["branch"].amount[:, t] > 0).sum())
        if hol:
            sev, why = "info", f" — {tag} public holiday"
        elif tag:
            others = np.flatnonzero((det.tags == tag) & (years != years[t]) & g.lifetime[0])
            rec = int(np.sum(branch_active_share[others] < 0.5))
            if rec >= 1:
                sev, why = "info", f" — around {tag}; the company was also largely closed on this day in {rec} of {others.size} other years (recurring closure)"
            else:
                sev, why = "high", f" — near {tag} but the company traded normally on this day in other years: check for an outage / missing extract"
        else:
            sev, why = "critical", " — NOT a known holiday: check for a system outage / missing extract"
        recs.append(det._base("global", "ALL", t, "company_closure", "drop", sev,
                              actual=float(det.global_amount[t]),
                              expected=float(np.expm1(g.expected[0, t])) if np.isfinite(g.expected[0, t]) else np.nan,
                              n_children=n_open, _s=0,
                              reason=f"Only {n_open} branches posted sales on {index[t].date()} ({branch_active_share[t]:.0%} of active branches)" + why))
    return recs


def systemic_events(det: Detector, recs: list[dict], scored: dict[str, Scored]) -> list[dict]:
    cfg = det.cfg; br = scored["branch"]; index = det.index
    by_date: dict[tuple[str, str], list[dict]] = {}
    for r in recs:
        if r["level"] == "branch" and r["type"].startswith("point_"):
            by_date.setdefault((r["date"], r["direction"]), []).append(r)
    global_by = {(r["date"], r["direction"]): r for r in recs if r["level"] == "global" and r["type"].startswith("point_")}
    out = []
    for (date, direction), group in by_date.items():
        t = index.get_loc(pd.Timestamp(date))
        n_scorable = int(np.sum(br.scorable[:, t]))
        if len(group) < max(cfg.systemic_min, math.ceil(cfg.systemic_share * max(n_scorable, 1))):
            continue
        parent = global_by.get((date, direction))
        g = scored["global"]
        if parent is None:
            parent = det._base("global", "ALL", t, "systemic_event", direction, "high", actual=float(g.panel.amount[0, t]),
                               expected=float(np.expm1(g.expected[0, t])) if np.isfinite(g.expected[0, t]) else np.nan,
                               z=float(g.z[0, t]) if np.isfinite(g.z[0, t]) else np.nan, _s=0, calendar_tag=group[0]["calendar_tag"])
            out.append(parent)
        else:
            parent["type"] = "systemic_event"
        parent["n_children"] = len(group)
        parent["scope"] = "systemic"
        parent["drivers"] = json.dumps([{"entity": g_["entity"], "actual": g_["actual"], "expected": g_["expected"], "delta": g_["delta_mnt"], "z": g_["z"]}
                                        for g_ in sorted(group, key=lambda x: -abs(x["delta_mnt"]))[:10]], ensure_ascii=False)
        parent["reason"] = (f"Company-wide {direction} on {date}: {len(group)} of {n_scorable} scorable branches moved the same way "
                            f"(e.g. {', '.join(det.short(x['entity']) for x in group[:6])}). Total {fmt_mnt(parent['actual'])} vs expected "
                            f"{fmt_mnt(parent['expected'])}. Likely a calendar/company event, price change or system issue rather than a local problem")
        if group[0]["calendar_tag"]:
            parent["reason"] += f"; calendar: {group[0]['calendar_tag']}"
        for x in group:
            x["parent_id"] = parent["id"]
    return out


def data_gaps(det: Detector, recs: list[dict], scored: dict[str, Scored], min_days: int = 5) -> list[dict]:
    """Several branches going dark at the same time for days = probable missing extract / outage.
    Creates one critical global record per gap and makes the branch episodes its children."""
    br = scored["branch"]; index = det.index; T = len(index)
    eps = [r for r in recs if r["level"] == "branch" and r["type"] == "unexpected_zero" and r["n_children"] >= min_days]
    if len(eps) < 2:
        return []
    eps.sort(key=lambda r: r["date"])
    out = []; used = set()
    for i, e in enumerate(eps):
        if e["id"] in used:
            continue
        d0 = pd.Timestamp(e["date"])
        group = [e]; last = d0
        for x in eps[i + 1:]:                       # chain: within 3 days of the group's latest start
            if x["id"] in used:
                continue
            dx = pd.Timestamp(x["date"])
            if (dx - last).days <= 3:
                group.append(x); last = dx
            elif (dx - last).days > 3:
                break
        t = index.get_loc(d0)
        n_active = int(br.lifetime[:, t].sum())
        start = min(pd.Timestamp(x["date"]) for x in group); end = max(pd.Timestamp(x["end_date"]) for x in group)
        loss = float(sum(x["expected"] for x in group))
        period_rev = max(float(np.nansum(det.global_amount[index.get_loc(start):index.get_loc(end) + 1])), 1.0)
        if len(group) < 2 or not (len(group) >= math.ceil(0.10 * max(n_active, 1)) or loss / period_rev >= 0.05):
            continue
        for x in group:
            used.add(x["id"])
        rec = det._base("global", "ALL", index.get_loc(start), "data_gap", "drop", "critical", end_date=end.date().isoformat(),
                        actual=np.nan, expected=loss, delta_mnt=-loss, ratio=np.nan, n_children=int((end - start).days + 1), scope="systemic",
                        materiality=loss / max(float(np.nansum(det.global_amount[index.get_loc(start):index.get_loc(end) + 1])), 1.0),
                        drivers=json.dumps([{"entity": x["entity"], "expected": x["expected"], "days": x["n_children"], "from": x["date"], "to": x["end_date"]} for x in group], ensure_ascii=False),
                        reason=(f"{len(group)} branches ({', '.join(det.short(x['entity']) for x in group[:8])}) posted NO sales from {start.date()} to {end.date()} "
                                f"({(end - start).days + 1} days) although they were trading normally before — probable missing extract, system outage or "
                                f"closure of a whole company/region; ≈{fmt_mnt(loss)} of expected revenue is absent from the file. Verify the source data before "
                                "reading any other finding in this period."))
        out.append(rec)
        for x in group:
            x["parent_id"] = rec["id"]
    return out


def repeated_days(det: Detector, df: pd.DataFrame) -> list[dict]:
    """Branch-days whose (item, amount) lines are identical to the previous day (>= 10 lines)."""
    g = df.sort_values(["BRANCH_ID", "DATE", "ITEM_ID"])
    key = g["ITEM_ID"].astype(str) + ":" + g["AMOUNT"].round(2).astype(str)
    sig = (pd.DataFrame({"BRANCH_ID": g["BRANCH_ID"], "DATE": g["DATE"], "k": key, "AMOUNT": g["AMOUNT"]})
           .groupby(["BRANCH_ID", "DATE"], observed=True)
           .agg(n=("k", "size"), amt=("AMOUNT", "sum"), h=("k", lambda s: hashlib.md5("|".join(s).encode()).hexdigest()))
           .reset_index().sort_values(["BRANCH_ID", "DATE"]))
    prev = sig.groupby("BRANCH_ID")[["DATE", "h"]].shift(1)
    same = (sig["h"] == prev["h"]) & ((sig["DATE"] - prev["DATE"]).dt.days == 1) & (sig["n"] >= 10)
    recs = []
    for r in sig[same].itertuples():
        t = det.index.get_loc(pd.Timestamp(r.DATE))
        recs.append(det._base("branch", str(r.BRANCH_ID), t, "repeated_day", "spike", "high", actual=float(r.amt), delta_mnt=float(r.amt), n_children=int(r.n),
                              reason=f"Branch {r.BRANCH_ID}: the {int(r.n)} item lines on {r.DATE.date()} are identical (same items, same amounts, {fmt_mnt(r.amt)}) to the previous day — probable duplicated posting"))
    return recs


def unusual_mix(det: Detector, panels: dict[str, Panel], scored: dict[str, Scored], already: set) -> list[dict]:
    if IsolationForest is None:
        return []
    cfg = det.cfg; index = det.index
    br = panels["branch"]; bc = panels["branch_category"]
    cats = sorted({k.split("|")[1] for k in bc.ids})
    if len(cats) < 3:
        return []
    cidx = {c: i for i, c in enumerate(cats)}
    B, T = br.amount.shape
    share = np.zeros((B, T, len(cats)))
    bpos = {b: i for i, b in enumerate(br.ids)}
    for k, row in zip(bc.ids, bc.amount):
        b, c = k.split("|")
        share[bpos[b], :, cidx[c]] = row
    tot = br.amount[:, :, None]
    share = np.where(tot > 0, share / np.maximum(tot, 1e-9), np.nan)
    dev = np.full_like(share, np.nan)
    for j in range(len(cats)):
        ref = pd.DataFrame(share[:, :, j].T).rolling(57, center=True, min_periods=20).median().to_numpy().T
        dev[:, :, j] = share[:, :, j] - ref
    is_event = det.tags != ""
    first_b = scored["branch"].first
    feats, meta = [], []
    for b in range(B):
        for t in range(T):
            if br.amount[b, t] <= 0 or is_event[t] or not np.isfinite(dev[b, t]).all() or t - first_b[b] < cfg.warmup_days:
                continue
            feats.append(dev[b, t]); meta.append((b, t))
    if len(feats) < 500:
        return []
    X = np.asarray(feats)
    iso = IsolationForest(n_estimators=200, contamination=cfg.iso_contamination, random_state=7).fit(X)
    flag = iso.predict(X) == -1
    zb = scored["branch"].z
    recs = []
    for k in np.flatnonzero(flag):
        b, t = meta[k]; key = br.ids[b]
        if (key, index[t].date().isoformat()) in already:
            continue
        top = np.argsort(-np.abs(dev[b, t]))[:3]
        parts = ", ".join(f"category {cats[j]} {dev[b, t, j] * 100:+.0f} pp (share {share[b, t, j] * 100:.0f}%)" for j in top)
        gm = float(det.global_amount[t]) if det.global_amount[t] > 0 else np.nan
        recs.append(det._base("branch", key, t, "unusual_mix", "mix", "medium", actual=float(br.amount[b, t]),
                              expected=float(np.expm1(scored["branch"].expected[b, t])), z=float(zb[b, t]) if np.isfinite(zb[b, t]) else np.nan,
                              materiality=(float(np.abs(dev[b, t]).sum()) * float(br.amount[b, t]) / 2.0 / gm) if np.isfinite(gm) else np.nan,
                              drivers=json.dumps([{"entity": f"{key}|{cats[j]}", "delta_share_pp": float(dev[b, t, j] * 100)} for j in top]), _s=int(b),
                              reason=f"{who('branch', key, det.names)} on {index[t].date()}: category mix is unusual for this branch — {parts}; total {fmt_mnt(float(br.amount[b, t]))} "
                                     f"(z={float(zb[b, t]) if np.isfinite(zb[b, t]) else 0:+.1f}): the total looks normal but WHAT was sold does not"))
    return recs


def lifecycle_events(det: Detector, sc: Scored, long_silence_days: int = 0, existing: list[dict] | None = None) -> list[dict]:
    A = sc.panel.amount; active = A > 0; T = A.shape[1]; index = det.index; recs = []
    level = sc.panel.level
    covered = {(r["entity"], r["date"]) for r in (existing or []) if r["level"] == level and r["type"] == "unexpected_zero"}
    for s, key in enumerate(sc.panel.ids):
        idx = np.flatnonzero(active[s])
        if idx.size == 0:
            continue
        first, last = idx[0], idx[-1]
        if long_silence_days:
            gaps = np.diff(idx)
            for g_i in np.flatnonzero(gaps > long_silence_days):
                s0, s1 = idx[g_i] + 1, idx[g_i + 1] - 1
                if (key, index[s0].date().isoformat()) in covered:
                    continue
                med = float(np.nanmedian(np.where(active[s, max(0, s0 - 90):s0], A[s, max(0, s0 - 90):s0], np.nan)))
                recs.append(det._base(level, key, s0, "long_silence", "drop", "high", end_date=index[s1].date().isoformat(), actual=0.0,
                                      expected=med * (s1 - s0 + 1) if np.isfinite(med) else np.nan, n_children=int(s1 - s0 + 1), _s=s,
                                      reason=f"{who(level, key, det.names)}: no sales for {s1 - s0 + 1} days ({index[s0].date()} → {index[s1].date()}) between two trading periods"
                                             + (f"; ran ≈{fmt_mnt(med)}/active day before" if np.isfinite(med) else "")))
        if level != "item":
            continue
        if first >= 30:
            recs.append(det._base(sc.panel.level, key, first, "item_launch", "spike", "info", actual=float(A[s, first]), _s=s,
                                  reason=f"{entity_label(sc.panel.level, key, det.names)} first sold on {index[first].date()}"))
        if last <= T - 1 - 30:
            med = float(np.nanmedian(np.where(active[s, max(0, last - 90):last + 1], A[s, max(0, last - 90):last + 1], np.nan)))
            recs.append(det._base(sc.panel.level, key, last, "item_discontinued", "drop", "info", end_date=index[-1].date().isoformat(),
                                  actual=0.0, expected=med, ratio=0.0, n_children=int(T - 1 - last), _s=s,
                                  reason=f"{entity_label(sc.panel.level, key, det.names)} last sold on {index[last].date()} ({T - 1 - last} days before the data ends; ran ≈{fmt_mnt(med)}/active day before)"))
    return recs


# =========================================================================== roll-up + priority
def roll_up(recs: list[dict], c2c1: dict, i2c1: dict, closure_ids: dict) -> None:
    parent_of = {"branch": ("global", lambda e: "ALL"), "category1": ("global", lambda e: "ALL"),
                 "category2": ("category1", lambda e: c2c1.get(e, "")), "branch_category": ("branch", lambda e: e.split("|")[0]),
                 "item": ("category1", lambda e: i2c1.get(e, "")), "branch_item": ("branch", lambda e: e.split("|")[0])}
    by_key: dict[tuple, str] = {}
    for r in recs:
        if r["type"] in ("point_spike", "point_drop", "systemic_event", "unexpected_zero", "level_shift", "activity_shift", "data_gap"):
            d0 = pd.Timestamp(r["date"]); d1 = pd.Timestamp(r["end_date"]) if r["end_date"] else d0
            for d in pd.date_range(d0, d1):
                by_key.setdefault((r["level"], r["entity"], d.date().isoformat(), r["direction"]), r["id"])
    for r in recs:
        if r["parent_id"] or r["level"] not in parent_of or r["type"] not in ("point_spike", "point_drop", "unexpected_zero", "level_shift", "activity_shift"):
            continue
        plevel, fn = parent_of[r["level"]]
        if r["type"] in ("level_shift", "activity_shift"):
            # change points rarely land on the same day as their parent's — allow +/- 21 days
            d0 = pd.Timestamp(r["date"])
            pid = next((by_key[(plevel, fn(r["entity"]), (d0 + pd.Timedelta(days=k)).date().isoformat(), r["direction"])]
                        for k in range(-21, 22)
                        if (plevel, fn(r["entity"]), (d0 + pd.Timedelta(days=k)).date().isoformat(), r["direction"]) in by_key), None)
        else:
            pid = by_key.get((plevel, fn(r["entity"]), r["date"], r["direction"]))
        if pid is None and plevel == "global":
            pid = closure_ids.get(r["date"])
        if pid is None and r["type"] in ("level_shift", "activity_shift"):
            # a company-wide change (or the end of a data gap) explains the same change everywhere below it
            d0 = pd.Timestamp(r["date"])
            for k in range(-21, 22):
                day = (d0 + pd.Timedelta(days=k)).date().isoformat()
                pid = (by_key.get(("global", "ALL", day, r["direction"])) or by_key.get(("global", "ALL", day, "drop"))
                       if r["direction"] == "spike" else by_key.get(("global", "ALL", day, r["direction"])))
                if pid:
                    break
        if pid:
            r["parent_id"] = pid
    echo: dict[str, int] = {}
    for r in recs:
        if r["parent_id"]:
            echo[r["parent_id"]] = echo.get(r["parent_id"], 0) + 1
    for r in recs:
        if r["id"] in echo and r["type"] in ("point_spike", "point_drop"):
            r["n_children"] = echo[r["id"]]
            r["reason"] += f" [{echo[r['id']]} lower-level series echo this]"


def priority(r: dict) -> float:
    z = abs(r["z"]) if r["z"] is not None and np.isfinite(r["z"]) else 0.0
    mat = r["materiality"] if r["materiality"] is not None and np.isfinite(r["materiality"]) else 0.0
    base = {"critical": 3, "high": 2, "medium": 1, "low": 0.5, "info": 0.1}[r["severity"]]
    lvl = {"global": 3, "branch": 2, "category1": 2, "category2": 1.5, "branch_category": 1.2, "item": 1.0, "branch_item": 0.8}[r["level"]]
    demote = 0.4 if r.get("parent_id") else 1.0
    echoes = r.get("n_children", 0) if r["type"] in ("point_spike", "point_drop", "systemic_event") else 0
    boost = 1 + 0.15 * min(echoes, 20)
    duration = 1 + math.log1p(r.get("n_children", 0)) if r["type"] in ("unexpected_zero", "data_gap", "level_shift", "long_silence", "activity_shift") else 1.0
    return base * lvl * demote * boost * duration * (1 + math.log1p(z)) * ((1 + 10 * min(mat, 0.5)) if mat else 1)


OUTPUT_COLUMNS = ["id", "date", "end_date", "level", "entity", "entity_name", "type", "direction", "severity", "priority", "scope",
                  "actual", "expected", "lower", "upper", "ratio", "delta_mnt", "z", "z_peer", "materiality", "calendar_tag",
                  "recurring_annual", "parent_id", "n_children", "drivers", "reason"]
