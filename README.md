# KKmart Whitespace Analysis

Identifies districts in Malaysia with strong retail demand but weak/no KKmart presence,
using DOSM open data (population, households, income, expenditure), the KKmart store list,
and competitor locations (7-Eleven, 99 Speedmart, FamilyMart, myNEWS) for market saturation.

**Saturation**: each district's total convenience stores per 100k population, relative to
the national rate (~22.5/100k). Above 1.2x = saturated, below 0.5x = underserved/open
(thresholds in `config.yaml`). Districts are then categorized: `open_whitespace`,
`room_to_expand`, `competitor_led`, `competitive`, `saturated`, `low_demand`.

See [WHITESPACE_ANALYSIS_PLAN.md](WHITESPACE_ANALYSIS_PLAN.md) for the full methodology.

## Setup

```bash
pip install -r requirements.txt
```

## Add the store data

Place the `KKmart stores final july` file at `data/raw/kkmart_stores_july.csv`
(CSV or XLSX; columns: name, address, longitude, latitude — if the column names differ,
edit `store_columns` in `config.yaml`).

## Run

```bash
python -m src.pipeline
```

This downloads the DOSM datasets, builds the district demand table, cleans and
spatially joins the stores, scores all 160 districts, and writes:

- `output/whitespace_ranking.csv` — districts ranked by whitespace score
- `output/kkmart_whitespace_map.html` — interactive choropleth + store markers

Until the store file is added, the pipeline runs in **demand-only mode**
(ranking reflects pure demand; no supply subtraction).

Scoring weights and settings live in `config.yaml`.
