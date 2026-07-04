"""Build the interactive whitespace + saturation map.

Choropleth of whitespace score (demand minus total market supply), with
toggleable clustered marker layers per brand (KKmart + competitors) and
district tooltips including saturation metrics.

Usage: python -m src.make_map
Output: output/kkmart_whitespace_map.html
"""
import sys
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import yaml
from folium.plugins import MarkerCluster

ROOT = Path(__file__).resolve().parents[1]

BRAND_COLORS = {
    "KKmart": "#1f6feb",       # blue (ours)
    "7-Eleven": "#e8590c",     # orange
    "99 Speedmart": "#2f9e44", # green
    "FamilyMart": "#9c36b5",   # purple
    "myNEWS": "#c92a2a",       # red
}


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def main() -> int:
    cfg = load_config()
    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    out_dir = ROOT / cfg["paths"]["output_dir"]
    ranking = pd.read_csv(out_dir / "whitespace_ranking.csv")

    districts = gpd.read_file(raw_dir / "district_geojson.geojson")
    key = lambda d: (d["state"].str.strip() + "|" + d["district"].str.strip()).str.lower()
    districts["key"] = key(districts)
    ranking["key"] = key(ranking)
    gdf = districts[["key", "geometry"]].merge(ranking, on="key")
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")
    # keep geometry light for the HTML
    gdf["geometry"] = gdf["geometry"].simplify(0.002)

    m = folium.Map(location=[4.2, 108.0], zoom_start=6, tiles="cartodbpositron")

    folium.Choropleth(
        geo_data=gdf.to_json(),
        data=gdf,
        columns=["key", "whitespace_score"],
        key_on="feature.properties.key",
        fill_color="YlOrRd",
        fill_opacity=0.75,
        line_opacity=0.3,
        legend_name="Whitespace score (demand minus total market supply)",
        name="Whitespace score",
    ).add_to(m)

    tooltip_fields = [
        ("rank", "Rank"),
        ("state", "State"),
        ("district", "District"),
        ("population", "Population (2024)"),
        ("household_total", "Households (2020)"),
        ("income_median", "Median income (RM, 2022)"),
        ("kkmart_count", "KKmart stores"),
        ("competitor_count", "Competitor stores"),
        ("stores_per_100k", "Stores per 100k pop"),
        ("saturation_ratio", "Saturation vs national"),
        ("saturation_level", "Saturation level"),
        ("demand_index", "Demand index"),
        ("whitespace_score", "Whitespace score"),
        ("category", "Category"),
    ]
    tooltip_fields = [(f, a) for f, a in tooltip_fields if f in gdf.columns]
    folium.GeoJson(
        gdf,
        style_function=lambda _: {"fillOpacity": 0, "color": "#00000000"},
        tooltip=folium.GeoJsonTooltip(
            fields=[f for f, _ in tooltip_fields],
            aliases=[a for _, a in tooltip_fields],
            localize=True,
        ),
        name="District details",
    ).add_to(m)

    stores_path = ROOT / cfg["paths"]["processed_dir"] / "all_stores_clean.csv"
    if not stores_path.exists():
        stores_path = ROOT / cfg["paths"]["processed_dir"] / "stores_clean.csv"

    if stores_path.exists():
        stores = pd.read_csv(stores_path)
        if "brand" not in stores.columns:
            stores["brand"] = "KKmart"
        for brand, group in stores.groupby("brand"):
            color = BRAND_COLORS.get(brand, "#495057")
            show = brand == "KKmart"  # competitors start toggled off to keep the map readable
            cluster = MarkerCluster(name=f"{brand} ({len(group)})", show=show).add_to(m)
            for _, s in group.iterrows():
                folium.CircleMarker(
                    location=[s["latitude"], s["longitude"]],
                    radius=4,
                    color=color,
                    fill=True,
                    fill_opacity=0.9,
                    popup=folium.Popup(
                        f"<b>[{brand}] {s['name']}</b><br>{s.get('address', '')}", max_width=300
                    ),
                ).add_to(cluster)
            print(f"  {brand}: {len(group)} markers")
    else:
        print("  no store data — map shows demand choropleth only")

    folium.LayerControl(collapsed=False).add_to(m)
    out = out_dir / "kkmart_whitespace_map.html"
    m.save(str(out))
    print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
