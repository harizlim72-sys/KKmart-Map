"""Peninsular Malaysia focus analysis: Northern (Pulau Pinang) and Southern (Johor)
expansion corridors per management guidance.

Adds Peninsular-only benchmarks and store headroom:
  headroom_to_par  = stores the district can absorb before reaching the Peninsular
                     average density (negative = overshoot / saturated)
  kkmart_fair_gap  = stores KKmart would need for its Peninsular network share (~14%)
                     of the district's current store base

Usage: python -m src.focus_region
Outputs: output/focus_peninsular_ranking.csv, output/focus_penang_johor.csv
"""
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

EAST = {"Sabah", "Sarawak", "W.P. Labuan"}
NORTH = {"Perlis", "Kedah", "Pulau Pinang", "Perak"}
SOUTH = {"Johor", "Melaka"}
FOCUS_STATES = ["Pulau Pinang", "Johor"]


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def main() -> int:
    r = pd.read_csv(ROOT / "output" / "whitespace_ranking.csv")

    pen = r[~r["state"].isin(EAST)].copy()
    pen_rate = pen["total_stores"].sum() / pen["population"].sum() * 100000
    kk_share = pen["kkmart_count"].sum() / pen["total_stores"].sum()
    print(f"Peninsular benchmark: {pen_rate:.1f} stores/100k "
          f"(national: {r['total_stores'].sum() / r['population'].sum() * 1e5:.1f})")
    print(f"KKmart Peninsular network share: {kk_share:.1%}\n")

    pen["region"] = pen["state"].map(
        lambda s: "North" if s in NORTH else ("South" if s in SOUTH else "Central/East Coast")
    )
    pen["saturation_vs_peninsular"] = (pen["stores_per_100k"] / pen_rate).round(3)
    pen["headroom_to_par"] = (
        pen_rate * pen["population"] / 100000 - pen["total_stores"]
    ).round(0).astype(int)
    pen["kkmart_fair_gap"] = (
        (kk_share * pen["total_stores"]).round(0).astype(int) - pen["kkmart_count"]
    ).clip(lower=0)
    pen = pen.sort_values("whitespace_score", ascending=False)
    pen.insert(0, "peninsular_rank", range(1, len(pen) + 1))
    pen = pen.drop(columns=["rank"])

    out_dir = ROOT / "output"
    pen.to_csv(out_dir / "focus_peninsular_ranking.csv", index=False)

    cols = ["peninsular_rank", "state", "district", "population", "income_median",
            "kkmart_count", "competitor_count", "stores_per_100k",
            "saturation_vs_peninsular", "saturation_level",
            "headroom_to_par", "kkmart_fair_gap", "category"]

    focus = pen[pen["state"].isin(FOCUS_STATES)].sort_values(
        ["state", "whitespace_score"], ascending=[True, False]
    )
    focus[cols].to_csv(out_dir / "focus_penang_johor.csv", index=False)
    print(f"Saved {out_dir / 'focus_peninsular_ranking.csv'} and focus_penang_johor.csv\n")

    for state in FOCUS_STATES:
        sub = focus[focus["state"] == state]
        print(f"=== {state} ===")
        print(sub[["district", "population", "kkmart_count", "competitor_count",
                   "stores_per_100k", "saturation_vs_peninsular", "saturation_level",
                   "headroom_to_par", "kkmart_fair_gap", "category"]].to_string(index=False))
        print()

    print("=== Top 15 Peninsular whitespace (North + South only) ===")
    ns = pen[pen["region"].isin(["North", "South"])]
    print(ns[cols].head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
