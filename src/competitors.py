"""Load all convenience-store brands (KKmart + competitors), clean and
spatially join them to districts.

Usage: python -m src.competitors
Output: data/processed/all_stores_clean.csv (columns: brand, name, address,
        longitude, latitude, state, district)
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.clean_stores import ROOT, clean, load_config, spatial_join


def load_brand(brand: str, spec: dict) -> pd.DataFrame:
    path = ROOT / spec["path"]
    if not path.exists():
        print(f"  WARNING: {brand} file missing ({spec['path']}) — skipped")
        return pd.DataFrame()
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={spec["name_col"]: "name"})
    keep = [c for c in ("name", "Address", "Latitude", "Longitude") if c in df.columns]
    df = df[keep].rename(columns={"Address": "address", "Latitude": "latitude", "Longitude": "longitude"})
    df.insert(0, "brand", brand)
    return df


def main() -> int:
    cfg = load_config()
    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    processed_dir = ROOT / cfg["paths"]["processed_dir"]
    processed_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    for brand, spec in cfg["brands"].items():
        df = load_brand(brand, spec)
        if df.empty:
            continue
        print(f"{brand}: {len(df)} rows")
        df = clean(df)
        frames.append(df)

    stores = pd.concat(frames, ignore_index=True)
    print(f"\nTotal: {len(stores)} stores across {stores['brand'].nunique()} brands")
    print("Spatial join to districts...")
    stores = spatial_join(stores, raw_dir)

    out = processed_dir / "all_stores_clean.csv"
    stores.to_csv(out, index=False)
    print(f"Saved {out}")
    print(stores.groupby("brand").size().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
