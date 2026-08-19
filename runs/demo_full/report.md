# Sales anomaly report

Engine `hier-robust-v2` · generated 2026-08-18T10:35 · data 2022-01-03..2026-05-31 (1579 trading days, 4,460,416 rows, 466.17B MNT) · sensitivity **medium**, calendar **mongolia**, auto-discovered recurring days · 46.4s

## Headline numbers

* 6384 records — high: 2902, medium: 2755, critical: 621, info: 59, low: 47
* by type: point_spike: 2803, point_drop: 1570, unexpected_zero: 1233, level_shift: 448, unusual_mix: 209, activity_shift: 83, company_closure: 31, long_silence: 5, data_gap: 2
* by level: branch_item: 2725, item: 1526, branch_category: 1071, branch: 919, category2: 83, global: 34, category1: 26
* effective |z| thresholds (self-calibrated): global 3.5, branch 4.0, category1 4.0, category2 4.0, branch_category 6.38, item 4.5, branch_item 5.0
* series scored / existing: global 1/1, branch 40/40, category1 12/12, category2 44/44, branch_category 448/462, item 658/658, branch_item 2087/8650

## Top 40 by priority

| # | date | level | entity | type | sev | scope | actual | expected | ratio | z | reason |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---|
| 1 | 2025-12-01 | branch | MARKET STORE | point_spike | critical | local | 58.8M | 8.6M | 6.81 | +15.5 | Branch MARKET STORE: 58.8M on 2025-12-01 (Monday) vs expected 8.6M — 6.81× (+50.2M), z=+15.5. Drivers: MARKET STORE·47 +46.5M; MARKET STORE·34 +1.2M; MARKET STORE·63 +674k [55 lower-level series echo this] |
| 2 | 2024-01-04→2024-03-24 | global | Company total | data_gap | critical | systemic | n/a | 6.37B |  |  | 4 branches (FRANCHISE 3, FRANCHISE 2, FRANCHISE 4, FRANCHISE 1) posted NO sales from 2024-01-04 to 2024-03-24 (81 days) although they were trading normally before — probable missing extract, system outage or closure of a whole company/region; ≈6.37B of expected revenue is absent from the file. Verify the source data before reading any other finding in this period. |
| 3 | 2023-07-01 | branch | FRANCHISE 1 | point_spike | critical | local | 59.8M | 21.5M | 2.78 | +9.5 | Branch FRANCHISE 1: 59.8M on 2023-07-01 (Saturday) vs expected 21.5M — 2.78× (+38.3M), z=+9.5. Drivers: FRANCHISE 1·47 +35.8M; FRANCHISE 1·78 +2.4M; FRANCHISE 1·63 +59k [34 lower-level series echo this] |
| 4 | 2024-05-13 | branch | FRANCHISE 3 | point_spike | critical | local | 49.2M | 18.7M | 2.64 | +9.2 | Branch FRANCHISE 3: 49.2M on 2024-05-13 (Monday) vs expected 18.7M — 2.64× (+30.6M), z=+9.2. Drivers: FRANCHISE 3·47 +30.2M; FRANCHISE 3·78 +438k; FRANCHISE 3·90 +23k [25 lower-level series echo this] |
| 5 | 2023-04-27 | branch | FRANCHISE 2 | point_spike | critical | local | 48.4M | 18.5M | 2.61 | +9.2 | Branch FRANCHISE 2: 48.4M on 2023-04-27 (Thursday) vs expected 18.5M — 2.61× (+29.9M), z=+9.2. Drivers: FRANCHISE 2·47 +29.2M; FRANCHISE 2·78 +576k; FRANCHISE 2·34 +16k [33 lower-level series echo this] |
| 6 | 2025-05-07 | branch | FRANCHISE 5 | point_spike | critical | local | 52.1M | 17.0M | 3.06 | +9.1 | Branch FRANCHISE 5: 52.1M on 2025-05-07 (Wednesday) vs expected 17.0M — 3.06× (+35.1M), z=+9.1. Drivers: FRANCHISE 5·47 +34.4M; FRANCHISE 5·78 +733k; FRANCHISE 5·34 +16k [31 lower-level series echo this] |
| 7 | 2024-11-28 | branch | FRANCHISE 2 | point_spike | critical | local | 50.3M | 19.7M | 2.55 | +9.0 | Branch FRANCHISE 2: 50.3M on 2024-11-28 (Thursday) vs expected 19.7M — 2.55× (+30.6M), z=+9.0. Drivers: FRANCHISE 2·47 +24.9M; FRANCHISE 2·78 +5.8M; FRANCHISE 2·63 +26k [22 lower-level series echo this] |
| 8 | 2026-03-21 | branch | FRANCHISE 3 | point_spike | critical | local | 81.1M | 30.5M | 2.66 | +9.2 | Branch FRANCHISE 3: 81.1M on 2026-03-21 (Saturday) vs expected 30.5M — 2.66× (+50.6M), z=+9.2. Drivers: FRANCHISE 3·47 +49.2M; FRANCHISE 3·78 +1.4M; FRANCHISE 3·90 +50k [25 lower-level series echo this] |
| 9 | 2025-03-21 | branch | FRANCHISE 3 | point_spike | critical | local | 61.2M | 24.8M | 2.46 | +8.7 | Branch FRANCHISE 3: 61.2M on 2025-03-21 (Friday) vs expected 24.8M — 2.46× (+36.4M), z=+8.7. Drivers: FRANCHISE 3·47 +36.0M; FRANCHISE 3·78 +289k; FRANCHISE 3·90 +43k [22 lower-level series echo this] |
| 10 | 2024-06-14 | branch | FRANCHISE 1 | point_spike | critical | local | 54.8M | 22.9M | 2.39 | +8.1 | Branch FRANCHISE 1: 54.8M on 2024-06-14 (Friday) vs expected 22.9M — 2.39× (+31.8M), z=+8.1. Drivers: FRANCHISE 1·47 +31.6M; FRANCHISE 1·78 +207k; FRANCHISE 1·21 +9k [29 lower-level series echo this] |
| 11 | 2025-10-20 | branch | FRANCHISE 4 | point_spike | critical | local | 37.4M | 16.6M | 2.25 | +8.0 | Branch FRANCHISE 4: 37.4M on 2025-10-20 (Monday) vs expected 16.6M — 2.25× (+20.8M), z=+8.0. Drivers: FRANCHISE 4·47 +20.2M; FRANCHISE 4·78 +693k; FRANCHISE 4·63 +43k [22 lower-level series echo this] |
| 12 | 2025-02-26 | branch | MARKET STORE | point_spike | critical | local | 33.6M | 9.7M | 3.48 | +10.0 | Branch MARKET STORE: 33.6M on 2025-02-26 (Wednesday) vs expected 9.7M — 3.48× (+23.9M), z=+10.0; calendar: TsagaanSar-3 (effect already in the baseline). Drivers: MARKET STORE·47 +21.7M; MARKET STORE·78 +1.3M; MARKET STORE·63 +786k [18 lower-level series echo this] |
| 13 | 2024-01-19 | branch | CENTRAL STORE | point_spike | critical | local | 22.9M | 9.0M | 2.53 | +8.1 | Branch CENTRAL STORE: 22.9M on 2024-01-19 (Friday) vs expected 9.0M — 2.53× (+13.9M), z=+8.1. Drivers: CENTRAL STORE·47 +13.7M; CENTRAL STORE·78 +306k; CENTRAL STORE·90 +24k [17 lower-level series echo this] |
| 14 | 2022-12-15 | branch | NORTHTOWN BRANCH | point_spike | critical | local | 26.0M | 7.3M | 3.58 | +10.5 | Branch NORTHTOWN BRANCH: 26.0M on 2022-12-15 (Thursday) vs expected 7.3M — 3.58× (+18.7M), z=+10.5. Drivers: NORTHTOWN BRANCH·47 +15.9M; NORTHTOWN BRANCH·78 +2.8M; NORTHTOWN BRANCH·63 +232k [14 lower-level series echo this] |
| 15 | 2023-03-18 | branch | EASTPORT BRANCH | point_spike | critical | local | 50.5M | 15.4M | 3.28 | +8.9 | Branch EASTPORT BRANCH: 50.5M on 2023-03-18 (Saturday) vs expected 15.4M — 3.28× (+35.1M), z=+8.9; calendar: SoldiersDay+0 (effect already in the baseline). Drivers: EASTPORT BRANCH·47 +29.8M; EASTPORT BRANCH·78 +4.9M; EASTPORT BRANCH·21 +117k [20 lower-level series echo this] |
| 16 | 2022-04-18 | branch | OLD TOWN STORE | point_spike | critical | local | 16.6M | 5.6M | 2.97 | +9.5 | Branch OLD TOWN STORE: 16.6M on 2022-04-18 (Monday) vs expected 5.6M — 2.97× (+11.0M), z=+9.5. Drivers: OLD TOWN STORE·47 +10.7M; OLD TOWN STORE·63 +293k; OLD TOWN STORE·78 +17k [17 lower-level series echo this] |
| 17 | 2022-01-17 | branch | FRANCHISE 1 | point_spike | high | local | 38.7M | 14.0M | 2.76 | +7.5 | Branch FRANCHISE 1: 38.7M on 2022-01-17 (Monday) vs expected 14.0M — 2.76× (+24.7M), z=+7.5. Drivers: FRANCHISE 1·47 +22.3M; FRANCHISE 1·78 +2.4M; FRANCHISE 1·90 +45k [24 lower-level series echo this] |
| 18 | 2024-08-28 | branch | HILLSIDE STORE | point_spike | critical | local | 22.4M | 7.8M | 2.88 | +9.1 | Branch HILLSIDE STORE: 22.4M on 2024-08-28 (Wednesday) vs expected 7.8M — 2.88× (+14.6M), z=+9.1. Drivers: HILLSIDE STORE·47 +12.9M; HILLSIDE STORE·78 +1.6M; HILLSIDE STORE·63 +51k [18 lower-level series echo this] |
| 19 | 2022-09-04 | branch | FRANCHISE 1 | point_spike | high | local | 43.5M | 15.7M | 2.77 | +7.8 | Branch FRANCHISE 1: 43.5M on 2022-09-04 (Sunday) vs expected 15.7M — 2.77× (+27.8M), z=+7.8. Drivers: FRANCHISE 1·47 +27.1M; FRANCHISE 1·78 +785k; FRANCHISE 1·21 +8k [26 lower-level series echo this] |
| 20 | 2022-06-23 | branch | OLD TOWN STORE | point_spike | critical | local | 18.1M | 5.8M | 3.13 | +9.1 | Branch OLD TOWN STORE: 18.1M on 2022-06-23 (Thursday) vs expected 5.8M — 3.13× (+12.3M), z=+9.1. Drivers: OLD TOWN STORE·47 +11.8M; OLD TOWN STORE·78 +528k; OLD TOWN STORE·63 +6k [16 lower-level series echo this] |
| 21 | 2025-02-06 | branch | OLD TOWN STORE | point_spike | critical | local | 26.2M | 8.6M | 3.04 | +9.0 | Branch OLD TOWN STORE: 26.2M on 2025-02-06 (Thursday) vs expected 8.6M — 3.04× (+17.6M), z=+9.0. Drivers: OLD TOWN STORE·47 +16.7M; OLD TOWN STORE·78 +412k; OLD TOWN STORE·63 +353k [17 lower-level series echo this] |
| 22 | 2023-06-04 | branch | NORTHTOWN 2 BRANCH | point_spike | critical | local | 23.3M | 7.3M | 3.20 | +8.1 | Branch NORTHTOWN 2 BRANCH: 23.3M on 2023-06-04 (Sunday) vs expected 7.3M — 3.20× (+16.0M), z=+8.1. Drivers: NORTHTOWN 2 BRANCH·47 +15.3M; NORTHTOWN 2 BRANCH·63 +708k; NORTHTOWN 2 BRANCH·34 +32k [15 lower-level series echo this] |
| 23 | 2024-09-28 | branch | OLD TOWN STORE | point_spike | critical | local | 23.8M | 9.2M | 2.57 | +8.2 | Branch OLD TOWN STORE: 23.8M on 2024-09-28 (Saturday) vs expected 9.2M — 2.57× (+14.5M), z=+8.2. Drivers: OLD TOWN STORE·47 +14.3M; OLD TOWN STORE·78 +212k; OLD TOWN STORE·21 +426 [17 lower-level series echo this] |
| 24 | 2023-03-03 | branch | HARBOUR STORE | point_spike | critical | local | 26.9M | 8.9M | 3.04 | +7.4 | Branch HARBOUR STORE: 26.9M on 2023-03-03 (Friday) vs expected 8.9M — 3.04× (+18.0M), z=+7.4. Drivers: HARBOUR STORE·47 +17.4M; HARBOUR STORE·63 +391k; HARBOUR STORE·34 +69k [15 lower-level series echo this] |
| 25 | 2024-09-11 | branch | HARBOUR STORE | point_spike | critical | local | 29.3M | 9.6M | 3.05 | +9.7 | Branch HARBOUR STORE: 29.3M on 2024-09-11 (Wednesday) vs expected 9.6M — 3.05× (+19.7M), z=+9.7. Drivers: HARBOUR STORE·47 +19.4M; HARBOUR STORE·78 +204k; HARBOUR STORE·63 +99k [13 lower-level series echo this] |
| 26 | 2025-03-07 | branch | FRANCHISE 3 | point_spike | high | local | 365.5M | 133.8M | 2.73 | +7.0 | Branch FRANCHISE 3: 365.5M on 2025-03-07 (Friday) vs expected 133.8M — 2.73× (+231.7M), z=+7.0; calendar: WomensDay-1 (effect already in the baseline). Drivers: FRANCHISE 3·47 +231.3M; FRANCHISE 3·78 +3.5M; FRANCHISE 3·111 +133k [28 lower-level series echo this] |
| 27 | 2024-09-29 | branch | FRANCHISE 1 | point_spike | high | local | 49.5M | 20.4M | 2.42 | +7.8 | Branch FRANCHISE 1: 49.5M on 2024-09-29 (Sunday) vs expected 20.4M — 2.42× (+29.1M), z=+7.8. Drivers: FRANCHISE 1·47 +29.2M; FRANCHISE 1·21 +18k; FRANCHISE 1·111 +6k [27 lower-level series echo this] |
| 28 | 2026-02-12 | branch | WESTFIELD 2 BRANCH | point_spike | critical | local | 30.6M | 10.0M | 3.05 | +8.1 | Branch WESTFIELD 2 BRANCH: 30.6M on 2026-02-12 (Thursday) vs expected 10.0M — 3.05× (+20.6M), z=+8.1. Drivers: WESTFIELD 2 BRANCH·47 +20.0M; WESTFIELD 2 BRANCH·63 +774k; WESTFIELD 2 BRANCH·90 +66k [15 lower-level series echo this] |
| 29 | 2022-06-16 | branch | MARKET STORE | point_spike | critical | local | 21.3M | 7.0M | 3.02 | +7.6 | Branch MARKET STORE: 21.3M on 2022-06-16 (Thursday) vs expected 7.0M — 3.02× (+14.2M), z=+7.6. Drivers: MARKET STORE·47 +13.1M; MARKET STORE·78 +801k; MARKET STORE·63 +440k [13 lower-level series echo this] |
| 30 | 2023-10-14 | branch | NORTHTOWN BRANCH | point_spike | critical | local | 30.2M | 10.2M | 2.96 | +8.7 | Branch NORTHTOWN BRANCH: 30.2M on 2023-10-14 (Saturday) vs expected 10.2M — 2.96× (+20.0M), z=+8.7. Drivers: NORTHTOWN BRANCH·47 +14.2M; NORTHTOWN BRANCH·78 +5.6M; NORTHTOWN BRANCH·111 +21k [12 lower-level series echo this] |
| 31 | 2026-03-13 | branch | HILLSIDE STORE | point_spike | critical | local | 28.5M | 11.9M | 2.38 | +8.0 | Branch HILLSIDE STORE: 28.5M on 2026-03-13 (Friday) vs expected 11.9M — 2.38× (+16.5M), z=+8.0. Drivers: HILLSIDE STORE·47 +14.0M; HILLSIDE STORE·78 +2.3M; HILLSIDE STORE·63 +152k [16 lower-level series echo this] |
| 32 | 2022-05-14 | branch | PARK STORE | point_spike | critical | local | 23.9M | 8.8M | 2.71 | +8.2 | Branch PARK STORE: 23.9M on 2022-05-14 (Saturday) vs expected 8.8M — 2.71× (+15.1M), z=+8.2. Drivers: PARK STORE·47 +10.8M; PARK STORE·78 +4.3M; PARK STORE·90 +64k [12 lower-level series echo this] |
| 33 | 2023-06-19 | branch | FRANCHISE 1 | point_spike | high | local | 34.6M | 16.6M | 2.09 | +6.8 | Branch FRANCHISE 1: 34.6M on 2023-06-19 (Monday) vs expected 16.6M — 2.09× (+18.0M), z=+6.8. Drivers: FRANCHISE 1·47 +17.1M; FRANCHISE 1·78 +414k; FRANCHISE 1·63 +319k [20 lower-level series echo this] |
| 34 | 2023-01-06 | branch | FRANCHISE 1 | point_spike | high | local | 37.3M | 20.0M | 1.87 | +5.8 | Branch FRANCHISE 1: 37.3M on 2023-01-06 (Friday) vs expected 20.0M — 1.87× (+17.3M), z=+5.8. Drivers: FRANCHISE 1·47 +17.3M; FRANCHISE 1·63 +154k; FRANCHISE 1·78 +24k [23 lower-level series echo this] |
| 35 | 2024-10-08 | branch | AIRPORT STORE | point_spike | critical | local | 19.0M | 6.9M | 2.77 | +9.2 | Branch AIRPORT STORE: 19.0M on 2024-10-08 (Tuesday) vs expected 6.9M — 2.77× (+12.2M), z=+9.2. Drivers: AIRPORT STORE·47 +11.9M; AIRPORT STORE·63 +227k; AIRPORT STORE·90 +73k [13 lower-level series echo this] |
| 36 | 2022-11-11 | branch | FRANCHISE 1 | point_spike | high | local | 38.5M | 17.8M | 2.17 | +6.6 | Branch FRANCHISE 1: 38.5M on 2022-11-11 (Friday) vs expected 17.8M — 2.17× (+20.8M), z=+6.6. Drivers: FRANCHISE 1·47 +20.4M; FRANCHISE 1·63 +382k; FRANCHISE 1·78 +189k [22 lower-level series echo this] |
| 37 | 2024-11-13 | branch | PARK STORE | point_spike | critical | local | 23.7M | 8.6M | 2.76 | +8.7 | Branch PARK STORE: 23.7M on 2024-11-13 (Wednesday) vs expected 8.6M — 2.76× (+15.1M), z=+8.7. Drivers: PARK STORE·47 +11.6M; PARK STORE·78 +3.1M; PARK STORE·63 +264k [12 lower-level series echo this] |
| 38 | 2022-07-14 | branch | CENTRAL STORE | point_spike | critical | local | 11.5M | 3.5M | 3.32 | +8.0 | Branch CENTRAL STORE: 11.5M on 2022-07-14 (Thursday) vs expected 3.5M — 3.32× (+8.1M), z=+8.0; calendar: Naadam+3 (effect already in the baseline). Drivers: CENTRAL STORE·47 +7.7M; CENTRAL STORE·78 +315k; CENTRAL STORE·90 +69k [12 lower-level series echo this] |
| 39 | 2023-08-31 | branch | FRANCHISE 2 | point_spike | high | local | 38.3M | 17.8M | 2.15 | +4.5 | Branch FRANCHISE 2: 38.3M on 2023-08-31 (Thursday) vs expected 17.8M — 2.15× (+20.5M), z=+4.5; calendar: AcademicYear-1 (effect already in the baseline). Drivers: FRANCHISE 2·47 +19.5M; FRANCHISE 2·78 +1.0M; FRANCHISE 2·63 +18k [21 lower-level series echo this] |
| 40 | 2025-05-01 | branch | MARKET STORE | point_spike | critical | local | 26.6M | 9.6M | 2.77 | +8.2 | Branch MARKET STORE: 26.6M on 2025-05-01 (Thursday) vs expected 9.6M — 2.77× (+17.0M), z=+8.2. Drivers: MARKET STORE·47 +16.3M; MARKET STORE·63 +807k; MARKET STORE·21 +7k [13 lower-level series echo this] |

## Company-wide / systemic events

none

## Company closures that are NOT known holidays

none

## Learned calendar effects (company total, multiplier vs. a normal day)

| event day | multiplier | years |
|---|---:|---:|
| AcademicYear+0 | 1.53× | 4 |
| AcademicYear+1 | 1.09× | 4 |
| AcademicYear-1 | 1.08× | 4 |
| ChildrensDay+0 | 4.85× | 4 |
| ChildrensDay+1 | 0.91× | 4 |
| ChildrensDay-1 | 4.10× | 5 |
| ChildrensDay-2 | 1.47× | 5 |
| ChinggisKhaanDay+0 | 1.16× | 4 |
| EldersDay+0 | 1.38× | 4 |
| EldersDay-1 | 1.01× | 4 |
| IndependenceDay+0 | 1.24× | 4 |
| Naadam+0 | 0.68× | 4 |
| Naadam+3 | 0.70× | 4 |
| Naadam+4 | 0.92× | 4 |
| Naadam-1 | 1.28× | 4 |
| Naadam-2 | 1.19× | 4 |
| NewYear+2 | 0.52× | 5 |
| NewYear+3 | 0.93× | 5 |
| NewYear-1 | 5.99× | 4 |
| NewYear-2 | 6.95× | 4 |
| NewYear-4 | 3.97× | 4 |
| NewYear-5 | 2.92× | 4 |
| NewYear-6 | 2.11× | 4 |
| NewYear-7 | 1.88× | 4 |
| NewYear-8 | 2.34× | 4 |
| NewYear-9 | 1.41× | 4 |
| RepublicDay+0 | 1.23× | 4 |
| SoldiersDay+0 | 2.38× | 5 |
| SoldiersDay-1 | 1.50× | 5 |
| TsagaanSar+3 | 0.80× | 4 |
| TsagaanSar+4 | 1.53× | 3 |
| TsagaanSar-1 | 1.56× | 5 |
| TsagaanSar-2 | 1.47× | 5 |
| TsagaanSar-3 | 1.28× | 5 |
| ValentinesDay+0 | 1.84× | 5 |
| ValentinesDay-1 | 1.02× | 5 |
| WomensDay+0 | 7.75× | 5 |
| WomensDay+1 | 1.17× | 5 |
| WomensDay-1 | 5.26× | 5 |
| WomensDay-2 | 2.39× | 5 |
| WomensDay-3 | 1.58× | 5 |

## Coverage

Share of each branch's trading days that could be scored: DC-01 99%, FR-01 100%, FR-02 100%, FR-03 100%, FR-04 100%, FR-05 100%, FR-06 96%, ON-01 100%, ON-02 88%, ON-03 95%, RG-01 100%, RG-02 100%, RG-03 100%, RG-04 100%, RG-05 100%, RG-06 100%, RG-07 100%, RG-08 100%, RG-09 100%, RG-10 98%, UB-01 100%, UB-02 100%, UB-03 100%, UB-04 100%, UB-05 100%, UB-06 100%, UB-07 100%, UB-08 100%, UB-09 100%, UB-10 100%, UB-11 100%, UB-12 100%, UB-13 100%, UB-14 100%, WS-01 100%, WS-02 100%, WS-03 100%, WS-04 100%, WS-05 100%, WS-06 99%

Series below 50 % coverage (treat their silence as *not checked*): none

## Data-quality flags

* 2025-06-17 · RIVERSIDE STORE · point_drop: Branch RIVERSIDE STORE: 355k on 2025-06-17 (Tuesday) vs expected 9.1M — 0.04× (-8.8M), z=-31.9; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: RIVERSIDE STORE·47 -8.3M; RIVERSIDE STORE·34 -300k; RIVERSIDE STORE·63 -185k [3 lower-level series echo this]
* 2024-05-16 · GARDEN STORE · category 78 · point_drop: Branch × Category 1 GARDEN STORE · category 78: 11k on 2024-05-16 (Thursday) vs expected 800k — 0.01× (-789k), z=-22.1; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: GARDEN STORE·[4082] Apple pizza 500g -698k; GARDEN STORE·[4104] Multigrain calzone -30k
* 2025-10-06 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 2k on 2025-10-06 (Monday) vs expected 134k — 0.01× (-132k), z=-23.9; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -133k
* 2024-11-11 · GARDEN STORE · category 78 · point_drop: Branch × Category 1 GARDEN STORE · category 78: 11k on 2024-11-11 (Monday) vs expected 727k — 0.01× (-716k), z=-20.0; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: GARDEN STORE·[4082] Apple pizza 500g -631k
* 2024-01-09 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 2k on 2024-01-09 (Tuesday) vs expected 125k — 0.02× (-123k), z=-21.5; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -118k
* 2022-02-17 · TOWER STORE · category 78 · point_drop: Branch × Category 1 TOWER STORE · category 78: 16k on 2022-02-17 (Thursday) vs expected 430k — 0.04× (-414k), z=-19.2; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: TOWER STORE·[4082] Apple pizza 500g -356k; TOWER STORE·[4084] Golden calzone 500g -40k; TOWER STORE·[4080] Lemon pizza 6pcs -11k
* 2022-06-07 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 2k on 2022-06-07 (Tuesday) vs expected 116k — 0.02× (-113k), z=-20.4; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -108k
* 2023-01-24 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 2k on 2023-01-24 (Tuesday) vs expected 116k — 0.02× (-114k), z=-19.9; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -116k
* 2024-04-09 · TOWER STORE · category 78 · point_drop: Branch × Category 1 TOWER STORE · category 78: 24k on 2024-04-09 (Tuesday) vs expected 553k — 0.04× (-529k), z=-18.3; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: TOWER STORE·[4082] Apple pizza 500g -397k; TOWER STORE·[4084] Golden calzone 500g -61k; TOWER STORE·[4080] Lemon pizza 6pcs -9k
* 2022-04-06 · UNIVERSITY STORE · category 78 · point_drop: Branch × Category 1 UNIVERSITY STORE · category 78: 4k on 2022-04-06 (Wednesday) vs expected 286k — 0.01× (-282k), z=-18.5; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: UNIVERSITY STORE·[4082] Apple pizza 500g -214k
* 2024-03-04 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 4k on 2024-03-04 (Monday) vs expected 141k — 0.03× (-136k), z=-18.3; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -134k
* 2022-10-10 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 3k on 2022-10-10 (Monday) vs expected 108k — 0.03× (-105k), z=-17.5; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -103k
* 2023-06-26 · NORTHTOWN 3 BRANCH · category 63 · point_drop: Branch × Category 1 NORTHTOWN 3 BRANCH · category 63: 2k on 2023-06-26 (Monday) vs expected 105k — 0.02× (-103k), z=-17.6; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: NORTHTOWN 3 BRANCH·[3956] Chocolate tart 0.5l -72k; NORTHTOWN 3 BRANCH·[4004] Sourdough tart 6pcs -12k
* 2022-09-13 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 4k on 2022-09-13 (Tuesday) vs expected 112k — 0.04× (-108k), z=-17.5; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -108k
* 2023-09-11 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 4k on 2023-09-11 (Monday) vs expected 113k — 0.04× (-109k), z=-17.5; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -110k
* 2023-03-15 · UNIVERSITY STORE · category 78 · point_drop: Branch × Category 1 UNIVERSITY STORE · category 78: 6k on 2023-03-15 (Wednesday) vs expected 283k — 0.02× (-277k), z=-16.7; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: UNIVERSITY STORE·[4082] Apple pizza 500g -267k
* 2025-07-17 · WESTFIELD 2 BRANCH · category 78 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 78: 16k on 2025-07-17 (Thursday) vs expected 639k — 0.03× (-622k), z=-16.2; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[4082] Apple pizza 500g -481k
* 2025-02-18 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 6k on 2025-02-18 (Tuesday) vs expected 139k — 0.04× (-133k), z=-17.1; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -143k
* 2023-06-11 · GARDEN STORE · category 78 · point_drop: Branch × Category 1 GARDEN STORE · category 78: 24k on 2023-06-11 (Sunday) vs expected 813k — 0.03× (-789k), z=-15.2; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: GARDEN STORE·[4082] Apple pizza 500g -669k; GARDEN STORE·[4104] Multigrain calzone -30k
* 2024-11-06 · MARKET STORE · category 63 · point_drop: Branch × Category 1 MARKET STORE · category 63: 3k on 2024-11-06 (Wednesday) vs expected 102k — 0.03× (-99k), z=-16.9; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: MARKET STORE·[3969] Country turnover 6pcs -93k
* 2022-09-15 · GARDEN STORE · category 78 · point_drop: Branch × Category 1 GARDEN STORE · category 78: 23k on 2022-09-15 (Thursday) vs expected 664k — 0.03× (-641k), z=-15.0; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: GARDEN STORE·[4082] Apple pizza 500g -567k
* 2024-09-15 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 6k on 2024-09-15 (Sunday) vs expected 148k — 0.04× (-141k), z=-16.6; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -135k
* 2022-05-15 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 6k on 2022-05-15 (Sunday) vs expected 137k — 0.04× (-131k), z=-16.5; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -132k
* 2023-10-23 · EASTPORT BRANCH · category 78 · point_drop: Branch × Category 1 EASTPORT BRANCH · category 78: 5k on 2023-10-23 (Monday) vs expected 333k — 0.02× (-328k), z=-15.8; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: EASTPORT BRANCH·[4082] Apple pizza 500g -309k
* 2024-05-16 · MARKET STORE · category 63 · point_drop: Branch × Category 1 MARKET STORE · category 63: 4k on 2024-05-16 (Thursday) vs expected 119k — 0.03× (-116k), z=-16.2; similar deviation recurs on this date in other years; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: MARKET STORE·[3969] Country turnover 6pcs -97k
* 2023-08-04 · WESTFIELD 2 BRANCH · category 78 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 78: 16k on 2023-08-04 (Friday) vs expected 556k — 0.03× (-539k), z=-15.1; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[4082] Apple pizza 500g -415k
* 2026-04-21 · EASTPORT BRANCH · category 78 · point_drop: Branch × Category 1 EASTPORT BRANCH · category 78: 16k on 2026-04-21 (Tuesday) vs expected 702k — 0.02× (-686k), z=-15.0; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: EASTPORT BRANCH·[4082] Apple pizza 500g -534k
* 2024-12-01 · WESTFIELD 2 BRANCH · category 63 · point_drop: Branch × Category 1 WESTFIELD 2 BRANCH · category 63: 8k on 2024-12-01 (Sunday) vs expected 156k — 0.05× (-148k), z=-16.0; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: WESTFIELD 2 BRANCH·[3969] Country turnover 6pcs -150k
* 2025-10-26 · MARKET STORE · category 63 · point_drop: Branch × Category 1 MARKET STORE · category 63: 4k on 2025-10-26 (Sunday) vs expected 128k — 0.03× (-124k), z=-16.0; similar deviation recurs on this date in other years; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: MARKET STORE·[3969] Country turnover 6pcs -107k
* 2022-08-08 · GARDEN STORE · category 78 · point_drop: Branch × Category 1 GARDEN STORE · category 78: 28k on 2022-08-08 (Monday) vs expected 647k — 0.04× (-619k), z=-14.0; magnitude suggests a posting / data-entry error — verify the source lines. Drivers: GARDEN STORE·[4082] Apple pizza 500g -534k; GARDEN STORE·[4104] Multigrain calzone -2k

## Method (short)

Each daily series (company, branch, category, branch×category, item, branch×item) is modelled on log1p(AMOUNT) of its trading days as local level (leave-one-out median of ±14 surrounding non-event days, widened automatically for sparse series) + weekday + day-of-month + calendar-event effect (built-in holiday preset + your custom events + recurring days discovered from the data; each effect learned leave-one-year-out with the parent series as fallback). Residuals are scaled by a rolling MAD that cannot collapse. Alert thresholds are self-calibrated per level to a target alert rate (sensitivity). Each point anomaly is split into local vs company-wide (peer-adjusted z). Zero days are judged against a leave-one-out open probability; level changes come from robust binary segmentation of the weekly, calendar- and season-adjusted series; branch alerts co-occurring company-wide roll up into one systemic record and lower-level echoes are demoted.
