# Sales Anomaly Studio

Finds and explains unusual patterns in daily sales — company-wide, per branch, per category,
per item and per branch × item — and shows them in an interactive dashboard.

## Start — just double-click `run.bat`

Nothing to install. No Python, no setup, no internet needed.

1. Double-click **`run.bat`**.
2. A window opens showing the startup steps, then your browser opens the dashboard automatically.
3. **Leave that window open** while you use the app — it shows what the app is doing (loading a
   file, scoring each level, saving results). Close it to stop the app.

> The app runs entirely on your own computer at `http://localhost:8501`. No data leaves the machine.

*macOS / Linux:* run `./run.sh` in a terminal (that route needs Python 3.10+ and downloads the
packages once).

## What you see

| Page | What you get |
|---|---|
| **Overview** | Headline counts, data-gap / closure warnings, company total against its expected band, anomalies per month, the top findings with full explanations |
| **Anomalies** | The ranked queue with filters (level, type, severity, dates, scope, free text). Click a row → plain-language reason, the numbers, the drivers (which branches / categories / items caused it) and the series chart with the expected band |
| **Explorer** | Any series: actual vs expected, z-score timeline, weekday profile, learned holiday effects, and its own anomalies |
| **Calendar & seasonality** | What each holiday does to sales (company-wide and per branch), recurring days discovered from the data, weekday patterns |
| **Data quality** | Data gaps, company closures, duplicated days, coverage per branch, long dark periods, item launches / discontinuations |
| **New scenario** | Analyse **your own sales file**: drag it in, click **Browse…** to pick it from the computer, or use the demo data. Name the scenario, adjust settings if you want, press Run and watch the progress |
| **Scenarios** | Every analysis you have ever run, with its source file, period, settings and results. Open, rename, export or delete any of them, and compare them side by side |
| **Export** | Download `anomalies.csv`, the summary `report.md`, calendar effects |

### Using your own data — scenarios

Go to **New scenario** and pick the file in one of three ways:

1. **Upload a file** — drag and drop, or click Browse (up to 2 GB).
2. **Choose from this computer** — click **📁 Browse…** for the normal Windows "open file" dialog,
   or paste a full path. Nothing is copied; the file is read where it sits, which suits very large files.
3. **Bundled demo data** — the synthetic dataset that ships with the app.

Give the scenario a name (e.g. *2026 H1 actuals*, *Region North only*), press **Run detection**,
and the progress appears both in the browser and in the launcher window.

**Every scenario is saved automatically** into `runs/<timestamp>_<name>/` — the anomaly table, the
per-day scores, the report and the settings used. They are all listed on the **Scenarios** page and
in the *Scenario* selector at the top left, so you can switch between analyses, compare them, or come
back to one next week. Nothing is overwritten: re-running the same file makes a new scenario.

The file needs these columns (any order, case-insensitive):

```
DATE, BRANCH_ID, CATEGORY_1_ID, CATEGORY_2_ID, ITEM_ID, AMOUNT
```

`DATE` as `YYYY-MM-DD`, `AMOUNT` numeric. Transaction-level files are aggregated automatically;
bad rows are reported, not silently dropped. Roughly one minute for 4–5 million rows.

Optional lookups placed in `data/` make the display readable instead of showing raw codes:
`branch_names.csv` (`BRANCH_ID,BRANCH_NAME`) and `item_dictionary.csv`
(`ITEM_ID,ITEM_CODE,ITEM_NAME,…`).

## The bundled demo dataset

`data/demo_sales.parquet` is **synthetic data generated for this app** — 40 invented branches in
five channel families, 12 categories / 44 sub-categories / 658 invented products, 2022-01 → 2026-05,
4.5 M rows, 466 B MNT. It contains **no real business data**: every id, name and number is invented.

It was tuned to have the same *statistical character* as a real bakery-chain extract, so the app
behaves the same on it — weekday and holiday seasonality, a core product range that sells daily with
an occasional long tail, corporate bulk orders, staggered branch openings and closures, wholesale
channels that trade irregularly, and missing extracts. (Branch-level daily noise σ ≈ 0.13 and
company-level σ ≈ 0.08 in log terms, matching a real extract measured at 0.14 / 0.08.)
Regenerate it any time with `python tools/make_demo_data.py`.

Nine incidents were deliberately planted in it (see `data/demo_incidents.csv`) — a missing
11-week extract for four franchises, an 8-day wholesale outage, two level changes, a
trading-frequency collapse, a 268-day silence, a refurbishment closure, a posting error and a big
corporate order. **The engine finds all nine**, which is what the Overview page shows on first open.

## How the detection works

Every daily series is judged against **its own calendar-aware baseline**:

```
expected(t) = local level (leave-one-out median of the ±14 surrounding non-event days)
            + weekday effect + day-of-month effect
            + calendar-event effect  (holiday preset with day offsets — Tsagaan Sar, Naadam,
                                      Women's / Children's Day, the New Year window — plus your own
                                      events and recurring days discovered from the data; each effect
                                      learned leave-one-year-out, falling back to the parent series)
z(t)        = residual / robust local sigma (cannot collapse; widened on uncertain event days)
```

Thresholds **self-calibrate** to whatever dataset is loaded (target alert rate per level, moved by
the sensitivity slider), so the same app works on one branch, a quarter, or next year's file.
Each point anomaly is also split into *local* vs *company-wide* by comparing it with its peers.

Anomaly types: `Spike` / `Drop`, `Unexpected zero / closure`, `Level change` (8-week-vs-8-week jump,
seasonal transition removed, must persist ≥ 6 weeks), `Company-wide event` (many branches move
together → one record; the branch alerts become *echoes* and are hidden by default), `Data gap`,
`Company closure` (holiday / recurring / unexplained), `Long silence`, `Trading-frequency change`,
`Repeated day`, `Unusual category mix`, `Item launch / discontinued`.

Every record carries actual, expected, band, ratio, z, MNT impact, share of the day's revenue,
calendar tag, whether it recurs annually, its parent, the drivers and a plain-language reason.
`priority` ranks the queue.

### Benchmark

`python -m engine.evaluate data/demo_sales.parquet` plants 40 known anomalies of each kind into the
data, re-runs the engine and reports how many came back:

| planted | recall |
|---|---:|
| one-day spike (×3) | 97 % |
| one-day drop (×0.3) | 97 % |
| 3-day branch outage | 93 % |
| 10-day branch outage | 80 % |
| 10-week level change (×0.6) | 75 % |

with ~180 extra branch-level records for 200 planted events. Run it against your own file to see how
the engine behaves on your data.

## Files

```
run.bat / run.sh    launchers            setup/start.ps1   what run.bat actually does
app.py              the dashboard        engine/           detection engine
data/               demo data + lookups  runs/             saved scenarios (demo_full is precomputed)
runtime/            the private Python that makes it zero-install (Windows)
tools/              demo-data generator  requirements.txt  package list
```

* `runtime/` is ~460 MB and is why nothing has to be installed. If you would rather keep the folder
  small, delete it — `run.bat` then uses a Python already on the PC, or downloads a private one
  automatically (needs internet once).
* A saved scenario is ~14 MB for the demo dataset. Delete ones you no longer need from the
  **Scenarios** page (or delete the folder under `runs/`).
* Baselines look at days on both sides of each date, which is right for auditing history; tick
  *Causal baselines* in **New scenario** for forecast-style scoring that only looks backwards.
