"""Compute demand, supply and whitespace scores per district.

Runs in demand-only mode (with a warning) if the cleaned store file
doesn't exist yet, so the demand side can be inspected before the
KKmart store list is added.

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


def classify(row: pd.Series) -> str:
    if row["demand_index"] >= row["demand_median"]:
        if row["store_count"] == 0:
            return "prime_whitespace"
        if row["supply_index"] < row["supply_median"]:
            return "underserved"
        return "served"
    return "low_demand"


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

    # supply side
    stores_path = ROOT / cfg["paths"]["processed_dir"] / "stores_clean.csv"
    if stores_path.exists():
        stores = pd.read_csv(stores_path)
        counts = (
            stores.groupby(["state", "district"], as_index=False)
            .size()
            .rename(columns={"size": "store_count"})
        )
        key = lambda d: (d["state"].str.strip() + "|" + d["district"].str.strip()).str.lower()
        counts["key"] = key(counts)
        master["key"] = key(master)
        master = master.merge(counts[["key", "store_count"]], on="key", how="left").drop(columns=["key"])
        master["store_count"] = master["store_count"].fillna(0).astype(int)
    else:
        print("  WARNING: no stores_clean.csv — running in DEMAND-ONLY mode (store_count=0 everywhere).")
        print("  Add the store file and run: python -m src.clean_stores")
        master["store_count"] = 0

    per = cfg["scoring"]["supply_per"]
    master["stores_per_100k"] = (master["store_count"] / master["population"] * per).round(3)
    master["supply_index"] = minmax(master["stores_per_100k"]).round(4)

    master["whitespace_score"] = (master["demand_index"] - master["supply_index"]).round(4)
    master["demand_median"] = master["demand_index"].median()
    master["supply_median"] = master.loc[master["store_count"] > 0, "supply_index"].median() if (master["store_count"] > 0).any() else 0.0
    master["category"] = master.apply(classify, axis=1)
    master = master.drop(columns=["demand_median", "supply_median"])

    master = master.sort_values("whitespace_score", ascending=False)
    master.insert(0, "rank", range(1, len(master) + 1))

    out_dir = ROOT / cfg["paths"]["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "whitespace_ranking.csv"
    master.to_csv(out, index=False)

    print(f"Saved {out}")
    cols = ["rank", "state", "district", "population", "household_total",
            "income_median", "store_count", "demand_index", "whitespace_score", "category"]
    print("\nTop 15 whitespace districts:")
    print(master[cols].head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
