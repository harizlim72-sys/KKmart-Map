"""Build the district-level demand table for the whitespace analysis.

Joins DOSM population (latest vintage), Census 2020 households, and the
latest HIES income/expenditure onto the 160 administrative districts.

Output: data/processed/district_master.csv
Usage: python -m src.build_district_table
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

YOUTH_AGES = ["15-19", "20-24", "25-29", "30-34", "35-39"]

# Newer DOSM vintages use variant district names; canonicalize to the
# GeoJSON boundary names, keyed on (state, district) where ambiguous.
NAME_FIXES = {
    ("Pahang", "Cameron Highland"): "Cameron Highlands",
    ("Pulau Pinang", "Sp Selatan"): "Seberang Perai Selatan",
    ("Pulau Pinang", "Sp Tengah"): "Seberang Perai Tengah",
    ("Pulau Pinang", "Sp Utara"): "Seberang Perai Utara",
    ("Pulau Pinang", "S.P. Selatan"): "Seberang Perai Selatan",
    ("Pulau Pinang", "S.P.Tengah"): "Seberang Perai Tengah",
    ("Pulau Pinang", "S.P.Utara"): "Seberang Perai Utara",
    ("Perak", "Larut & Matang"): "Larut Dan Matang",
    ("Terengganu", "Hulu"): "Hulu Terengganu",
    ("Sarawak", "Lubok antu"): "Lubok Antu",
}


def fix_names(df: pd.DataFrame) -> pd.DataFrame:
    fixed = df["district"].str.strip()
    keys = list(zip(df["state"].str.strip(), fixed))
    df = df.copy()
    df["district"] = [NAME_FIXES.get(k, d) for k, d in zip(keys, fixed)]
    return df


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def join_key(df: pd.DataFrame) -> pd.Series:
    """Case-insensitive state|district key (handles 'Larut dan Matang' vs 'Larut Dan Matang')."""
    return (df["state"].str.strip() + "|" + df["district"].str.strip()).str.lower()


def build_population(raw_dir: Path, year: int) -> pd.DataFrame:
    pop = fix_names(pd.read_parquet(raw_dir / "population_district.parquet"))
    pop["year"] = pd.to_datetime(pop["date"]).dt.year
    # name fixes can leave the same district under two spellings in one year
    pop = pop.drop_duplicates(subset=["state", "district", "year", "sex", "age", "ethnicity"])
    both = pop[(pop["sex"] == "both") & (pop["ethnicity"] == "overall")]

    total = both[both["age"] == "overall"]
    latest = total[total["year"] == year][["state", "district", "population"]].rename(
        columns={"population": "population_k"}
    )

    # population is in thousands
    latest["population"] = latest["population_k"] * 1000

    base_year = int(total["year"].min())
    base = total[total["year"] == base_year][["state", "district", "population"]].rename(
        columns={"population": "pop_base_k"}
    )
    latest = latest.merge(base, on=["state", "district"], how="left")
    n_years = year - base_year
    latest["pop_cagr"] = (latest["population_k"] / latest["pop_base_k"]) ** (1 / n_years) - 1

    youth = (
        both[(both["age"].isin(YOUTH_AGES)) & (both["year"] == year)]
        .groupby(["state", "district"], as_index=False)["population"]
        .sum()
        .rename(columns={"population": "youth_k"})
    )
    latest = latest.merge(youth, on=["state", "district"], how="left")
    latest["youth_share"] = latest["youth_k"] / latest["population_k"]

    return latest[["state", "district", "population", "pop_cagr", "youth_share"]]


def build_census(raw_dir: Path) -> pd.DataFrame:
    cen = pd.read_csv(raw_dir / "census_district.csv")
    cen = cen.loc[:, ~cen.columns.str.startswith("Unnamed")]
    cen2020 = cen[cen["year"] == 2020]
    out = cen2020[
        ["state", "district", "household_total", "housing_total", "household_size_avg", "area_km2"]
    ].copy()
    out["key"] = join_key(out)
    return out.drop(columns=["state", "district"])


def build_hies(raw_dir: Path) -> pd.DataFrame:
    hies = fix_names(pd.read_parquet(raw_dir / "hies_district.parquet"))
    latest, prev = hies["date"].max(), hies["date"].min()
    cols = ["income_mean", "income_median", "expenditure_mean", "gini", "poverty"]

    cur = hies[hies["date"] == latest].copy()
    cur["income_year"] = pd.to_datetime(latest).year
    # some districts (Perlis, W.P. KL/Labuan/Putrajaya) are absent from the
    # latest vintage — fall back to the previous survey for those only
    old = hies[hies["date"] == prev].copy()
    old["income_year"] = pd.to_datetime(prev).year
    missing = old[~join_key(old).isin(set(join_key(cur)))]
    if len(missing):
        print(f"  HIES: {len(cur)} districts from {cur['income_year'].iat[0]}, "
              f"{len(missing)} filled from {old['income_year'].iat[0]}: "
              + ", ".join(missing["district"]))
    out = pd.concat([cur, missing])[["state", "district", "income_year"] + cols]
    out["key"] = join_key(out)
    return out.drop(columns=["state", "district"])


def main() -> int:
    cfg = load_config()
    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    processed_dir = ROOT / cfg["paths"]["processed_dir"]
    processed_dir.mkdir(parents=True, exist_ok=True)
    year = cfg["scoring"]["population_year"]

    districts = gpd.read_file(raw_dir / "district_geojson.geojson")
    master = districts[["state", "district", "code_state_district"]].copy()
    master["key"] = join_key(master)

    pop = build_population(raw_dir, year)
    pop["key"] = join_key(pop)
    master = master.merge(pop.drop(columns=["state", "district"]), on="key", how="left")
    master = master.merge(build_census(raw_dir), on="key", how="left")
    master = master.merge(build_hies(raw_dir), on="key", how="left")

    master["pop_density"] = master["population"] / master["area_km2"]

    out_path = processed_dir / "district_master.csv"
    master.drop(columns=["key"]).to_csv(out_path, index=False)

    missing = master.isna().sum()
    print(f"Built {out_path} with {len(master)} districts, population year {year}")
    print("Missing values per column:")
    print(missing[missing > 0].to_string() if missing.any() else "  none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
