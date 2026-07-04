"""Compute demand, supply, saturation and whitespace scores per district.

Supply/saturation uses ALL convenience-store brands (KKmart + competitors)
from data/processed/all_stores_clean.csv when available, falling back to
KKmart-only (stores_clean.csv), or demand-only mode if neither exists.

Saturation: a district's total convenience stores per 100k population,
relative to the national rate. Above `saturated_ratio` = saturated;
below `open_ratio` = underserved/open.

Usage: python -m src.score
Output: output/whitespace_ranking.csv
"""
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

DEMAND_COLUMNS = {
    # weight key in config.yaml -> column in district_master.csv
    "population": "population",
    "households": "household_total",
    "density": "pop_density",
    "expenditure": "expenditure_mean",
    "youth_share": "youth_share",
    "growth": "pop_cagr",
}


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def minmax(s: pd.Series) -> pd.Series:
    rng = s.max() - s.min()
    if rng == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.min()) / rng


def district_key(d: pd.DataFrame) -> pd.Series:
    return (d["state"].str.strip() + "|" + d["district"].str.strip()).str.lower()


def load_store_counts(cfg: dict, master: pd.DataFrame) -> pd.DataFrame:
    """Attach kkmart_count, competitor_count, total_stores (and per-brand counts)."""
    processed = ROOT / cfg["paths"]["processed_dir"]
    master = master.copy()
    master["key"] = district_key(master)

    all_path = processed / "all_stores_clean.csv"
    kk_path = processed / "stores_clean.csv"

    if all_path.exists():
        stores = pd.read_csv(all_path)
        stores["key"] = district_key(stores)
        pivot = stores.pivot_table(index="key", columns="brand", aggfunc="size", fill_value=0)
        pivot.columns = [f"n_{c}" for c in pivot.columns]
        master = master.merge(pivot, on="key", how="left")
        brand_cols = list(pivot.columns)
        master[brand_cols] = master[brand_cols].fillna(0).astype(int)
        master["kkmart_count"] = master.get("n_KKmart", 0)
        master["total_stores"] = master[brand_cols].sum(axis=1)
        master["competitor_count"] = master["total_stores"] - master["kkmart_count"]
    elif kk_path.exists():
        print("  note: only KKmart stores available — saturation reflects KKmart only")
        stores = pd.read_csv(kk_path)
        stores["key"] = district_key(stores)
        counts = stores.groupby("key").size().rename("kkmart_count").reset_index()
        master = master.merge(counts, on="key", how="left")
        master["kkmart_count"] = master["kkmart_count"].fillna(0).astype(int)
        master["competitor_count"] = 0
        master["total_stores"] = master["kkmart_count"]
    else:
        print("  WARNING: no store data — running in DEMAND-ONLY mode.")
        master["kkmart_count"] = 0
        master["competitor_count"] = 0
        master["total_stores"] = 0

    return master.drop(columns=["key"])


def categorize(row: pd.Series, demand_median: float, sat_hi: float, sat_lo: float) -> str:
    if row["demand_index"] < demand_median:
        return "low_demand"
    if row["saturation_ratio"] >= sat_hi:
        return "saturated"
    if row["saturation_ratio"] < sat_lo:
        return "open_whitespace" if row["kkmart_count"] == 0 else "room_to_expand"
    return "competitor_led" if row["kkmart_count"] == 0 else "competitive"


def main() -> int:
    cfg = load_config()
    weights = cfg["demand_weights"]
    total_w = sum(weights.values())
    if abs(total_w - 1.0) > 1e-6:
        print(f"  note: demand weights sum to {total_w}, normalizing")
        weights = {k: v / total_w for k, v in weights.items()}

    master = pd.read_csv(ROOT / cfg["paths"]["processed_dir"] / "district_master.csv")

    # demand index: weighted sum of min-max normalized indicators
    demand = pd.Series(0.0, index=master.index)
    for wkey, col in DEMAND_COLUMNS.items():
        demand += weights[wkey] * minmax(master[col])
    master["demand_index"] = demand.round(4)

    master = load_store_counts(cfg, master)

    per = cfg["scoring"]["supply_per"]
    master["stores_per_100k"] = (master["total_stores"] / master["population"] * per).round(2)
    master["kkmart_per_100k"] = (master["kkmart_count"] / master["population"] * per).round(2)
    master["kkmart_share"] = (
        (master["kkmart_count"] / master["total_stores"]).fillna(0).round(3)
    )

    # saturation: district store density relative to the national rate
    national_rate = master["total_stores"].sum() / master["population"].sum() * per
    master["saturation_ratio"] = (master["stores_per_100k"] / national_rate).round(3)
    sat_hi = cfg["saturation"]["saturated_ratio"]
    sat_lo = cfg["saturation"]["open_ratio"]
    master["saturation_level"] = pd.cut(
        master["saturation_ratio"],
        bins=[-1, sat_lo, sat_hi, float("inf")],
        labels=["underserved", "balanced", "saturated"],
    )

    # whitespace: demand minus market-wide supply (all brands)
    master["supply_index"] = minmax(master["stores_per_100k"]).round(4)
    master["whitespace_score"] = (master["demand_index"] - master["supply_index"]).round(4)

    demand_median = master["demand_index"].median()
    master["category"] = master.apply(
        categorize, axis=1, demand_median=demand_median, sat_hi=sat_hi, sat_lo=sat_lo
    )

    master = master.sort_values("whitespace_score", ascending=False)
    master.insert(0, "rank", range(1, len(master) + 1))

    out_dir = ROOT / cfg["paths"]["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "whitespace_ranking.csv"
    master.to_csv(out, index=False)
    print(f"Saved {out}")
    print(f"National rate: {national_rate:.1f} convenience stores per 100k population")
    print("\nSaturation levels:", master["saturation_level"].value_counts().to_dict())
    print("Categories:", master["category"].value_counts().to_dict())

    cols = ["rank", "state", "district", "population", "kkmart_count", "competitor_count",
            "stores_per_100k", "saturation_ratio", "saturation_level",
            "demand_index", "whitespace_score", "category"]
    print("\nTop 15 opportunity districts (demand minus total market supply):")
    print(master[cols].head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
