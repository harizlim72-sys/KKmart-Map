# KKmart Whitespace Analysis — Project Plan

Goal: identify **where KKmart should open new stores** by finding areas with strong demand
(population, households, spending power) but weak or no KKmart presence, using the
`KKmart stores final july` file (store name, address, longitude, latitude) as the supply side
and official Malaysian government open data (DOSM) as the demand side.

---

## 1. Data sources (all verified & free)

### 1.1 Supply side — our data
| Data | Source | Notes |
|---|---|---|
| KKmart store list | `KKmart stores final july` | Place in repo as `data/raw/kkmart_stores_july.csv` (name, address, longitude, latitude) |

### 1.2 Demand side — OpenDOSM (open.dosm.gov.my)
All datasets are downloadable as Parquet/CSV directly from DOSM storage:

| Dataset | URL | What we use it for |
|---|---|---|
| Population by district | https://open.dosm.gov.my/data-catalogue/population_district (`https://storage.dosm.gov.my/population/population_district.parquet`) | Population 2020–2024 by district, sex, age group, ethnicity → market size + age mix |
| Household income by district | https://open.dosm.gov.my/data-catalogue/hh_income_district | Mean & median gross monthly household income (HIES 2022) → spending power |
| HIES by district (full) | https://open.dosm.gov.my/data-catalogue/hies_district (`https://storage.dosm.gov.my/hies/hies_district.parquet`) | Income **and expenditure** per household → convenience-retail spend proxy |
| Poverty by district | https://open.dosm.gov.my/data-catalogue/hh_poverty_district | Absolute poverty rate → demand quality filter |
| Income inequality by district | https://open.dosm.gov.my/data-catalogue/hh_inequality_district | Gini → market homogeneity |

### 1.3 GitHub — DOSM `data-open` repo (github.com/dosm-malaysia/data-open)
| File | Path in repo | What we use it for |
|---|---|---|
| District boundaries (GeoJSON) | `datasets/geodata/administrative_2_district.geojson` | Spatial join: assign each store to a district; choropleth map |
| State boundaries (GeoJSON) | `datasets/geodata/administrative_1_state.geojson` | State-level roll-up map |
| Parlimen / DUN boundaries | `datasets/geodata/electoral_0_parlimen.geojson`, `electoral_1_dun.geojson` | Optional finer-grained analysis (DUNs are smaller than districts) |
| Census 2020 by district | `datasets/census/census_district.csv` | **Number of households** & living quarters per district |
| Census by parlimen / DUN | `datasets/census/census_parlimen.csv`, `census_dun.csv` | Households at finer grain if we analyse at DUN level |
| Name lookup tables | `datasets/geodata/state_district.csv` | Consistent state/district name keys for joins |

### 1.4 Suggested extra signals (recommended additions)
- **Population density** (population ÷ district area from the GeoJSON) — convenience stores live on density.
- **Age structure** — share of population aged 15–39 (core convenience/KK-mart demographic) from `population_district`.
- **Household expenditure** (from `hies_district`) — better than income alone for retail demand.
- **Competitor presence** — 99 Speedmart, 7-Eleven, KK Super Mart rivals, myNEWS from **OpenStreetMap Overpass API** (free) → true competitive whitespace, not just "no KKmart".
- **Foot-traffic anchors** from OSM: universities, hospitals, transit stations, petrol stations.
- **Urbanization / built-up areas** — optional, via DOSM urban population or OSM land use.
- **Growth** — population trend 2020→2024 per district (fast-growing districts = future demand).

---

## 2. Methodology

### Phase 1 — Data ingestion & cleaning
1. Load KKmart store CSV; validate coordinates (inside Malaysia bounding box, no swapped lat/lon, dedupe).
2. Download DOSM parquet/CSV + GeoJSON files with a reproducible script (`src/download_data.py`).
3. Standardize join keys using DOSM's `state_district.csv` (names differ between datasets — join on state+district codes, not raw strings).

### Phase 2 — Spatial join (supply)
4. Point-in-polygon join stores → `administrative_2_district.geojson` (GeoPandas `sjoin`).
5. Compute per district: **store count**, and later **stores per 100k population** and **stores per 10k households**.

### Phase 3 — Demand table (one row per district, ~160 districts)
| Column | Source |
|---|---|
| population (latest year, total + 15–39 share) | population_district |
| population CAGR 2020–2024 | population_district |
| households, living quarters | census_district.csv |
| median & mean household income | hh_income_district / hies_district |
| household expenditure | hies_district |
| poverty rate, gini | hh_poverty_district, hh_inequality_district |
| area km², population density | computed from GeoJSON |
| competitor count (optional) | OSM Overpass |

### Phase 4 — Whitespace scoring
6. Normalize each indicator (z-score or min-max) across districts.
7. **Demand index** = weighted sum, e.g.
   `0.30·population + 0.20·households + 0.20·density + 0.15·expenditure/income + 0.10·youth share + 0.05·growth`
   (weights configurable in one place; run sensitivity checks).
8. **Supply index** = stores per 100k population (KKmart only; optionally + competitors).
9. **Whitespace score = demand index − supply index** (or demand rank among districts with 0–low stores).
10. Classify districts: 🟢 *Prime whitespace* (high demand, zero stores) / 🟡 *Underserved* (high demand, few stores) / ⚪ *Saturated or low demand*.
11. Sanity checks: vintage mismatch (households = Census 2020, income = HIES 2022, population = 2024) — document it; W.P. Kuala Lumpur/Putrajaya/Labuan treated as their own districts.

### Phase 5 — Optional refinement
12. Re-run at **DUN level** (~600 units) for finer targeting using `census_dun.csv` + `electoral_1_dun.geojson` (note: income data isn't published at DUN level, so DUN pass uses population/household density only).
13. **Catchment analysis**: 2 km / 5 km buffers around existing stores → % of a district's area/population already covered, so big districts with one clustered store still show as whitespace.

### Phase 6 — Deliverables
14. **Interactive map** (`output/kkmart_whitespace_map.html`, Folium/Leaflet):
    - choropleth of whitespace score by district,
    - KKmart store markers (clustered),
    - tooltips with population, households, income, store count, rank.
15. **Ranking table** (`output/whitespace_ranking.csv` + top-20 in the report).
16. **Report** (`output/REPORT.md`): method, weights, top opportunities per state, caveats.
17. Clean, re-runnable pipeline: `make all` / `python -m src.pipeline`.

---

## 3. Proposed repo structure

```
KKmart-Map/
├── data/
│   ├── raw/                  # kkmart_stores_july.csv + downloaded DOSM files
│   └── processed/            # district_master.parquet (joined demand+supply table)
├── src/
│   ├── download_data.py      # fetch DOSM parquet/CSV + GeoJSON (idempotent)
│   ├── clean_stores.py       # validate/dedupe store coordinates
│   ├── build_district_table.py
│   ├── score.py              # demand/supply/whitespace scoring (weights as config)
│   └── make_map.py           # Folium map + outputs
├── notebooks/
│   └── whitespace_analysis.ipynb   # exploratory walkthrough of the same pipeline
├── output/                   # map HTML, ranking CSV, report
├── config.yaml               # scoring weights, buffer radii, data URLs
├── requirements.txt          # pandas, geopandas, shapely, pyarrow, folium, requests
└── WHITESPACE_ANALYSIS_PLAN.md
```

## 4. Execution order
1. ✅ Plan (this document)
2. Add store file to `data/raw/` ← **needs the `KKmart stores final july` file committed or shared**
3. Build downloader + district demand table (Phases 1–3)
4. Scoring + map + report (Phases 4, 6)
5. Optional: competitors from OSM, DUN-level pass, catchment buffers (Phase 5)

## 5. Caveats to keep in mind
- District names must be joined via DOSM lookup codes (spelling differs across files).
- Data vintages differ (Census 2020 households, HIES 2022 income, 2024 population) — fine for ranking, but label it.
- Districts are coarse (a whole district can hide urban/rural splits) — the DUN pass and buffer analysis mitigate this.
- OSM competitor coverage in Malaysia is good in urban areas but incomplete in rural ones — treat competitor counts as a lower bound.
