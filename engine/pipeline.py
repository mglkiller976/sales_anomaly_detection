"""End-to-end run: input file -> validated frame -> scored panels -> anomaly table -> saved run folder."""
from __future__ import annotations

import hashlib
import io
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from . import calendar as calmod
from .detect import (DetectConfig, Detector, OUTPUT_COLUMNS, calibrate_thresholds, company_closures, data_gaps, lifecycle_events,
                     priority, repeated_days, roll_up, systemic_events, unusual_mix)
from .model import LEVELS, LEVEL_LABEL, PARENT_LEVEL, CHILD_LEVEL, ModelConfig, Scored, build_panels, find_changepoints, link_panels, score_panel, select_dense

ENGINE_VERSION = "hier-robust-v2"
REQUIRED = ["DATE", "BRANCH_ID", "CATEGORY_1_ID", "CATEGORY_2_ID", "ITEM_ID", "AMOUNT"]


@dataclass
class RunConfig:
    calendar_preset: str = "mongolia"        # mongolia | none
    auto_events: bool = True                 # discover recurring month-days from the data
    sensitivity: str = "medium"              # low | medium | high
    causal: bool = False
    custom_events: pd.DataFrame | None = None
    model: ModelConfig = field(default_factory=ModelConfig)
    detect: DetectConfig = field(default_factory=DetectConfig)

    def to_json(self) -> dict:
        d = {"calendar_preset": self.calendar_preset, "auto_events": self.auto_events, "sensitivity": self.sensitivity,
             "causal": self.causal, "model": asdict(self.model), "detect": asdict(self.detect),
             "custom_events": None if self.custom_events is None else self.custom_events.to_dict(orient="records")}
        return d


# ---------------------------------------------------------------------------- input
def load_input(source, name: str = "") -> pd.DataFrame:
    """Read CSV / parquet (path, bytes or file-like) in the expected sales format and validate it.
    Column names are matched case-insensitively; DATE is parsed; ids are strings; AMOUNT float."""
    if isinstance(source, (str, Path)):
        p = Path(source); name = name or p.name
        if p.suffix.lower() in (".parquet", ".pq"):
            df = pd.read_parquet(p)
        else:
            df = pd.read_csv(p, dtype=str, engine="pyarrow") if p.stat().st_size > 5e6 else pd.read_csv(p, dtype=str)
    else:
        raw = source.read() if hasattr(source, "read") else source
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        if name.lower().endswith((".parquet", ".pq")) or raw[:4] == b"PAR1":
            df = pd.read_parquet(io.BytesIO(raw))
        else:
            comp = "gzip" if name.lower().endswith(".gz") or raw[:2] == b"\x1f\x8b" else None
            df = pd.read_csv(io.BytesIO(raw), dtype=str, compression=comp)
    df.columns = [str(c).strip().upper() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns {missing}; expected {REQUIRED}")
    df = df[REQUIRED].copy()
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    for c in ["BRANCH_ID", "CATEGORY_1_ID", "CATEGORY_2_ID", "ITEM_ID"]:
        df[c] = df[c].fillna("UNKNOWN").astype(str).str.strip()
        df.loc[df[c].isin(["", "nan", "None", "NaN", "<NA>", "null", "NULL"]), c] = "UNKNOWN"
    df["AMOUNT"] = pd.to_numeric(df["AMOUNT"], errors="coerce")
    before_drop = len(df)
    df = df.dropna(subset=["DATE", "AMOUNT"])
    dropped = before_drop - len(df)
    df.attrs["dropped_rows"] = dropped
    if df.empty:
        raise ValueError("no valid rows after parsing")
    df["DATE"] = df["DATE"].dt.normalize()
    neg = int((df["AMOUNT"] < 0).sum())
    df.attrs["negative_rows"] = neg
    # aggregate defensively in case the input is line-level
    before = len(df)
    df = df.groupby(REQUIRED[:-1], observed=True, sort=False, as_index=False)["AMOUNT"].sum()
    df.attrs["aggregated_from"] = before
    df = df.sort_values(REQUIRED[:-1], kind="mergesort", ignore_index=True)
    return df


def fingerprint(df: pd.DataFrame) -> str:
    h = hashlib.sha1()
    h.update(str(len(df)).encode()); h.update(str(float(df["AMOUNT"].sum())).encode())
    h.update(str(df["DATE"].min()).encode()); h.update(str(df["DATE"].max()).encode())
    h.update(str(df["BRANCH_ID"].nunique()).encode()); h.update(str(df["ITEM_ID"].nunique()).encode())
    return h.hexdigest()[:12]


def describe_input(df: pd.DataFrame) -> dict:
    daily = df.groupby("DATE")["AMOUNT"].sum()
    return {"rows": int(len(df)), "date_min": df["DATE"].min().date().isoformat(), "date_max": df["DATE"].max().date().isoformat(),
            "days": int(daily.shape[0]), "calendar_days": int((df["DATE"].max() - df["DATE"].min()).days + 1),
            "amount_total": float(df["AMOUNT"].sum()), "median_day": float(daily.median()),
            "branches": int(df["BRANCH_ID"].nunique()), "category1": int(df["CATEGORY_1_ID"].nunique()),
            "category2": int(df["CATEGORY_2_ID"].nunique()), "items": int(df["ITEM_ID"].nunique()),
            "dropped_rows": int(df.attrs.get("dropped_rows", 0)), "negative_rows": int(df.attrs.get("negative_rows", 0)),
            "aggregated_from": int(df.attrs.get("aggregated_from", len(df)))}


def load_names(data_dir: Path) -> dict:
    names = {"item": {}, "branch": {}}
    p = data_dir / "item_dictionary.csv"
    if p.exists():
        d = pd.read_csv(p, dtype=str, encoding="utf-8-sig")
        names["item"] = dict(zip(d["ITEM_ID"], "[" + d["ITEM_CODE"] + "] " + d["ITEM_NAME"]))
        names["item_cat"] = dict(zip(d["ITEM_ID"], d["CATEGORY_1_ID"]))
    p = data_dir / "branch_names.csv"
    if p.exists():
        d = pd.read_csv(p, dtype=str, encoding="utf-8-sig")
        if {"BRANCH_ID", "BRANCH_NAME"}.issubset(d.columns):
            names["branch"] = dict(zip(d["BRANCH_ID"], d["BRANCH_NAME"]))
    return names


# ---------------------------------------------------------------------------- results
@dataclass
class Results:
    anomalies: pd.DataFrame
    scored: dict[str, Scored]
    index: pd.DatetimeIndex
    cal: pd.DataFrame
    summary: dict
    calendar_effects: pd.DataFrame
    auto_events: pd.DataFrame
    names: dict


def _calendar_effects(scored: dict[str, Scored], cal: pd.DataFrame) -> pd.DataFrame:
    rows = []
    tags = cal["tag"].to_numpy()
    for level in ["global", "branch", "category1"]:
        sc = scored[level]
        for tag in sorted(set(tags) - {""}):
            cols = np.flatnonzero(tags == tag)
            for s, key in enumerate(sc.panel.ids):
                yv = sc.y[s, cols]; ok = np.isfinite(yv)
                if ok.sum() == 0:
                    continue
                rows.append({"level": level, "entity": key, "tag": tag, "event": tag.rsplit("+", 1)[0].rsplit("-", 1)[0] if not tag.startswith("Auto") else tag.split("+")[0],
                             "years_observed": int(ok.sum()), "multiplier": float(np.exp(np.nanmedian(sc.event_eff[s, cols][ok])))})
    return pd.DataFrame(rows)


def run(df: pd.DataFrame, cfg: RunConfig, names: dict | None = None, progress: Callable[[float, str], None] | None = None) -> Results:
    t0 = time.time()
    names = names or {"item": {}, "branch": {}}
    prog = progress or (lambda f, m: None)
    prog(0.02, "building daily panels")
    index = pd.date_range(df["DATE"].min(), df["DATE"].max(), freq="D")
    panels, c2c1, i2c1 = build_panels(df, index)
    m = cfg.model; m.causal = cfg.causal
    d = cfg.detect; d.sensitivity = cfg.sensitivity
    T = len(index)
    scale_days = lambda d: int(min(d, max(20, 0.4 * T)))          # short files: scale the density bar to the span
    universe = {k: len(p.ids) for k, p in panels.items()}
    panels["branch_category"] = select_dense(panels["branch_category"], scale_days(m.min_active_days), 0.0)
    panels["item"] = select_dense(panels["item"], scale_days(m.min_active_days_item), 0.0)
    panels["branch_item"] = select_dense(panels["branch_item"], scale_days(m.min_active_days_branch_item), m.min_coverage_branch_item)
    link_panels(panels, c2c1, i2c1)

    # calendar: preset + custom, then discover recurring month-days from the company residual
    cal = calmod.build_calendar(index, cfg.calendar_preset, cfg.custom_events)
    auto = pd.DataFrame(columns=["month_day", "effect_log", "multiplier", "years", "sign_agreement"])
    if cfg.auto_events and (index[-1] - index[0]).days >= 3 * 365:
        prog(0.05, "discovering recurring calendar days")
        g0 = score_panel(panels["global"], index, cal, m)
        auto = calmod.discover_recurring_days(index, cal, g0.resid[0])
        cal = calmod.add_auto_events(cal, index, auto)

    scored: dict[str, Scored] = {}
    weights = {"global": 0.02, "branch": 0.04, "category1": 0.02, "category2": 0.03, "branch_category": 0.08, "item": 0.10, "branch_item": 0.45}
    done = 0.06
    for level in LEVELS:
        prog(done, f"scoring {LEVEL_LABEL[level]} ({len(panels[level].ids)} series)")
        parent = scored.get(PARENT_LEVEL.get(level, ""), None)
        scored[level] = score_panel(panels[level], index, cal, m, parent)
        if level in ("global", "branch", "category1", "category2", "item"):
            scored[level].changepoints = find_changepoints(scored[level], index, m)
        done += weights[level]
    prog(0.82, "extracting anomalies")

    global_amount = panels["global"].amount[0]
    det = Detector(d, index, cal, names, global_amount)
    thresholds, clipped = calibrate_thresholds(scored, d)
    det.thresholds = thresholds
    branch_active_share = (panels["branch"].amount > 0).sum(axis=0) / np.maximum(scored["branch"].lifetime.sum(axis=0), 1)
    recs: list[dict] = []
    per_level = {}
    for level in LEVELS:
        sc = scored[level]
        ch = scored[CHILD_LEVEL[level]] if CHILD_LEVEL[level] else None
        pts = det.point_anomalies(sc, ch, thresholds[level])
        zs = det.zero_episodes(sc, branch_active_share) if level != "global" else []
        ls = det.level_shifts(sc, sc.changepoints) if sc.changepoints else []
        acts = det.activity_shifts(sc) if level in ("branch", "item") else []
        per_level[level] = {"point": len(pts), "zero": len(zs), "shift": len(ls), "activity": len(acts)}
        recs += pts + zs + ls + acts
    closures = company_closures(det, panels, scored, branch_active_share)
    dark = {r["date"] for r in closures}
    closure_ids = {r["date"]: r["id"] for r in closures}
    recs = [r for r in recs if not (r["date"] in dark and r["level"] != "global")]
    recs = [r for r in recs if not (r["date"] in dark and r["level"] == "global" and r["type"].startswith("point_"))]
    recs += closures
    recs += systemic_events(det, recs, scored)
    recs += data_gaps(det, recs, scored)
    roll_up(recs, c2c1, i2c1, closure_ids)
    already = {(r["entity"], r["date"]) for r in recs if r["level"] == "branch"}
    prog(0.9, "pattern detectors (repeated days, category mix, lifecycle)")
    recs += repeated_days(det, df)
    recs += unusual_mix(det, panels, scored, already)
    recs += lifecycle_events(det, scored["item"])
    recs += lifecycle_events(det, scored["branch"], long_silence_days=30, existing=recs)
    for r in recs:
        r["priority"] = priority(r)
    if recs:
        anoms = pd.DataFrame(recs)
        if d.max_per_series:
            anoms = anoms.sort_values("priority", ascending=False).groupby(["level", "entity"], group_keys=False).head(d.max_per_series)
        anoms = anoms.sort_values(["priority", "date"], ascending=[False, True]).reset_index(drop=True)
        anoms = anoms[OUTPUT_COLUMNS]
    else:
        anoms = pd.DataFrame(columns=OUTPUT_COLUMNS)

    prog(0.95, "summaries")
    coverage = {}
    for level in ["global", "branch", "category1", "category2"]:
        sc = scored[level]
        active = (sc.panel.amount > 0) & sc.lifetime
        cov = (sc.scorable & active).sum(axis=1) / np.maximum(active.sum(axis=1), 1)
        coverage[level] = {k: round(float(c), 3) for k, c in zip(sc.panel.ids, cov)}
    eff = _calendar_effects(scored, cal)
    summary = {
        "engine": ENGINE_VERSION, "generated_at": pd.Timestamp.now(tz="UTC").isoformat(), "elapsed_seconds": round(time.time() - t0, 1),
        "config": cfg.to_json(), "thresholds": {k: round(v, 2) for k, v in thresholds.items()}, "thresholds_clipped": clipped,
        "data": describe_input(df) | {"fingerprint": fingerprint(df), "series_scored": {k: len(v.ids) for k, v in panels.items()},
                                     "series_universe": universe,
                                     "calendar_event_days": int((cal["tag"] != "").sum()), "auto_events": int(len(auto))},
        "counts": {"total": int(len(anoms)), "by_severity": anoms["severity"].value_counts().to_dict(),
                   "by_type": anoms["type"].value_counts().to_dict(), "by_level": anoms["level"].value_counts().to_dict(),
                   "per_level_raw": per_level},
        "coverage": {"share_of_active_days_scorable": coverage,
                     "below_50pct": [f"{l}:{k} {c:.0%}" for l, dd in coverage.items() for k, c in dd.items() if c < 0.5]},
    }
    prog(1.0, "done")
    return Results(anoms, scored, index, cal, summary, eff, auto, names)


# ---------------------------------------------------------------------------- persistence
def save_run(res: Results, out_dir: Path, name: str = "", source: dict | None = None) -> Path:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    res.anomalies.to_parquet(out_dir / "anomalies.parquet", index=False)
    res.anomalies.to_csv(out_dir / "anomalies.csv", index=False, encoding="utf-8-sig", float_format="%.4f")
    res.calendar_effects.to_csv(out_dir / "calendar_effects.csv", index=False)
    res.auto_events.to_csv(out_dir / "auto_events.csv", index=False)
    cal = res.cal.reset_index().rename(columns={"index": "date"})
    cal.to_csv(out_dir / "calendar.csv", index=False)
    meta = dict(res.summary); meta["name"] = name or out_dir.name
    meta["dates"] = [res.index[0].date().isoformat(), res.index[-1].date().isoformat()]
    meta["source"] = source or {}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out_dir / "names.json").write_text(json.dumps(res.names, ensure_ascii=False), encoding="utf-8")
    sdir = out_dir / "series"; sdir.mkdir(exist_ok=True)
    for level, sc in res.scored.items():
        np.savez_compressed(sdir / f"{level}.npz", amount=sc.panel.amount.astype(np.float32), expected=sc.expected.astype(np.float32),
                            sigma=sc.sigma.astype(np.float16), p_open=sc.p_open.astype(np.float16), lifetime=sc.lifetime,
                            first=sc.first, weekday_eff=sc.weekday_eff.astype(np.float32), z=sc.z.astype(np.float16))
        (sdir / f"{level}.ids.json").write_text(json.dumps({"ids": sc.panel.ids, "parent_idx": None if sc.panel.parent_idx is None else sc.panel.parent_idx.tolist()}), encoding="utf-8")
    from .report import write_report
    write_report(res, out_dir)
    return out_dir


class SeriesStore:
    """Lazy reader for a saved run's series (used by the app)."""

    def __init__(self, run_dir: Path):
        self.dir = Path(run_dir) / "series"
        self._cache: dict[str, dict] = {}
        self._ids: dict[str, list[str]] = {}

    def levels(self) -> list[str]:
        return [p.stem for p in sorted(self.dir.glob("*.npz"))]

    def ids(self, level: str) -> list[str]:
        if level not in self._ids:
            p = self.dir / f"{level}.ids.json"
            self._ids[level] = json.loads(p.read_text(encoding="utf-8"))["ids"] if p.exists() else []
        return self._ids[level]

    def _load(self, level: str) -> dict:
        if level not in self._cache:
            z = np.load(self.dir / f"{level}.npz")
            self._cache[level] = {k: z[k] for k in z.files}
        return self._cache[level]

    def series(self, level: str, entity: str) -> dict | None:
        ids = self.ids(level)
        if entity not in ids:
            return None
        s = ids.index(entity); d = self._load(level)
        return {k: (v[s].astype(float) if v.ndim == 2 else v[s]) for k, v in d.items()}

    def matrix(self, level: str, key: str) -> np.ndarray:
        return self._load(level)[key]


def load_run(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    anoms = pd.read_parquet(run_dir / "anomalies.parquet")
    cal = pd.read_csv(run_dir / "calendar.csv", parse_dates=["date"]).set_index("date")
    cal["tag"] = cal["tag"].fillna(""); cal["event"] = cal["event"].fillna("")
    eff = pd.read_csv(run_dir / "calendar_effects.csv") if (run_dir / "calendar_effects.csv").exists() else pd.DataFrame()
    auto = pd.read_csv(run_dir / "auto_events.csv") if (run_dir / "auto_events.csv").exists() else pd.DataFrame()
    names = json.loads((run_dir / "names.json").read_text(encoding="utf-8")) if (run_dir / "names.json").exists() else {"item": {}, "branch": {}}
    index = pd.date_range(meta["dates"][0], meta["dates"][1], freq="D")
    return {"meta": meta, "anomalies": anoms, "cal": cal, "effects": eff, "auto": auto, "names": names, "index": index,
            "store": SeriesStore(run_dir), "dir": run_dir}
