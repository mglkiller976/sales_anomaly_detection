"""Synthetic-injection benchmark: plant known anomalies into a real dataset and measure recall.

    python -m engine.evaluate data/demo_sales.parquet  [--n 40] [--seed 7]

For a random set of (branch, date) pairs on ordinary days it injects
  * spikes  (branch-day × 3)      * drops (branch-day × 0.3)
  * outages (branch dark for 3 and for 10 days)
  * level shifts (branch × 0.6 for 10 weeks)
then runs the engine on the modified data and checks whether each planted event is reported at
branch level (or rolled up into a systemic / data-gap record).  Prints recall per type and the
number of extra branch-level records compared with the untouched data (false-alarm inflation).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import RunConfig, load_input, run  # noqa: E402
from engine.calendar import build_calendar  # noqa: E402


def choose_days(df: pd.DataFrame, n: int, rng: np.random.Generator, min_share: float = 0.005) -> list[tuple[str, pd.Timestamp]]:
    """Ordinary days: branch trading on that day, not a calendar day, not within 60 days of the branch's first day."""
    index = pd.date_range(df["DATE"].min(), df["DATE"].max(), freq="D")
    cal = build_calendar(index, "mongolia")
    tagged = set(cal.index[cal["tag"] != ""])
    tot = df.groupby("DATE")["AMOUNT"].sum()
    bd = df.groupby(["BRANCH_ID", "DATE"])["AMOUNT"].sum().reset_index()
    first = bd.groupby("BRANCH_ID")["DATE"].min()
    bd = bd[bd["AMOUNT"] >= min_share * tot.median()]
    bd = bd[~bd["DATE"].isin(tagged)]
    bd = bd[bd["DATE"] >= bd["BRANCH_ID"].map(first) + pd.Timedelta(days=60)]
    bd = bd[bd["DATE"] <= index[-1] - pd.Timedelta(days=80)]
    pick = bd.sample(n=n, random_state=int(rng.integers(1e9)))
    return list(zip(pick["BRANCH_ID"], pick["DATE"]))


def inject(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    d = df.copy()
    key = d["BRANCH_ID"] + "|" + d["DATE"].dt.strftime("%Y-%m-%d")
    for kind, items in plan.items():
        for b, day in items:
            if kind == "spike":
                d.loc[key == f"{b}|{day:%Y-%m-%d}", "AMOUNT"] *= 3.0
            elif kind == "drop":
                d.loc[key == f"{b}|{day:%Y-%m-%d}", "AMOUNT"] *= 0.3
            elif kind.startswith("outage"):
                n = int(kind.split("_")[1])
                days = pd.date_range(day, periods=n)
                d = d[~((d["BRANCH_ID"] == b) & d["DATE"].isin(days))]
                key = d["BRANCH_ID"] + "|" + d["DATE"].dt.strftime("%Y-%m-%d")
            elif kind == "shift":
                days = pd.date_range(day, periods=70)
                d.loc[(d["BRANCH_ID"] == b) & d["DATE"].isin(days), "AMOUNT"] *= 0.6
    return d


def evaluate(df: pd.DataFrame, n: int = 40, seed: int = 7, sensitivity: str = "medium") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    kinds = ["spike", "drop", "outage_3", "outage_10", "shift"]
    picks = choose_days(df, n * len(kinds), rng)
    plan = {k: picks[i * n:(i + 1) * n] for i, k in enumerate(kinds)}
    base = run(df, RunConfig(sensitivity=sensitivity, auto_events=False)).anomalies
    inj = run(inject(df, plan), RunConfig(sensitivity=sensitivity, auto_events=False)).anomalies
    br_inj = inj[inj["level"] == "branch"]
    gaps = inj[inj["type"] == "data_gap"]

    def span(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        s0 = pd.to_datetime(frame["date"])
        s1 = pd.to_datetime(frame["end_date"].replace("", np.nan)).fillna(s0)
        return s0, s1

    rows = []
    for kind, items in plan.items():
        hit = 0
        for b, day in items:
            a = br_inj[br_inj["entity"] == b]
            d0 = pd.Timestamp(day)
            if kind in ("spike", "drop"):
                typ = "point_spike" if kind == "spike" else "point_drop"
                ok = ((a["type"] == typ) & (pd.to_datetime(a["date"]).sub(d0).abs().dt.days <= 1)).any()
            elif kind.startswith("outage"):
                # a hit is ANY reported silence for this branch overlapping the window we blanked out —
                # the engine may start the episode a day or two in, or roll it into a company-wide data gap
                d1 = d0 + pd.Timedelta(days=int(kind.split("_")[1]) - 1)
                z = a[a["type"].isin(["unexpected_zero", "long_silence"])]
                s0, s1 = span(z)
                ok = ((s0 <= d1) & (s1 >= d0)).any()
                if not ok and len(gaps):
                    g = gaps[gaps["drivers"].str.contains(f'"{b}"', na=False, regex=False)]
                    if len(g):
                        g0, g1 = span(g)
                        ok = ((g0 <= d1) & (g1 >= d0)).any()
            else:
                z = a[a["type"].isin(["level_shift", "activity_shift"])]
                ok = (pd.to_datetime(z["date"]).sub(d0).abs().dt.days <= 21).any()
            hit += bool(ok)
        rows.append({"type": kind, "planted": len(items), "found": hit, "recall": hit / len(items)})
    res = pd.DataFrame(rows)
    b0 = base[base["level"] == "branch"]; b1 = br_inj
    res.attrs["branch_records_base"] = int(len(b0)); res.attrs["branch_records_injected"] = int(len(b1))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("data"); ap.add_argument("--n", type=int, default=40); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--sensitivity", default="medium")
    a = ap.parse_args()
    df = load_input(Path(a.data))
    res = evaluate(df, a.n, a.seed, a.sensitivity)
    print(res.to_string(index=False))
    print(f"branch-level records: baseline {res.attrs['branch_records_base']}, with injections {res.attrs['branch_records_injected']} "
          f"(planted {res['planted'].sum()})")
