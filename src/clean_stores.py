"""Load, validate and spatially join the KKmart store list to districts.

Usage: python -m src.clean_stores
Output: data/processed/stores_clean.csv (with state/district columns added)
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

# Malaysia bounding box (generous)
LON_MIN, LON_MAX = 99.0, 120.0
LAT_MIN, LAT_MAX = 0.8, 7.5


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def load_stores(cfg: dict) -> pd.DataFrame:
    path = ROOT / cfg["paths"]["stores_csv"]
    if not path.exists():
        raise FileNotFoundError(
            f"Store file not found: {path}\n"
            "Add the 'KKmart stores final july' file as data/raw/kkmart_stores_july.csv "
            "(columns: name, address, longitude, latitude — adjust config.yaml store_columns if named differently)."
        )
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    cols = cfg["store_columns"]
    df = df.rename(columns={v: k for k, v in cols.items()})
    required = ["name", "longitude", "latitude"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Store file is missing columns {missing}. Found: {list(df.columns)}. "
                         "Update store_columns in config.yaml to match.")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    n0 = len(df)
    df = df.dropna(subset=["longitude", "latitude"]).copy()
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df = df.dropna(subset=["longitude", "latitude"])

    # fix obviously swapped coordinates
    swapped = df["latitude"].between(LON_MIN, LON_MAX) & df["longitude"].between(LAT_MIN, LAT_MAX)
    if swapped.any():
        df.loc[swapped, ["longitude", "latitude"]] = df.loc[swapped, ["latitude", "longitude"]].values
        print(f"  fixed {swapped.sum()} rows with swapped lat/lon")

    in_box = df["longitude"].between(LON_MIN, LON_MAX) & df["latitude"].between(LAT_MIN, LAT_MAX)
    if (~in_box).any():
        print(f"  WARNING: dropping {(~in_box).sum()} rows outside Malaysia bounding box:")
        print(df.loc[~in_box, ["name", "longitude", "latitude"]].to_string(index=False))
    df = df[in_box]

    dupes = df.duplicated(subset=["longitude", "latitude"], keep="first")
    if dupes.any():
        print(f"  note: {dupes.sum()} rows share exact coordinates with another store (kept — may be co-located)")

    print(f"  {n0} rows in, {len(df)} rows out")
    return df


def spatial_join(df: pd.DataFrame, raw_dir: Path) -> gpd.GeoDataFrame:
    districts = gpd.read_file(raw_dir / "district_geojson.geojson")
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]), crs="EPSG:4326"
    )
    joined = gpd.sjoin(gdf, districts[["state", "district", "geometry"]], how="left", predicate="within")
    unmatched = joined["district"].isna()
    if unmatched.any():
        # coastal stores can fall just outside polygons; snap to nearest district
        print(f"  {unmatched.sum()} stores outside all district polygons — snapping to nearest")
        near = gpd.sjoin_nearest(
            gdf[unmatched].drop(columns=[c for c in ("index_right",) if c in gdf.columns]).to_crs(3857),
            districts[["state", "district", "geometry"]].to_crs(3857),
            how="left",
        )
        joined.loc[unmatched, ["state", "district"]] = near[["state", "district"]].values
    return joined.drop(columns=["index_right", "geometry"])


def main() -> int:
    cfg = load_config()
    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    processed_dir = ROOT / cfg["paths"]["processed_dir"]
    processed_dir.mkdir(parents=True, exist_ok=True)

    print("Loading stores...")
    stores = load_stores(cfg)
    print("Cleaning...")
    stores = clean(stores)
    print("Spatial join to districts...")
    stores = spatial_join(stores, raw_dir)

    out = processed_dir / "stores_clean.csv"
    stores.to_csv(out, index=False)
    print(f"Saved {out} ({len(stores)} stores across {stores['district'].nunique()} districts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
