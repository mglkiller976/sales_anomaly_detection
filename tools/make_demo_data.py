"""Generate the synthetic DEMO dataset shipped with the app.

The demo file has the same *character* as a real bakery-chain extract — 40 branches in five
channel families, 12 categories / 47 sub-categories / ~660 products, four and a half years of
daily rows, weekday and holiday seasonality, staggered openings and closures, and a handful of
planted incidents — but every id, name and number is invented.  No real business data is used.

    python tools/make_demo_data.py            # writes data/demo_sales.parquet + dictionaries

Reproducible: fixed seed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from engine.calendar import build_calendar  # noqa: E402

SEED = 20260818
START, END = "2022-01-01", "2026-05-31"

# ---------------------------------------------------------------- branches (invented codes/names)
# (code, name, family, revenue weight, opens, closes, trades daily?)
BRANCHES = [
    ("UB-01", "CENTRAL STORE", "city", 3.1, None, None, True),
    ("UB-02", "HARBOUR STORE", "city", 2.4, None, None, True),
    ("UB-03", "RIVERSIDE STORE", "city", 2.0, None, None, True),
    ("UB-04", "OLD TOWN STORE", "city", 1.8, None, None, True),
    ("UB-05", "STATION STORE", "city", 1.7, None, None, True),
    ("UB-06", "PARK STORE", "city", 1.6, None, None, True),
    ("UB-07", "UNIVERSITY STORE", "city", 1.5, None, None, True),
    ("UB-08", "MARKET STORE", "city", 1.4, None, None, True),
    ("UB-09", "HILLSIDE STORE", "city", 1.4, None, None, True),
    ("UB-10", "GARDEN STORE", "city", 1.3, None, None, True),
    ("UB-11", "AIRPORT STORE", "city", 1.2, None, None, True),
    ("UB-12", "STADIUM STORE", "city", 0.9, "2022-06-20", None, True),
    ("UB-13", "LAKESIDE STORE", "city", 0.7, "2022-10-24", None, True),
    ("UB-14", "TOWER STORE", "city", 0.6, None, None, True),
    ("RG-01", "NORTHTOWN BRANCH", "region", 2.1, None, None, True),
    ("RG-02", "NORTHTOWN 2 BRANCH", "region", 1.0, None, None, True),
    ("RG-03", "NORTHTOWN 3 BRANCH", "region", 0.5, None, None, True),
    ("RG-04", "NORTHTOWN 4 BRANCH", "region", 0.2, "2024-03-25", None, True),
    ("RG-05", "EASTPORT BRANCH", "region", 2.0, None, None, True),
    ("RG-06", "EASTPORT 2 BRANCH", "region", 0.7, None, "2026-03-14", True),
    ("RG-07", "EASTPORT 3 BRANCH", "region", 0.3, "2024-09-02", None, True),
    ("RG-08", "WESTFIELD BRANCH", "region", 0.9, None, None, True),
    ("RG-09", "WESTFIELD 2 BRANCH", "region", 0.8, None, "2026-03-09", True),
    ("RG-10", "SOUTHGATE BRANCH", "region", 0.15, "2025-12-26", None, True),
    ("FR-01", "FRANCHISE 1", "franchise", 5.6, None, None, True),
    ("FR-02", "FRANCHISE 2", "franchise", 3.4, None, None, True),
    ("FR-03", "FRANCHISE 3", "franchise", 4.7, None, None, True),
    ("FR-04", "FRANCHISE 4", "franchise", 2.0, "2023-09-04", None, True),
    ("FR-05", "FRANCHISE 5", "franchise", 0.6, "2024-12-13", None, True),
    ("FR-06", "FRANCHISE 6", "franchise", 0.3, "2025-12-22", None, True),
    ("WS-01", "WHOLESALE A", "wholesale", 0.60, None, None, True),
    ("WS-02", "WHOLESALE B", "wholesale", 0.34, None, None, True),
    ("WS-03", "WHOLESALE C", "wholesale", 0.28, None, None, True),
    ("WS-04", "WHOLESALE D", "wholesale", 0.28, None, None, True),
    ("WS-05", "WHOLESALE E", "wholesale", 0.06, "2025-05-29", None, True),
    ("WS-06", "WHOLESALE F", "wholesale", 0.06, "2025-01-30", None, True),
    ("ON-01", "ONLINE ORDERS", "online", 0.50, None, None, True),
    ("ON-02", "PHONE ORDERS", "online", 0.26, None, None, False),   # irregular
    ("ON-03", "EVENT CATERING", "online", 0.10, None, None, False),
    ("DC-01", "CENTRAL DEPOT", "depot", 0.65, None, None, False),   # sparse burst trading
]

# ---------------------------------------------------------------- categories (invented ids/names)
# cat1_id: (name, [(cat2_id, name, share)], n_items, unit price range, popularity)
CATEGORIES = {
    "21": ("Bread", [("211", "Bread-Plain", .42), ("212", "Bread-Seeded", .18), ("213", "Bread-Sweet", .14), ("214", "Bread-Artisan", .12),
                     ("215", "Bread-Rye", .08), ("216", "Bread-Gluten free", .06)], 54, (1800, 9000), 1.00),
    "34": ("Layered pastry", [("341", "Layered-Plain", .3), ("342", "Layered-Filled", .25), ("343", "Layered-Glazed", .2), ("344", "Layered-Mini", .15), ("345", "Layered-Party", .1)], 80, (1500, 12000), 1.10),
    "47": ("Cake", [("471", "Cake-Birthday", .22), ("472", "Cake-Brand", .22), ("473", "Cake-Slice", .16), ("474", "Cake-Mini", .1), ("475", "Cake-Custom", .07),
                    ("476", "Cake-Cheesecake", .09), ("477", "Cake-Roll", .07), ("478", "Cake-Seasonal", .07)], 300, (5000, 120000), 1.30),
    "55": ("Bun", [("551", "Bun-Sweet", .45), ("552", "Bun-Burger", .3), ("553", "Bun-Filled", .25)], 29, (900, 6500), 0.95),
    "63": ("Pie", [("631", "Pie-Slice", .5), ("632", "Pie-Whole", .3), ("633", "Pie-Mini", .2)], 28, (2500, 40000), 0.70),
    "78": ("Pizza", [("781", "Pizza-Whole", .3), ("782", "Pizza-Slice", .25), ("783", "Pizza-Frozen", .23), ("784", "Pizza-Half", .12),
                     ("785", "Pizza-Party", .10)], 48, (7000, 90000), 0.60),
    "82": ("Sandwich", [("821", "Sandwich-Cold", .5), ("822", "Sandwich-Hot", .5)], 11, (3500, 15000), 0.85),
    "90": ("Cupcake", [("901", "Cupcake-Plain", .35), ("902", "Cupcake-Decorated", .3), ("903", "Cupcake-Box", .22), ("904", "Cupcake-Seasonal", .13)], 30, (1800, 25000), 0.80),
    "111": ("Drinks", [("1111", "Drinks-Coffee", .3), ("1112", "Drinks-Juice", .27), ("1113", "Drinks-Water", .18), ("1114", "Drinks-Tea", .15),
                       ("1115", "Drinks-Shake", .10)], 51, (1200, 6000), 0.90),
    "126": ("Biscuit", [("1261", "Biscuit-Assorted", .7), ("1262", "Biscuit-Gift tin", .3)], 4, (2500, 9000), 0.55),
    "140": ("Bundle offer", [("UNKNOWN", "", 1.0)], 12, (5000, 15000), 0.20),
    "205": ("Clearance", [("UNKNOWN", "", 1.0)], 11, (900, 8000), 0.12),
}
# a few products in category 34 have no sub-category (mirrors real master-data gaps)
BLANK_CAT2_IN_34 = 7

ADJ = ["Classic", "Golden", "Rustic", "Soft", "Country", "Royal", "Farmhouse", "Velvet", "Honey", "Almond", "Cocoa",
       "Berry", "Lemon", "Caramel", "Vanilla", "Cinnamon", "Walnut", "Raisin", "Cheese", "Garlic", "Herb", "Multigrain",
       "Sourdough", "Butter", "Cream", "Chocolate", "Strawberry", "Apple", "Peach", "Coconut", "Pistachio", "Maple"]
NOUN = {"21": ["loaf", "toast", "baguette", "sandwich bread", "bun loaf"], "34": ["croissant", "danish", "roll", "twist", "layer"],
        "47": ["cake", "gateau", "torte", "cheesecake", "roll cake"], "55": ["bun", "brioche", "slider", "knot"],
        "63": ["pie", "tart", "turnover"], "78": ["pizza", "calzone"], "82": ["sandwich", "wrap", "panini"],
        "90": ["cupcake", "muffin", "friand"], "111": ["coffee", "juice", "water", "tea", "shake"],
        "126": ["biscuit", "cookie"], "140": ["combo", "set", "bundle"], "205": ["clearance pack", "last-day item"]}
SIZE = ["", "", "", " 250g", " 400g", " 500g", ' 7"', ' 8"', ' 9"', ' 10"', " 6pcs", " 12 slice", " 0.5l"]


def make_master(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    code = 3000
    for c1, (c1name, subs, n_items, (p_lo, p_hi), pop) in CATEGORIES.items():
        sub_ids = [s[0] for s in subs]
        sub_w = np.array([s[2] for s in subs], dtype=float)
        for i in range(n_items):
            code += rng.integers(1, 4)
            c2 = rng.choice(sub_ids, p=sub_w / sub_w.sum())
            if c1 == "34" and i < BLANK_CAT2_IN_34:
                c2 = "UNKNOWN"
            name = f"{rng.choice(ADJ)} {rng.choice(NOUN[c1])}{rng.choice(SIZE)}"
            price = float(np.exp(rng.uniform(np.log(p_lo), np.log(p_hi)))) * 0.63   # chain-wide price level
            price = round(price / 100) * 100
            rows.append({"ITEM_ID": str(10000 + len(rows) * 7 + rng.integers(0, 5)), "ITEM_CODE": str(code),
                         "ITEM_NAME": name, "CATEGORY_1_ID": c1, "CATEGORY_2_ID": c2, "price": max(price, 500),
                         "pop": float(pop * np.exp(rng.normal(0, 0.9)))})
    m = pd.DataFrame(rows).drop_duplicates("ITEM_ID").reset_index(drop=True)
    return m


def main() -> None:
    rng = np.random.default_rng(SEED)
    out_dir = APP / "data"
    out_dir.mkdir(exist_ok=True)
    index = pd.date_range(START, END, freq="D")
    T = len(index)
    cal = build_calendar(index, "mongolia")
    tag = cal["tag"].to_numpy()
    event = cal["event"].to_numpy()
    offset = cal["offset"].to_numpy()

    master = make_master(rng)
    n_items = len(master)
    print(f"{n_items} demo products, {len(BRANCHES)} branches, {T} days")

    # ---------------- company-level daily multiplier: trend + weekday + annual + holidays
    t = np.arange(T)
    trend = np.exp(0.00022 * t + 0.05 * np.sin(2 * np.pi * t / 365.25))
    dow = index.dayofweek.to_numpy()
    weekday = np.array([0.92, 0.93, 0.95, 1.00, 1.12, 1.18, 1.05])[dow]
    day_mult = trend * weekday

    ev_mult = np.ones(T)
    closed = np.zeros(T, dtype=bool)          # company-wide closure days
    for i in range(T):
        e, o = event[i], offset[i]
        if e == "WomensDay":
            ev_mult[i] = {-3: 1.5, -2: 2.2, -1: 4.2, 0: 6.0, 1: 1.1}.get(o, 1.0)
        elif e == "ChildrensDay":
            ev_mult[i] = {-2: 1.4, -1: 3.6, 0: 3.9, 1: 0.9}.get(o, 1.0)
        elif e == "NewYear":
            ev_mult[i] = {-9: 1.3, -8: 1.4, -7: 1.6, -6: 1.9, -5: 2.4, -4: 3.2, -3: 4.1, -2: 5.4, -1: 4.4,
                          0: 0.25, 1: 0.30, 2: 0.55, 3: 0.85}.get(o, 1.0)
            if o in (0, 1):
                closed[i] = True
        elif e == "TsagaanSar":
            ev_mult[i] = {-3: 1.2, -2: 1.4, -1: 1.5, 0: 0.02, 1: 0.15, 2: 0.25, 3: 0.8, 4: 1.5}.get(o, 1.0)
            if o in (0, 1, 2):
                closed[i] = True
        elif e == "Naadam":
            ev_mult[i] = {-2: 1.15, -1: 1.25, 0: 0.75, 1: 0.5, 2: 0.6, 3: 0.75, 4: 0.9}.get(o, 1.0)
            if o in (1, 2):
                closed[i] = True
        elif e == "ValentinesDay":
            ev_mult[i] = 1.6 if o == 0 else 1.0
        elif e == "SoldiersDay":
            ev_mult[i] = 2.2 if o == 0 else 1.5
        elif e == "AcademicYear":
            ev_mult[i] = 1.45 if o == 0 else 1.1
        elif e == "EldersDay":
            ev_mult[i] = 1.35 if o == 0 else 1.0
        elif e in ("RepublicDay", "IndependenceDay", "ChinggisKhaanDay"):
            ev_mult[i] = 1.2
    # a recurring, self-inflicted promo day the preset calendar does NOT know about (Dec 24)
    md = index.strftime("%m-%d").to_numpy()
    ev_mult[md == "12-24"] *= 1.45
    day_mult = day_mult * ev_mult
    day_mult *= np.exp(rng.normal(0, 0.06, T))          # ordinary day-to-day noise

    # ---------------- per-branch lifetime and daily factor
    frames = []
    incidents: list[str] = []
    price = master["price"].to_numpy()
    pop = master["pop"].to_numpy()
    cat1 = master["CATEGORY_1_ID"].to_numpy()
    for bi, (code, name, fam, weight, opens, closes, daily) in enumerate(BRANCHES):
        first = 0 if opens is None else index.get_loc(pd.Timestamp(opens))
        last = T - 1 if closes is None else index.get_loc(pd.Timestamp(closes))
        live = np.zeros(T, dtype=bool); live[first:last + 1] = True

        # which products this branch carries
        keep = rng.random(n_items) < {"city": .34, "region": .30, "franchise": .26, "wholesale": .15, "online": .19, "depot": .08}[fam]
        if fam == "franchise":                       # franchises skew to pizza + cake
            keep |= (np.isin(cat1, ["78", "47"]) & (rng.random(n_items) < .8))
        if fam == "wholesale":
            keep |= (np.isin(cat1, ["21", "55"]) & (rng.random(n_items) < .5))
        items = np.flatnonzero(keep)
        if items.size < 30:
            items = rng.choice(n_items, 60, replace=False)

        # branch daily factor: own drift + noise, plus open/closed pattern
        bf = weight * np.exp(np.cumsum(rng.normal(0, 0.004, T)) * 0.5 + rng.normal(0, 0.05, T))
        open_day = live & ~closed
        if not daily:                                  # irregular channels trade some days only
            p = {"online": 0.55, "depot": 0.11}[fam]
            open_day &= rng.random(T) < p
        else:
            open_day &= rng.random(T) > 0.012          # occasional ordinary closed day

        # ---- planted incidents (documented in demo_incidents.csv)
        def window(a, b):
            return slice(index.get_loc(pd.Timestamp(a)), index.get_loc(pd.Timestamp(b)) + 1)

        if code in ("FR-01", "FR-02", "FR-03", "FR-04"):     # 11-week missing extract
            w = window("2024-01-05", "2024-03-24")
            open_day[w] = False
            if code == "FR-01":
                incidents.append("2024-01-05,2024-03-24,data_gap,FR-01/02/03/04,four franchise branches missing from the extract")
        if code in ("WS-01", "WS-02", "WS-03", "WS-04"):     # 8-day wholesale outage
            open_day[window("2025-08-01", "2025-08-08")] = False
            if code == "WS-01":
                incidents.append("2025-08-01,2025-08-08,data_gap,WS-01..04,wholesale channels dark for 8 days")
        if code == "UB-06":                                   # sustained level shift
            bf[index.get_loc(pd.Timestamp("2025-05-26")):] *= 0.58
            incidents.append("2025-05-26,,level_shift,UB-06,revenue drops to 58% after a competitor opens")
        if code == "RG-05":
            bf[index.get_loc(pd.Timestamp("2023-11-20")):] *= 1.45
            incidents.append("2023-11-20,,level_shift,RG-05,revenue steps up 45% after refurbishment")
        if code == "ON-02":                                   # trading-frequency collapse then recovery
            open_day[window("2023-10-09", "2024-07-21")] &= rng.random(T)[window("2023-10-09", "2024-07-21")] < 0.28
            incidents.append("2023-10-09,2024-07-21,activity_shift,ON-02,order channel trades only ~1 day in 4 for 9 months")
        if code == "WS-06":                                   # long silence after launch
            open_day[window("2025-02-01", "2025-10-26")] = False
            incidents.append("2025-02-01,2025-10-26,long_silence,WS-06,dark for 268 days between two trading periods")
        if code == "UB-03":                                   # single-day posting error
            incidents.append("2025-06-17,,point_drop,UB-03,only a fraction of the day posted")
        if code == "UB-08":
            incidents.append("2025-12-01,,point_spike,UB-08,large corporate cake order")
        if code == "RG-01":
            open_day[window("2025-04-09", "2025-04-24")] = False
            incidents.append("2025-04-09,2025-04-24,unexpected_zero,RG-01,16-day refurbishment closure")

        days = np.flatnonzero(open_day)
        if days.size == 0:
            continue
        # ---- build the (item x day) sales matrix for this branch
        pr = price[items]; pp = pop[items]
        # a store sells its CORE range almost every day and the tail only occasionally — this is what
        # keeps a real branch's daily total smooth, so model it explicitly instead of one flat probability
        rank = pd.Series(pp).rank(pct=True).to_numpy()
        base_p = np.where(rank >= 0.75, 0.95, np.where(rank >= 0.45, 0.45, 0.10))
        base_p = base_p * rng.uniform(0.9, 1.05, items.size)
        if fam == "wholesale":
            base_p *= 0.75
        if fam == "depot":
            base_p *= 0.6
        M = day_mult[days][None, :] * bf[days][None, :]
        P = np.clip(base_p[:, None] * (0.75 + 0.35 * M / M.mean()), 0, 0.995)
        sold = rng.random((items.size, days.size)) < P
        # units: each (branch, item) has a stable typical daily volume that moves with the day factor,
        # plus modest multiplicative noise -- this is what makes a real store's daily total fairly smooth
        base_units = np.clip(2.2 * pp * rng.lognormal(0, 0.35, items.size), 1.0, 40)
        rel = M / np.mean(M)
        qty = np.maximum(1, np.round(base_units[:, None] * rel * rng.lognormal(0, 0.12, (items.size, days.size)))).astype(int)
        amount = qty * pr[:, None]
        # occasional discounting / odd prices
        amount = amount * np.where(rng.random(amount.shape) < 0.06, rng.uniform(0.6, 0.95, amount.shape), 1.0)
        # bulk / corporate orders: a whole ORDER lands on one day at one branch and lifts several
        # cake / pizza lines together (that is how the upper tail looks in real sales data)
        order_day = rng.random(days.size) < (0.010 if fam in ("online", "wholesale", "depot") else 0.004)
        if order_day.any():
            party = np.isin(cat1[items], ["47", "78", "63"])[:, None] & (rng.random((items.size, days.size)) < 0.35)
            lift = np.where(party & order_day[None, :], rng.uniform(2.5, 7.0, (items.size, days.size)), 1.0)
            amount = amount * lift
        amount = np.round(amount / 100) * 100
        # single-day incidents
        if code == "UB-03":
            j = np.searchsorted(days, index.get_loc(pd.Timestamp("2025-06-17")))
            if j < days.size and days[j] == index.get_loc(pd.Timestamp("2025-06-17")):
                sold[:, j] &= rng.random(items.size) < 0.04
        if code == "UB-08":
            j = np.searchsorted(days, index.get_loc(pd.Timestamp("2025-12-01")))
            if j < days.size and days[j] == index.get_loc(pd.Timestamp("2025-12-01")):
                amount[:, j] *= 6.5
        # item lifecycle: some products launch late / are discontinued
        if bi == 0:
            master.loc[master.index[:20], "_launch"] = 1
        launch = rng.random(items.size) < 0.05
        for k in np.flatnonzero(launch):
            cut = rng.integers(0, days.size)
            sold[k, :cut] = False
        disc = rng.random(items.size) < 0.04
        for k in np.flatnonzero(disc):
            cut = rng.integers(int(days.size * 0.4), days.size)
            sold[k, cut:] = False

        ii, jj = np.nonzero(sold)
        if ii.size == 0:
            continue
        frames.append(pd.DataFrame({
            "DATE": index[days[jj]],
            "BRANCH_ID": code,
            "CATEGORY_1_ID": cat1[items[ii]],
            "CATEGORY_2_ID": master["CATEGORY_2_ID"].to_numpy()[items[ii]],
            "ITEM_ID": master["ITEM_ID"].to_numpy()[items[ii]],
            "AMOUNT": amount[ii, jj],
        }))
        print(f"  {code:6s} {name:22s} {ii.size:>9,} rows")

    df = pd.concat(frames, ignore_index=True)
    df = df[df["AMOUNT"] > 0]
    # a few zero-amount giveaway lines, like the real extract
    z = df.sample(90, random_state=1).copy(); z["AMOUNT"] = 0.0
    df = pd.concat([df, z], ignore_index=True)
    df = df.groupby(["DATE", "BRANCH_ID", "CATEGORY_1_ID", "CATEGORY_2_ID", "ITEM_ID"], observed=True, as_index=False)["AMOUNT"].sum()
    df = df.sort_values(["DATE", "BRANCH_ID", "CATEGORY_1_ID", "CATEGORY_2_ID", "ITEM_ID"], kind="mergesort", ignore_index=True)
    df["AMOUNT"] = df["AMOUNT"].round(2)

    df.to_parquet(out_dir / "demo_sales.parquet", index=False, compression="zstd")
    sample = df[(df["DATE"] >= "2026-04-01")]
    sample.to_csv(out_dir / "demo_sales_sample.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8", lineterminator="\n")

    # dictionaries
    used = set(df["ITEM_ID"])
    it = master[master["ITEM_ID"].isin(used)].copy()
    agg = df.groupby("ITEM_ID").agg(FIRST_DATE=("DATE", "min"), LAST_DATE=("DATE", "max"), ACTIVE_DAYS=("DATE", "nunique"),
                                    SOURCE_ROWS=("AMOUNT", "size"), TOTAL_AMOUNT=("AMOUNT", "sum"))
    it = it.join(agg, on="ITEM_ID")
    it["MEDIAN_UNIT_PRICE"] = it["price"].round(0)
    it = it[["ITEM_ID", "ITEM_CODE", "ITEM_NAME", "CATEGORY_1_ID", "CATEGORY_2_ID", "FIRST_DATE", "LAST_DATE", "ACTIVE_DAYS",
             "SOURCE_ROWS", "TOTAL_AMOUNT", "MEDIAN_UNIT_PRICE"]]
    for c in ["FIRST_DATE", "LAST_DATE"]:
        it[c] = pd.to_datetime(it[c]).dt.date
    it.to_csv(out_dir / "item_dictionary.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame([{"BRANCH_ID": c, "BRANCH_NAME": n, "FAMILY": f} for c, n, f, *_ in BRANCHES]).to_csv(
        out_dir / "branch_names.csv", index=False, encoding="utf-8-sig")
    cats = [{"CATEGORY_1_ID": c1, "CATEGORY_1_NAME": v[0], "CATEGORY_2_ID": s[0], "CATEGORY_2_NAME": s[1] or "(none)"}
            for c1, v in CATEGORIES.items() for s in v[1]]
    pd.DataFrame(cats).to_csv(out_dir / "category_dictionary.csv", index=False, encoding="utf-8-sig")
    (out_dir / "demo_incidents.csv").write_text(
        "start,end,type,entity,description\n" + "\n".join(sorted(incidents)) + "\n", encoding="utf-8")

    daily = df.groupby("DATE")["AMOUNT"].sum()
    print(f"\nrows {len(df):,} · {df['DATE'].min().date()}..{df['DATE'].max().date()} · trading days {daily.shape[0]} "
          f"· total {df['AMOUNT'].sum() / 1e9:,.1f}B · median day {daily.median() / 1e6:,.0f}M "
          f"· branches {df['BRANCH_ID'].nunique()} · items {df['ITEM_ID'].nunique()} "
          f"· cat1 {df['CATEGORY_1_ID'].nunique()} · cat2 {df['CATEGORY_2_ID'].nunique()}")
    print(f"planted incidents: {len(incidents)} (see data/demo_incidents.csv)")
    print("parquet", (out_dir / 'demo_sales.parquet').stat().st_size / 1e6, "MB; sample csv",
          (out_dir / 'demo_sales_sample.csv').stat().st_size / 1e6, "MB")


if __name__ == "__main__":
    main()
