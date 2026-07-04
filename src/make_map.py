"""Build the interactive whitespace map (choropleth + store markers).

Works without the store file (demand-only choropleth); store markers
are added automatically once data/processed/stores_clean.csv exists.

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
        legend_name="Whitespace score (higher = bigger opportunity)",
        name="Whitespace score",
    ).add_to(m)

    tooltip = folium.GeoJsonTooltip(
        fields=["rank", "state", "district", "population", "household_total",
                "income_median", "expenditure_mean", "store_count",
                "demand_index", "whitespace_score", "category"],
        aliases=["Rank", "State", "District", "Population (2024)", "Households (2020)",
                 "Median income (RM, 2022)", "Mean expenditure (RM, 2022)", "KKmart stores",
                 "Demand index", "Whitespace score", "Category"],
        localize=True,
    )
    folium.GeoJson(
        gdf,
        style_function=lambda _: {"fillOpacity": 0, "color": "#00000000"},
        tooltip=tooltip,
        name="District details",
    ).add_to(m)

    stores_path = ROOT / cfg["paths"]["processed_dir"] / "stores_clean.csv"
    if stores_path.exists():
        stores = pd.read_csv(stores_path)
        cluster = MarkerCluster(name="KKmart stores").add_to(m)
        for _, s in stores.iterrows():
            folium.CircleMarker(
                location=[s["latitude"], s["longitude"]],
                radius=4,
                color="#1f6feb",
                fill=True,
                fill_opacity=0.9,
                popup=folium.Popup(f"<b>{s['name']}</b><br>{s.get('address', '')}", max_width=300),
            ).add_to(cluster)
        print(f"  added {len(stores)} store markers")
    else:
        print("  no stores_clean.csv — map shows demand choropleth only")

    folium.LayerControl().add_to(m)
    out = out_dir / "kkmart_whitespace_map.html"
    m.save(str(out))
    print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
