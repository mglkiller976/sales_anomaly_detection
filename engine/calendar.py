"""Calendar of special days: built-in Mongolian holidays, user-supplied events and
data-driven recurring days discovered from the series themselves."""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------- built-in presets
# Lunar-based holidays (Tsagaan Sar verified against the data: the three all-closed dates in the
# bundled extract are exactly Tsagaan Sar day 1 of 2022, 2023 and 2025).
TSAGAAN_SAR = {2020: "2020-02-24", 2021: "2021-02-12", 2022: "2022-02-02", 2023: "2023-02-21", 2024: "2024-02-10",
               2025: "2025-03-01", 2026: "2026-02-18", 2027: "2027-02-07", 2028: "2028-01-27", 2029: "2029-02-14",
               2030: "2030-02-03"}
CHINGGIS_DAY = {2020: "2020-11-16", 2021: "2021-11-05", 2022: "2022-11-24", 2023: "2023-11-14", 2024: "2024-11-02",
                2025: "2025-11-20", 2026: "2026-11-09", 2027: "2027-10-30", 2028: "2028-11-17", 2029: "2029-11-06"}

# (name, month, day, days before, days after)
MONGOLIA_FIXED = [
    ("NewYear", 1, 1, 9, 3),           # Dec 23 .. Jan 4: pre-holiday ramp, Christmas/NYE cake rush, then closure days
    ("ValentinesDay", 2, 14, 1, 0),
    ("WomensDay", 3, 8, 3, 1),
    ("SoldiersDay", 3, 18, 1, 0),
    ("ChildrensDay", 6, 1, 2, 1),
    ("Naadam", 7, 11, 2, 4),           # Jul 9 .. Jul 15
    ("AcademicYear", 9, 1, 1, 1),
    ("EldersDay", 10, 1, 1, 0),
    ("RepublicDay", 11, 26, 0, 0),
    ("IndependenceDay", 12, 29, 0, 0),
]
MONGOLIA_LUNAR = [
    ("TsagaanSar", TSAGAAN_SAR, 3, 4, 2),      # eve rush, 3 closed-ish days, recovery; holiday days 0..2
    ("ChinggisKhaanDay", CHINGGIS_DAY, 0, 0, 0),
]
EVENT_PRIORITY = ["TsagaanSar", "NewYear", "WomensDay", "ChildrensDay", "Naadam", "SoldiersDay", "ValentinesDay",
                  "AcademicYear", "EldersDay", "ChinggisKhaanDay", "RepublicDay", "IndependenceDay"]

PRESETS = {"mongolia": "Mongolia (Tsagaan Sar, Naadam, Women's / Children's Day, New Year window, …)",
           "none": "No built-in holidays (learn recurring days from the data only)"}


def _rows_for_preset(preset: str, years: range) -> list[tuple]:
    rows: list[tuple] = []
    if preset == "mongolia":
        for name, month, day, before, after in MONGOLIA_FIXED:
            for y in years:
                base = pd.Timestamp(year=y, month=month, day=day)
                for off in range(-before, after + 1):
                    rows.append((base + pd.Timedelta(days=off), name, off, off == 0))
        for name, table, before, after, hol_days in MONGOLIA_LUNAR:
            for y, d in table.items():
                if y not in years:
                    continue
                base = pd.Timestamp(d)
                for off in range(-before, after + 1):
                    rows.append((base + pd.Timedelta(days=off), name, off, 0 <= off <= hol_days))
    return rows


def build_calendar(index: pd.DatetimeIndex, preset: str = "mongolia", custom: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per date of ``index``: event ('' if none), offset, tag ('Event+off'), is_holiday, source."""
    years = range(index.min().year - 1, index.max().year + 2)
    rows = [(d, e, o, h, "preset") for d, e, o, h in _rows_for_preset(preset, years)]
    if custom is not None and len(custom):
        c = custom.copy()
        c.columns = [str(x).strip().lower() for x in c.columns]
        if not {"date", "event"}.issubset(c.columns):
            raise ValueError("custom events need columns: date, event [, offset_before, offset_after]")
        for _, r in c.iterrows():
            base = pd.Timestamp(r["date"])
            b = int(r.get("offset_before", 0) or 0)
            a = int(r.get("offset_after", 0) or 0)
            for off in range(-b, a + 1):
                rows.append((base + pd.Timedelta(days=off), str(r["event"]).strip(), off, off == 0, "custom"))
    cal = pd.DataFrame(rows, columns=["date", "event", "offset", "is_holiday", "source"])
    if cal.empty:
        cal = pd.DataFrame({"date": index, "event": "", "offset": 0, "is_holiday": False, "source": ""})
    cal["prio"] = cal["event"].map({e: i for i, e in enumerate(EVENT_PRIORITY)}).fillna(50)
    cal.loc[cal["source"] == "custom", "prio"] = -1          # user events win
    cal["absoff"] = cal["offset"].abs()
    cal = cal.sort_values(["date", "absoff", "prio"]).drop_duplicates("date").set_index("date")
    cal = cal.reindex(index)
    cal["event"] = cal["event"].fillna("")
    cal["offset"] = cal["offset"].fillna(0).astype(int)
    cal["is_holiday"] = cal["is_holiday"].fillna(False).astype(bool)
    cal["source"] = cal["source"].fillna("")
    cal["tag"] = np.where(cal["event"] == "", "",
                          cal["event"] + np.where(cal["offset"] >= 0, "+", "") + cal["offset"].astype(str))
    return cal[["event", "offset", "tag", "is_holiday", "source"]]


def discover_recurring_days(index: pd.DatetimeIndex, cal: pd.DataFrame, resid: np.ndarray,
                            min_other_years: int = 2, min_effect: float = 0.25) -> pd.DataFrame:
    """Find month-days that deviate the same way every year in the company-total residual
    (leave-one-year-out) and are not already covered by a calendar tag.  Returns a table
    (month_day, median_effect_log, years, sign_agreement) — used to add 'Auto:MM-DD' tags."""
    md = index.strftime("%m-%d").to_numpy()
    years = index.year.to_numpy()
    tagged = cal["tag"].to_numpy() != ""
    out = []
    for m in np.unique(md):
        cols = np.flatnonzero((md == m) & ~tagged)
        if cols.size < min_other_years + 1:
            continue
        vals = resid[cols]
        ok = np.isfinite(vals)
        if ok.sum() < min_other_years + 1:
            continue
        v = vals[ok]
        med = float(np.median(v))
        agree = float(np.mean(np.sign(v) == np.sign(med)))
        # leave-one-year-out check: each year's value must be predicted by the others
        loo_ok = 0
        for j in range(v.size):
            others = np.delete(v, j)
            if others.size >= min_other_years and abs(np.median(others)) >= min_effect and np.sign(np.median(others)) == np.sign(v[j]):
                loo_ok += 1
        if abs(med) >= min_effect and agree >= 0.75 and loo_ok >= min_other_years + 1:
            out.append({"month_day": m, "effect_log": med, "multiplier": float(np.exp(med)), "years": int(v.size),
                        "sign_agreement": agree})
    return pd.DataFrame(out, columns=["month_day", "effect_log", "multiplier", "years", "sign_agreement"])


def add_auto_events(cal: pd.DataFrame, index: pd.DatetimeIndex, found: pd.DataFrame) -> pd.DataFrame:
    if found is None or found.empty:
        return cal
    cal = cal.copy()
    md = index.strftime("%m-%d")
    for r in found.itertuples():
        mask = (md == r.month_day) & (cal["tag"] == "")
        cal.loc[mask, "event"] = f"Auto:{r.month_day}"
        cal.loc[mask, "offset"] = 0
        cal.loc[mask, "tag"] = f"Auto:{r.month_day}+0"
        cal.loc[mask, "source"] = "auto"
    return cal
