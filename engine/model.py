"""Robust hierarchical baselines for daily sales series.

Every series (matrix row) is modelled on log1p(AMOUNT) of its *active* days as

    expected(t) = local level(t) + weekday effect + day-of-month effect + calendar-event effect

* local level  — leave-one-out median of the +/-H surrounding non-event days (the day itself is never
                 used, so a big day cannot mask itself; sparse series get a wider window automatically)
* weekday      — robust median offset per weekday
* day-of-month — robust median offset per day of month, kept only when statistically solid
* events       — per calendar tag ("WomensDay-1", "TsagaanSar+0", "Auto:12-27+0", …) the effect is
                 the leave-one-year-out median residual of the same tag in the OTHER years; a series
                 with no other year falls back to its parent's effect.  The year-to-year spread of the
                 tag is added to that day's sigma.
* sigma        — rolling MAD of the residual with a floor that cannot collapse for discrete series.

Change points are found separately on the weekly, calendar-adjusted, seasonally-adjusted series with
robust binary segmentation.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

warnings.filterwarnings("ignore", category=RuntimeWarning)

LEVELS = ["global", "branch", "category1", "category2", "branch_category", "item", "branch_item"]
LEVEL_LABEL = {"global": "Company total", "branch": "Branch", "category1": "Category 1", "category2": "Category 2",
               "branch_category": "Branch × Category 1", "item": "Item", "branch_item": "Branch × Item"}
PARENT_LEVEL = {"branch": "global", "category1": "global", "category2": "category1", "branch_category": "branch",
                "item": "category1", "branch_item": "branch"}
CHILD_LEVEL = {"global": "branch", "branch": "branch_category", "category1": "item", "category2": None,
               "branch_category": "branch_item", "item": "branch_item", "branch_item": None}


@dataclass
class ModelConfig:
    half_window: int = 14
    half_window_max: int = 90
    scale_window: int = 45
    min_neighbours: int = 8
    sigma_floor: float = 0.06
    causal: bool = False
    min_active_days: int = 60
    min_active_days_item: int = 90
    min_active_days_branch_item: int = 180
    min_coverage_branch_item: float = 0.5
    cp_z: float = 3.0              # jump / robust spread of the jump statistic for this series
    cp_min_log: float = math.log(1.3)
    cp_min_hold_weeks: int = 6     # the new level must persist at least this long
    cp_max_per_series: int = 6


# =========================================================================== panels
@dataclass
class Panel:
    level: str
    ids: list[str]
    amount: np.ndarray                     # (S, T) daily MNT; 0 = no sales
    parent_idx: np.ndarray | None = None   # index into the parent panel (effect inheritance / roll-up)
    driver_idx: dict = field(default_factory=dict)   # {parent_level: index array} for driver attribution


def build_panels(df: pd.DataFrame, index: pd.DatetimeIndex) -> tuple[dict[str, Panel], dict, dict]:
    """df has DATE, BRANCH_ID, CATEGORY_1_ID, CATEGORY_2_ID, ITEM_ID, AMOUNT (already validated)."""
    T = len(index)
    pos = pd.Series(np.arange(T), index=index)
    c2c1 = df.drop_duplicates("CATEGORY_2_ID").set_index("CATEGORY_2_ID")["CATEGORY_1_ID"].to_dict()
    i2c1 = df.drop_duplicates("ITEM_ID").set_index("ITEM_ID")["CATEGORY_1_ID"].to_dict()

    def pivot(keys: list[str], level: str) -> Panel:
        g = df.groupby(keys + ["DATE"], observed=True, sort=False)["AMOUNT"].sum().reset_index()
        ent = g[keys[0]].astype(str) if len(keys) == 1 else g[keys[0]].astype(str) + "|" + g[keys[1]].astype(str)
        codes, uniques = pd.factorize(ent, sort=True)
        M = np.zeros((len(uniques), T))
        np.add.at(M, (codes, pos.reindex(g["DATE"]).to_numpy()), g["AMOUNT"].to_numpy())
        return Panel(level, [str(u) for u in uniques], M)

    panels: dict[str, Panel] = {}
    total = np.zeros(T)
    np.add.at(total, pos.reindex(df["DATE"]).to_numpy(), df["AMOUNT"].to_numpy())
    panels["global"] = Panel("global", ["ALL"], total[None, :])
    panels["branch"] = pivot(["BRANCH_ID"], "branch")
    panels["category1"] = pivot(["CATEGORY_1_ID"], "category1")
    panels["category2"] = pivot(["CATEGORY_2_ID"], "category2")
    panels["branch_category"] = pivot(["BRANCH_ID", "CATEGORY_1_ID"], "branch_category")
    panels["item"] = pivot(["ITEM_ID"], "item")
    panels["branch_item"] = pivot(["BRANCH_ID", "ITEM_ID"], "branch_item")
    return panels, c2c1, i2c1


def select_dense(panel: Panel, min_days: int, min_cov: float) -> Panel:
    active = panel.amount > 0
    days = active.sum(axis=1)
    first = np.argmax(active, axis=1)
    last = panel.amount.shape[1] - 1 - np.argmax(active[:, ::-1], axis=1)
    span = np.maximum(last - first + 1, 1)
    keep = (days >= min_days) & (days / span >= min_cov)
    return Panel(panel.level, [i for i, k in zip(panel.ids, keep) if k], panel.amount[keep])


def link_panels(panels: dict[str, Panel], c2c1: dict, i2c1: dict) -> None:
    """Fill parent_idx (effect inheritance) and driver_idx (child -> parent attribution) AFTER density selection."""
    pos = {lvl: {k: i for i, k in enumerate(p.ids)} for lvl, p in panels.items()}

    def link(level: str, parent: str, fn) -> np.ndarray:
        return np.array([pos[parent].get(fn(u), -1) for u in panels[level].ids], dtype=int)

    panels["branch"].parent_idx = link("branch", "global", lambda u: "ALL")
    panels["category1"].parent_idx = link("category1", "global", lambda u: "ALL")
    panels["category2"].parent_idx = link("category2", "category1", lambda u: c2c1.get(u, ""))
    panels["branch_category"].parent_idx = link("branch_category", "branch", lambda u: u.split("|")[0])
    panels["item"].parent_idx = link("item", "category1", lambda u: i2c1.get(u, ""))
    panels["branch_item"].parent_idx = link("branch_item", "branch", lambda u: u.split("|")[0])
    # drivers: which parent level uses which index
    panels["branch"].driver_idx = {"global": panels["branch"].parent_idx}
    panels["item"].driver_idx = {"category1": panels["item"].parent_idx}
    panels["branch_category"].driver_idx = {"branch": panels["branch_category"].parent_idx}
    panels["branch_item"].driver_idx = {
        "branch": panels["branch_item"].parent_idx,
        "item": link("branch_item", "item", lambda u: u.split("|")[1]),
        "branch_category": link("branch_item", "branch_category", lambda u: u.split("|")[0] + "|" + i2c1.get(u.split("|")[1], "")),
    }


# =========================================================================== robust helpers
def loo_window_median(M: np.ndarray, half: int, min_count: int, causal: bool, chunk: int = 400,
                      max_half: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Leave-one-out median over +/-half (or the previous 2*half days if causal); NaNs ignored.
    Series most of whose own days cannot reach ``min_count`` neighbours are recomputed with a wider
    window (up to ``max_half``) so sparse burst-trading channels still get a baseline."""
    S, T = M.shape
    left, right = (2 * half, 0) if causal else (half, half)
    W = left + right + 1
    out = np.full((S, T), np.nan)
    cnt = np.zeros((S, T), dtype=np.int32)
    for s0 in range(0, S, chunk):
        block = M[s0:s0 + chunk]
        padded = np.pad(block, ((0, 0), (left, right)), constant_values=np.nan)
        win = sliding_window_view(padded, W, axis=1).copy()
        win[:, :, left] = np.nan
        c = np.isfinite(win).sum(axis=2)
        med = np.nanmedian(win, axis=2)
        med[c < min_count] = np.nan
        out[s0:s0 + chunk] = med
        cnt[s0:s0 + chunk] = c
    if max_half is not None and max_half > half and S:
        act = np.isfinite(M)
        ok_share = ((cnt >= min_count) & act).sum(axis=1) / np.maximum(act.sum(axis=1), 1)
        sparse = ok_share < 0.8
        if sparse.any():
            out2, cnt2 = loo_window_median(M[sparse], min(max_half, half * 2), min_count, causal, chunk, max_half)
            out[sparse] = out2
            cnt[sparse] = cnt2
    return out, cnt


def rolling_mad_sigma(R: np.ndarray, half: int, min_count: int, floor: float) -> np.ndarray:
    """max(1.4826*rolling median|r|, series q80|r|/1.2816, 0.5*series MAD sigma, floor).
    The q80 term keeps the scale from collapsing for discrete 'fixed order' series."""
    A = pd.DataFrame(np.abs(R).T)
    med = A.rolling(2 * half + 1, center=True, min_periods=min_count).median().to_numpy().T
    sigma = 1.4826 * med
    overall = 1.4826 * np.nanmedian(np.abs(R), axis=1)
    q80 = np.nanquantile(np.abs(R), 0.80, axis=1) / 1.2816
    overall = np.where(np.isfinite(overall), overall, floor)
    q80 = np.where(np.isfinite(q80), q80, floor)
    fallback = np.maximum.reduce([0.5 * overall, q80, np.full_like(q80, floor)])[:, None]
    return np.where(np.isfinite(sigma), np.maximum(sigma, fallback), fallback)


def group_median_effect(R: np.ndarray, groups: np.ndarray, n_groups: int, min_n: int, t_min: float | None) -> np.ndarray:
    S, T = R.shape
    eff = np.zeros((S, n_groups))
    for g in range(n_groups):
        cols = groups == g
        if not cols.any():
            continue
        block = R[:, cols]
        n = np.isfinite(block).sum(axis=1)
        med = np.nanmedian(block, axis=1)
        if t_min is not None:
            mad = 1.4826 * np.nanmedian(np.abs(block - med[:, None]), axis=1)
            se = 1.2533 * np.maximum(mad, 0.02) / np.sqrt(np.maximum(n, 1))
            med = np.where((np.abs(med) / se >= t_min) & (n >= min_n), med, 0.0)
        else:
            med = np.where(n >= min_n, med, 0.0)
        eff[:, g] = np.where(np.isfinite(med), med, 0.0)
    return eff[:, groups]


def event_effects(R: np.ndarray, tags: np.ndarray, years: np.ndarray, parent: np.ndarray | None,
                  parent_disp: np.ndarray | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Leave-one-year-out median residual per tag -> (effect, n_other_years, dispersion)."""
    S, T = R.shape
    eff = np.zeros((S, T)); disp = np.zeros((S, T)); nother = np.zeros((S, T), dtype=np.int16)
    for tag in np.unique(tags):
        if tag == "":
            continue
        cols = np.flatnonzero(tags == tag)
        block = R[:, cols]; yrs = years[cols]
        for j, c in enumerate(cols):
            others = block[:, yrs != yrs[j]]
            n = np.isfinite(others).sum(axis=1)
            if others.shape[1]:
                med = np.nanmedian(others, axis=1)
                dev = 1.4826 * np.nanmedian(np.abs(others - med[:, None]), axis=1)
                rng = (np.nanmax(others, axis=1) - np.nanmin(others, axis=1)) / 2.0
                d = np.where(n >= 3, dev, np.where(n == 2, rng, np.nan))
            else:
                med = np.full(S, np.nan); d = np.full(S, np.nan)
            e = np.where(n >= 1, med, np.nan)
            if parent is not None:
                e = np.where(n >= 1, e, parent[:, c])
                if parent_disp is not None:
                    d = np.where(np.isfinite(d), d, parent_disp[:, c])
            eff[:, c] = np.where(np.isfinite(e), e, 0.0)
            disp[:, c] = np.where(np.isfinite(d), d, 0.0)
            nother[:, c] = n
    return eff, nother, disp


# =========================================================================== scoring
@dataclass
class Scored:
    panel: Panel
    y: np.ndarray               # log1p amount on active days, NaN otherwise
    expected: np.ndarray        # log scale
    sigma: np.ndarray
    z: np.ndarray
    p_open: np.ndarray
    lifetime: np.ndarray
    first: np.ndarray
    weekday_eff: np.ndarray     # (S, 7)
    event_eff: np.ndarray
    event_nother: np.ndarray
    event_disp: np.ndarray
    scorable: np.ndarray
    resid: np.ndarray           # y - expected
    deseason: np.ndarray        # y - weekday - dom - event  (level + noise), NaN on event days
    changepoints: list = field(default_factory=list)   # filled by find_changepoints


def score_panel(panel: Panel, index: pd.DatetimeIndex, cal: pd.DataFrame, cfg: ModelConfig,
                parent: Scored | None = None) -> Scored:
    S, T = panel.amount.shape
    A = panel.amount
    active = A > 0
    y = np.where(active, np.log1p(A), np.nan)
    first = np.argmax(active, axis=1)
    last = T - 1 - np.argmax(active[:, ::-1], axis=1)
    ar = np.arange(T)[None, :]
    lifetime = (ar >= first[:, None]) & (ar <= last[:, None])

    is_event = cal["tag"].to_numpy() != ""
    dow = index.dayofweek.to_numpy(); dom = index.day.to_numpy() - 1
    years = index.year.to_numpy(); tags = cal["tag"].to_numpy()

    parent_eff = parent_disp = None
    if parent is not None and panel.parent_idx is not None:
        pi = np.maximum(panel.parent_idx, 0)
        has = (panel.parent_idx >= 0)[:, None]
        parent_eff = np.where(has, parent.event_eff[pi], 0.0)
        parent_disp = np.where(has, parent.event_disp[pi], 0.0)

    kw = dict(min_count=cfg.min_neighbours, causal=cfg.causal, max_half=cfg.half_window_max)
    y_m = np.where(is_event[None, :], np.nan, y)
    L0, _ = loo_window_median(y_m, cfg.half_window, **kw)
    r0 = np.where(is_event[None, :], np.nan, y - L0)
    wk = group_median_effect(r0, dow, 7, min_n=8, t_min=None)
    wk_tab = np.zeros((S, 7))
    for d in range(7):
        col = np.flatnonzero(dow == d)
        wk_tab[:, d] = wk[:, col[0]] if len(col) else 0.0

    y1 = y - wk
    L1, _ = loo_window_median(np.where(is_event[None, :], np.nan, y1), cfg.half_window, **kw)
    r1 = np.where(is_event[None, :], np.nan, y1 - L1)
    dm = group_median_effect(r1, dom, 31, min_n=24, t_min=3.0)

    y2 = y1 - dm
    L2, _ = loo_window_median(np.where(is_event[None, :], np.nan, y2), cfg.half_window, **kw)
    r2 = y2 - L2
    ev, nother, ev_disp = event_effects(r2, tags, years, parent_eff, parent_disp)

    expected = L2 + wk + dm + ev
    resid = y - expected
    sigma = rolling_mad_sigma(np.where(is_event[None, :], np.nan, resid), cfg.scale_window, 20, cfg.sigma_floor)
    sigma = np.sqrt(sigma ** 2 + ev_disp ** 2)
    z = resid / sigma
    scorable = np.isfinite(z) & lifetime

    # open probability: share of the PRECEDING 8 same weekdays on which the series was active
    # (past-only on purpose: at the start of a long gap the future zeros must not lower it)
    o = np.where(lifetime, active.astype(float), np.nan)
    p_open = np.full((S, T), np.nan)
    for d in range(7):
        cols = np.flatnonzero(dow == d)
        sub = o[:, cols]
        padded = np.pad(sub, ((0, 0), (8, 0)), constant_values=np.nan)
        win = sliding_window_view(padded, 9, axis=1).copy()
        win[:, :, 8] = np.nan                     # exclude the day itself
        pm = np.nanmean(win, axis=2)
        pm[np.isfinite(win).sum(axis=2) < 5] = np.nan
        p_open[:, cols] = pm

    deseason = np.where(is_event[None, :], np.nan, y - wk - dm - ev)
    return Scored(panel, y, expected, sigma, z, p_open, lifetime, first, wk_tab, ev, nother, ev_disp, scorable, resid, deseason)


# =========================================================================== change points
def find_changepoints(sc: Scored, index: pd.DatetimeIndex, cfg: ModelConfig) -> list[dict]:
    """Level changes on the weekly, calendar-adjusted series.

    jump(k) = median(x[k : k+8 weeks]) - median(x[k-8 : k])   (>= 5 valid weeks each side)
    minus the median of the same statistic at the same week of the OTHER years (recurring seasonal
    transitions such as the January slump are not level changes), scaled by the robust spread of the
    statistic itself for that series (no independence assumption).  Local maxima above cp_z with an
    effect >= cp_min_log are reported, together with how long the new level held."""
    S, T = sc.deseason.shape
    nW = T // 7
    H = 8
    if nW < 3 * H:
        return []
    D = sc.deseason[:, :nW * 7].reshape(S, nW, 7)
    W = np.nanmedian(D, axis=2)
    W[np.isfinite(D).sum(axis=2) < 3] = np.nan
    A_raw = sc.panel.amount[:, :nW * 7].reshape(S, nW, 7)
    W_raw = np.nanmedian(np.where(A_raw > 0, A_raw, np.nan), axis=2)

    Wdf = pd.DataFrame(W.T)
    before = Wdf.rolling(H, min_periods=5).median().shift(1).to_numpy().T           # weeks [k-8, k-1]
    after = Wdf[::-1].rolling(H, min_periods=5).median()[::-1].to_numpy().T          # weeks [k, k+7]
    jump = after - before
    stack = []
    for k in (-3, -2, -1, 1, 2, 3):
        for dd in (-1, 0, 1):
            off = 52 * k + dd
            sh = np.full_like(jump, np.nan)
            if off > 0:
                sh[:, off:] = jump[:, :-off]
            elif off < 0:
                sh[:, :off] = jump[:, -off:]
            stack.append(sh)
    stack = np.stack(stack)
    seasonal = np.where(np.isfinite(stack).sum(axis=0) >= 4, np.nanmedian(stack, axis=0), 0.0)
    adj = jump - seasonal
    center = np.nanmedian(adj, axis=1, keepdims=True)
    scale = 1.4826 * np.nanmedian(np.abs(adj - center), axis=1, keepdims=True)
    n_ok = np.isfinite(adj).sum(axis=1, keepdims=True)
    scale = np.where(n_ok >= 40, scale, np.nan)
    pooled = float(np.nanmedian(scale)) if np.isfinite(scale).any() else cfg.sigma_floor   # level-wide fallback for short series
    scale = np.maximum(np.where(np.isfinite(scale), scale, pooled), cfg.sigma_floor / 2)
    tstat = adj / scale
    first_week = sc.first // 7
    recs = []
    for s in range(S):
        ts = tstat[s]; ok = np.isfinite(ts) & (np.abs(ts) >= cfg.cp_z) & (np.abs(adj[s]) >= cfg.cp_min_log)
        if not ok.any():
            continue
        cand = np.flatnonzero(ok)
        cand = cand[np.argsort(-np.abs(ts[cand]))]
        taken: list[int] = []
        for k in cand:
            if k - first_week[s] < H + 4:          # 'before' window inside the series' own start-up ramp
                continue
            if all(abs(k - u) > H for u in taken):
                taken.append(int(k))
            if len(taken) >= cfg.cp_max_per_series:
                break
        for k in sorted(taken):
            old = before[s, k]; new = after[s, k]
            if not (np.isfinite(old) and np.isfinite(new)):
                continue
            # persistence: weeks after k while the 4-week median stays beyond the midpoint
            mid = old + 0.5 * (new - old)
            held = 0
            for j in range(k, nW - 3):
                m4 = np.nanmedian(W[s, j:j + 4])
                if not np.isfinite(m4) or (new > old and m4 < mid) or (new < old and m4 > mid):
                    break
                held += 1
            held = max(held, 1)
            if held < cfg.cp_min_hold_weeks and k + 4 < nW:      # transient (allow the tail of the series)
                continue
            recs.append({"s": s, "t": int(k * 7), "shift_log": float(adj[s, k]), "t_stat": float(ts[k]),
                         "before_raw": float(np.nanmedian(W_raw[s, max(0, k - H):k])) if np.isfinite(W_raw[s, max(0, k - H):k]).any() else np.nan,
                         "after_raw": float(np.nanmedian(W_raw[s, k:k + H])) if np.isfinite(W_raw[s, k:k + H]).any() else np.nan,
                         "seasonal_log": float(seasonal[s, k]), "weeks_after": int(held)})
    return recs


def find_activity_shifts(sc: Scored, cfg: ModelConfig, H: int = 8, min_delta: float = 0.3, hold_weeks: int = 6) -> list[dict]:
    """Changes in HOW OFTEN a series trades (share of active days), independent of the amount model.
    share(k) over 8 weeks after vs 8 weeks before; |delta| >= min_delta and the new rate must persist."""
    S, T = sc.panel.amount.shape
    nW = T // 7
    if nW < 3 * H:
        return []
    act = ((sc.panel.amount > 0) & sc.lifetime)[:, :nW * 7].reshape(S, nW, 7).astype(float)
    life = sc.lifetime[:, :nW * 7].reshape(S, nW, 7)
    W = np.where(life.sum(axis=2) >= 4, act.sum(axis=2) / np.maximum(life.sum(axis=2), 1), np.nan)
    Wdf = pd.DataFrame(W.T)
    before = Wdf.rolling(H, min_periods=5).mean().shift(1).to_numpy().T
    after = Wdf[::-1].rolling(H, min_periods=5).mean()[::-1].to_numpy().T
    jump = after - before
    first_week = sc.first // 7
    recs = []
    for s in range(S):
        j = jump[s]
        ok = np.isfinite(j) & (np.abs(j) >= min_delta) & (before[s] >= 0.15) | (np.isfinite(j) & (j >= min_delta))
        if not ok.any():
            continue
        cand = np.flatnonzero(ok); cand = cand[np.argsort(-np.abs(j[cand]))]
        taken: list[int] = []
        for k in cand:
            if k - first_week[s] < H + 4:
                continue
            if all(abs(k - u) > H for u in taken):
                taken.append(int(k))
            if len(taken) >= 4:
                break
        for k in sorted(taken):
            old, new = before[s, k], after[s, k]
            mid = old + 0.5 * (new - old); held = 0
            for q in range(k, nW - 3):
                m4 = np.nanmean(W[s, q:q + 4])
                if not np.isfinite(m4) or (new > old and m4 < mid) or (new < old and m4 > mid):
                    break
                held += 1
            if held < hold_weeks and k + 4 < nW:
                continue
            recs.append({"s": s, "t": int(k * 7), "before": float(old), "after": float(new), "weeks_after": int(max(held, 1))})
    return recs
