"""Build the interactive whitespace + saturation map.

Single-hue red choropleth of whitespace score (demand minus total market
supply), brand-colored clustered store markers, a header, a custom legend,
and an interactive "where is the whitespace" panel with fly-to hotspots.

Usage: python -m src.make_map
Output: output/kkmart_whitespace_map.html (+ docs/index.html for GitHub Pages)
"""
import sys
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import yaml
from branca.colormap import LinearColormap
from folium.plugins import Fullscreen, MarkerCluster

ROOT = Path(__file__).resolve().parents[1]

# categorical palette validated with the dataviz six-checks script
# (worst adjacent CVD deltaE 24.2 on the light surface)
BRAND_COLORS = {
    "KKmart": "#2a78d6",       # blue (ours)
    "7-Eleven": "#1baf7a",     # aqua
    "99 Speedmart": "#eda100", # yellow
    "FamilyMart": "#008300",   # green
    "myNEWS": "#4a3aa7",       # violet
}

# ColorBrewer Reds — sequential single-hue ramp for the choropleth
REDS = ["#fff5f0", "#fee0d2", "#fcbba1", "#fc9272", "#fb6a4a", "#ef3b2c", "#cb181d"]

HOTSPOTS = [
    ("Kelantan coast cluster", 6.10, 102.25, 10,
     "Kota Bharu, Pasir Mas, Tumpat, Bachok — 1.2M people at less than half the "
     "Peninsular store density, zero KKmart."),
    ("Greater Kota Kinabalu", 5.95, 116.10, 10,
     "1.1M-person metro, 191 competitor stores, zero KKmart — largest "
     "competitor-proven market not yet entered."),
    ("Sabah east coast", 4.60, 118.10, 8,
     "Tawau, Semporna, Lahad Datu — the deepest whitespace in Malaysia "
     "(~2 stores per 100k people)."),
    ("Northern corridor", 5.85, 100.45, 9,
     "Alor Setar, Sungai Petani, Kulim, Perlis — competitor-validated, "
     "KKmart nearly absent; adjoins the Penang focus state."),
    ("Penang", 5.35, 100.40, 10,
     "Georgetown (+55 store headroom) and mainland Seberang Perai — the biggest "
     "urban under-supply in the North."),
    ("Johor secondary towns", 2.05, 102.90, 9,
     "Batu Pahat, Muar, Kluang, Kota Tinggi — ~120-store headroom while "
     "Johor Bahru itself is saturated."),
]


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def cluster_js(color: str) -> str:
    """Brand-colored cluster icon."""
    return (
        "function(cluster) {"
        "  var n = cluster.getChildCount();"
        f" return new L.DivIcon({{html: '<div style=\"background:{color}\">' + n + '</div>',"
        "   className: 'brand-cluster', iconSize: new L.Point(34, 34)});"
        "}"
    )


def build_panel_html(map_var: str, brand_counts: dict, score_max: float) -> str:
    dots = "".join(
        f'<div class="lg-row"><span class="dot" style="background:{c}"></span>'
        f"{b}<span class='lg-n'>{brand_counts.get(b, 0):,}</span></div>"
        for b, c in BRAND_COLORS.items()
    )
    grad = ", ".join(REDS)
    spots = "".join(
        f"<button class='spot' onclick=\"{map_var}.flyTo([{lat},{lon}],{zoom})\">"
        f"<span class='spot-t'>{name}</span><span class='spot-d'>{desc}</span></button>"
        for name, lat, lon, zoom, desc in HOTSPOTS
    )
    return f"""
<style>
  .brand-cluster div {{
    width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: #fff; font: 600 12px/1 system-ui, -apple-system, "Segoe UI", sans-serif;
    border: 2px solid #fcfcfb; box-shadow: 0 1px 4px rgba(11,11,11,.35);
  }}
  .kk-card {{
    position: absolute; z-index: 1000;
    background: rgba(252,252,251,.96); backdrop-filter: blur(4px);
    border: 1px solid rgba(11,11,11,.10); border-radius: 10px;
    box-shadow: 0 2px 10px rgba(11,11,11,.12);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #0b0b0b;
  }}
  #kk-header {{ top: 12px; left: 50%; transform: translateX(-50%);
    padding: 10px 18px; text-align: center; max-width: min(92vw, 640px); }}
  #kk-header h1 {{ margin: 0; font-size: 16px; font-weight: 700; }}
  #kk-header p {{ margin: 2px 0 0; font-size: 11.5px; color: #52514e; }}
  #kk-legend {{ bottom: 24px; left: 12px; padding: 12px 14px; width: 216px; }}
  #kk-legend h2, #kk-panel h2 {{ margin: 0 0 8px; font-size: 12px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .04em; color: #52514e; }}
  .lg-row {{ display: flex; align-items: center; gap: 8px; font-size: 12.5px; padding: 2.5px 0; }}
  .lg-n {{ margin-left: auto; color: #898781; font-variant-numeric: tabular-nums; }}
  .dot {{ width: 11px; height: 11px; border-radius: 50%; flex: none;
    box-shadow: 0 0 0 1.5px #fcfcfb, 0 0 0 2.5px rgba(11,11,11,.15); }}
  .lg-ramp {{ height: 10px; border-radius: 5px; margin: 10px 0 4px;
    background: linear-gradient(90deg, {grad}); border: 1px solid rgba(11,11,11,.08); }}
  .lg-scale {{ display: flex; justify-content: space-between; font-size: 10.5px; color: #898781; }}
  .lg-note {{ font-size: 11px; color: #52514e; margin-top: 6px; line-height: 1.35; }}
  #kk-panel {{ top: 76px; right: 12px; width: 264px; max-height: calc(100% - 140px);
    display: flex; flex-direction: column; }}
  #kk-panel-head {{ padding: 11px 14px; cursor: pointer; display: flex;
    align-items: center; user-select: none; }}
  #kk-panel-head h2 {{ margin: 0; }}
  #kk-panel-head .chev {{ margin-left: auto; color: #898781; font-size: 11px;
    transition: transform .2s; }}
  #kk-panel.closed .chev {{ transform: rotate(-90deg); }}
  #kk-panel-body {{ overflow-y: auto; padding: 0 10px 10px; }}
  #kk-panel.closed #kk-panel-body {{ display: none; }}
  #kk-panel-body .intro {{ font-size: 11.5px; color: #52514e; margin: 0 4px 8px; line-height: 1.4; }}
  .spot {{ display: block; width: 100%; text-align: left; background: none;
    border: 1px solid rgba(11,11,11,.08); border-radius: 8px; padding: 8px 10px;
    margin-bottom: 6px; cursor: pointer; font-family: inherit; }}
  .spot:hover {{ background: rgba(42,120,214,.07); border-color: rgba(42,120,214,.45); }}
  .spot-t {{ display: block; font-size: 12.5px; font-weight: 650; color: #0b0b0b; }}
  .spot-t::before {{ content: '\\2192\\00a0'; color: #2a78d6; }}
  .spot-d {{ display: block; font-size: 11px; color: #52514e; margin-top: 2px; line-height: 1.35; }}
  @media (max-width: 640px) {{
    #kk-header {{ top: 8px; padding: 7px 12px; max-width: 86vw; }}
    #kk-header h1 {{ font-size: 12.5px; }}
    #kk-header p {{ display: none; }}
    #kk-panel {{ width: min(80vw, 264px); top: 64px; max-height: calc(100% - 120px); }}
    #kk-legend {{ width: 178px; bottom: 16px; padding: 10px 12px; }}
    .lg-note {{ display: none; }}
  }}
</style>
<script>
  // start the hotspot panel collapsed on small screens
  document.addEventListener('DOMContentLoaded', function() {{
    if (window.innerWidth < 640) document.getElementById('kk-panel').classList.add('closed');
  }});
</script>
<div id="kk-header" class="kk-card">
  <h1>KKmart Whitespace &amp; Market Saturation — Malaysia</h1>
  <p>Demand (DOSM population, households, income) vs 7,667 stores across 5 chains, by district</p>
</div>
<div id="kk-legend" class="kk-card">
  <h2>Store networks</h2>
  {dots}
  <h2 style="margin-top:12px">Whitespace score</h2>
  <div class="lg-ramp"></div>
  <div class="lg-scale"><span>0 (supplied)</span><span>{score_max:.2f} (gap)</span></div>
  <div class="lg-note">Deeper red = more unmet demand (high population, households &amp;
  spending, few stores from any chain). Palest = demand already met or
  over-supplied. Hover a district for details.</div>
</div>
<div id="kk-panel" class="kk-card">
  <div id="kk-panel-head" onclick="document.getElementById('kk-panel').classList.toggle('closed')">
    <h2>Where is the whitespace?</h2><span class="chev">&#9660;</span>
  </div>
  <div id="kk-panel-body">
    <p class="intro">The biggest gaps between consumer demand and store supply.
    Tap a hotspot to fly there, then toggle store layers in the layer control.</p>
    {spots}
  </div>
</div>
"""


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
    gdf["geometry"] = gdf["geometry"].simplify(0.002)

    m = folium.Map(location=[4.2, 108.0], zoom_start=6, tiles="cartodbpositron",
                   zoom_control=True, control_scale=True)
    Fullscreen(position="topleft").add_to(m)

    smax = gdf["whitespace_score"].max()
    cmap = LinearColormap(REDS, vmin=0, vmax=smax)  # scores <= 0 mean supplied/over-supplied

    tooltip_fields = [
        ("rank", "Rank"), ("state", "State"), ("district", "District"),
        ("population", "Population (2025)"), ("household_total", "Households (2020)"),
        ("income_median", "Median income (RM, 2024)"),
        ("kkmart_count", "KKmart stores"), ("competitor_count", "Competitor stores"),
        ("stores_per_100k", "Stores per 100k pop"),
        ("saturation_level", "Saturation level"),
        ("whitespace_score", "Whitespace score"), ("category", "Category"),
    ]
    tooltip_fields = [(f, a) for f, a in tooltip_fields if f in gdf.columns]
    folium.GeoJson(
        gdf,
        style_function=lambda feat: {
            "fillColor": cmap(max(0.0, feat["properties"]["whitespace_score"])),
            "fillOpacity": 0.78,
            "color": "#c3c2b7",
            "weight": 0.7,
        },
        highlight_function=lambda feat: {"weight": 2, "color": "#0b0b0b", "fillOpacity": 0.85},
        tooltip=folium.GeoJsonTooltip(
            fields=[f for f, _ in tooltip_fields],
            aliases=[a for _, a in tooltip_fields],
            localize=True,
        ),
        name="Whitespace score (districts)",
    ).add_to(m)

    stores_path = ROOT / cfg["paths"]["processed_dir"] / "all_stores_clean.csv"
    brand_counts = {}
    if stores_path.exists():
        stores = pd.read_csv(stores_path)
        for brand, group in stores.groupby("brand"):
            color = BRAND_COLORS.get(brand, "#52514e")
            brand_counts[brand] = len(group)
            cluster = MarkerCluster(
                name=f"{brand} ({len(group):,})",
                show=(brand == "KKmart"),
                icon_create_function=cluster_js(color),
            ).add_to(m)
            for _, s in group.iterrows():
                folium.CircleMarker(
                    location=[s["latitude"], s["longitude"]],
                    radius=5,
                    color="#fcfcfb", weight=1.5,
                    fill=True, fill_color=color, fill_opacity=0.95,
                    popup=folium.Popup(
                        f"<b>[{brand}] {s['name']}</b><br>{s.get('address', '')}", max_width=300
                    ),
                ).add_to(cluster)
            print(f"  {brand}: {len(group)} markers")
    else:
        print("  no store data — map shows demand choropleth only")

    folium.LayerControl(collapsed=True).add_to(m)
    m.get_root().html.add_child(
        folium.Element(build_panel_html(m.get_name(), brand_counts, smax))
    )

    out = out_dir / "kkmart_whitespace_map.html"
    m.save(str(out))
    print(f"Saved {out}")

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "index.html").write_bytes(out.read_bytes())
    print(f"Saved {docs / 'index.html'} (GitHub Pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
