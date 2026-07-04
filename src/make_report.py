"""Generate the whitespace analysis report as a Word document.

Usage: python -m src.make_report
Output: output/KKmart_Whitespace_Report.docx
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
NAVY = RGBColor(0x1F, 0x3A, 0x5F)


def add_heading(doc, text, level):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = NAVY
    return h


def add_table(doc, df, col_widths=None):
    table = doc.add_table(rows=1, cols=len(df.columns))
    table.style = "Light Grid Accent 1"
    for i, col in enumerate(df.columns):
        cell = table.rows[0].cells[i]
        cell.text = str(col)
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.size = Pt(9)
    for _, row in df.iterrows():
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
            for p in cells[i].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
    return table


def fmt_pop(x):
    return f"{x/1000:,.0f}k"


def main() -> int:
    r = pd.read_csv(ROOT / "output" / "whitespace_ranking.csv")

    total = int(r["total_stores"].sum())
    kk = int(r["kkmart_count"].sum())
    comp = int(r["competitor_count"].sum())
    kk_share = kk / total
    national_rate = total / r["population"].sum() * 100000
    kk_districts = int((r["kkmart_count"] > 0).sum())
    pop_covered = r.loc[r["kkmart_count"] > 0, "population"].sum() / r["population"].sum()

    doc = Document()
    for section in doc.sections:
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Title
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = t.add_run("KKmart Malaysia: Whitespace & Market Saturation Analysis")
    run.font.size = Pt(20)
    run.font.bold = True
    run.font.color.rgb = NAVY
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    srun = sub.add_run(f"District-level expansion opportunity assessment  |  {date.today().strftime('%d %B %Y')}")
    srun.font.size = Pt(11)
    srun.italic = True

    # 1. Executive summary
    add_heading(doc, "1. Executive Summary", 1)
    doc.add_paragraph(
        f"This analysis maps all {kk:,} KKmart stores against {comp:,} competitor outlets "
        f"(7-Eleven, 99 Speedmart, FamilyMart, myNEWS) and official demographic data from the "
        f"Department of Statistics Malaysia (DOSM) across all 160 administrative districts. "
        f"KKmart holds a {kk_share:.0%} share of the combined convenience-store network and is "
        f"present in only {kk_districts} of 160 districts, covering {pop_covered:.0%} of the national "
        f"population. The national benchmark is {national_rate:.1f} convenience stores per 100,000 "
        f"people. Twenty districts are saturated (>1.2x the national rate) — including KKmart's core "
        f"markets of Kuala Lumpur, Petaling and Johor Bahru — while 76 districts remain structurally "
        f"underserved (<0.5x). The clearest expansion opportunities fall into two groups: open "
        f"whitespace in East Malaysia (Tawau, Semporna, Lahad Datu) and competitor-validated markets "
        f"where KKmart is absent (Kota Kinabalu, Alor Setar, Kuala Terengganu)."
    )

    # 2. Methodology
    add_heading(doc, "2. Methodology", 1)

    add_heading(doc, "2.1 Data sources", 2)
    src_df = pd.DataFrame({
        "Dataset": [
            "KKmart store list (1,054 stores)",
            "Competitor stores (6,613 outlets)",
            "Population by district, 2024",
            "Households, Census 2020",
            "Income, expenditure, poverty, Gini (HIES 2022)",
            "District boundaries (GeoJSON, 160 districts)",
        ],
        "Source": [
            "Company data (July)",
            "Compiled lists: 7-Eleven (2,600), 99 Speedmart (3,014), FamilyMart (479), myNEWS (520)",
            "DOSM OpenDOSM: population_district",
            "DOSM data-open GitHub: census_district",
            "DOSM OpenDOSM: hies_district",
            "DOSM data-open GitHub: administrative_2_district",
        ],
    })
    add_table(doc, src_df)
    doc.add_paragraph()

    add_heading(doc, "2.2 Approach", 2)
    for step in [
        "Data cleaning: coordinates validated against Malaysia's bounding box (2 competitor records "
        "with invalid coordinates removed), duplicates flagged, all 7,667 stores geocoded.",
        "Spatial join: every store assigned to its administrative district by point-in-polygon matching "
        "against official DOSM boundaries (coastal stores snapped to nearest district).",
        "Demand index per district: weighted blend of normalized indicators — population 2024 (30%), "
        "households (20%), population density (20%), mean household expenditure (15%), share of "
        "population aged 15-39 (10%), and population growth 2020-2024 (5%).",
        "Saturation ratio: district convenience stores per 100k population divided by the national rate "
        f"({national_rate:.1f}/100k). Above 1.2x = saturated; below 0.5x = underserved.",
        "Whitespace score: demand index minus normalized total market supply (all five brands), so a "
        "district only scores highly if demand is strong AND the market is not already crowded.",
        "Classification: each district labelled open_whitespace, room_to_expand, competitor_led, "
        "competitive, saturated, or low_demand based on demand, saturation and KKmart presence.",
    ]:
        doc.add_paragraph(step, style="List Number")

    # 3. Findings
    add_heading(doc, "3. Key Findings", 1)

    add_heading(doc, "3.1 Market structure", 2)
    brand_df = pd.DataFrame({
        "Brand": ["99 Speedmart", "7-Eleven", "KKmart", "myNEWS", "FamilyMart", "Total"],
        "Stores": ["3,014", "2,600", "1,054", "520", "479", "7,667"],
        "Network share": ["39%", "34%", "14%", "7%", "6%", "100%"],
    })
    add_table(doc, brand_df)
    doc.add_paragraph()
    doc.add_paragraph(
        "KKmart's footprint is heavily concentrated: Selangor (466), Kuala Lumpur (245) and Johor (132) "
        "account for 80% of all stores. KKmart has zero presence in Sabah, Kelantan, Terengganu, Perlis "
        "and Labuan."
    )

    add_heading(doc, "3.2 Saturation", 2)
    doc.add_paragraph(
        "Of 160 districts: 20 saturated, 64 balanced, 76 underserved. The most saturated markets are "
        "Cameron Highlands (2.7x national rate, tourism-inflated), Sepang (2.2x), Kuala Lumpur (2.0x), "
        "Port Dickson (1.8x) and Petaling (1.7x). KKmart's core Klang Valley base is therefore a "
        "share-defence market, not a growth market: incremental stores there compete for existing "
        "traffic rather than serving unmet demand."
    )
    sat = r[r["saturation_level"] == "saturated"].nlargest(8, "saturation_ratio")
    sat_df = pd.DataFrame({
        "District": sat["district"] + ", " + sat["state"],
        "Population": sat["population"].map(fmt_pop),
        "KKmart": sat["kkmart_count"].astype(int),
        "Competitors": sat["competitor_count"].astype(int),
        "Stores/100k": sat["stores_per_100k"].round(1),
        "vs national": (sat["saturation_ratio"]).map(lambda x: f"{x:.1f}x"),
    })
    add_table(doc, sat_df)
    doc.add_paragraph()

    add_heading(doc, "3.3 Open whitespace (high demand, few stores from any brand)", 2)
    ow = r[r["category"] == "open_whitespace"].nlargest(8, "whitespace_score")
    ow_df = pd.DataFrame({
        "District": ow["district"] + ", " + ow["state"],
        "Population": ow["population"].map(fmt_pop),
        "Median income (RM)": ow["income_median"].astype(int).map("{:,}".format),
        "Total stores": ow["total_stores"].astype(int),
        "Stores/100k": ow["stores_per_100k"].round(1),
    })
    add_table(doc, ow_df)
    doc.add_paragraph()
    doc.add_paragraph(
        "East Malaysia dominates: Tawau (414k people, 8 stores in total across all brands), Semporna, "
        "Lahad Datu and Kinabatangan in Sabah; Bintulu and Sibu in Sarawak. Bintulu is notable for its "
        "high median income (RM 8,567 — above Klang) with no KKmart presence. The main execution risk "
        "in this group is East Malaysian logistics and supply-chain cost."
    )

    add_heading(doc, "3.4 Competitor-led markets (demand proven, KKmart absent)", 2)
    cl = r[r["category"] == "competitor_led"].nlargest(8, "demand_index")
    cl_df = pd.DataFrame({
        "District": cl["district"] + ", " + cl["state"],
        "Population": cl["population"].map(fmt_pop),
        "Competitors": cl["competitor_count"].astype(int),
        "Stores/100k": cl["stores_per_100k"].round(1),
        "vs national": cl["saturation_ratio"].map(lambda x: f"{x:.1f}x"),
    })
    add_table(doc, cl_df)
    doc.add_paragraph()
    doc.add_paragraph(
        "These are arguably the lowest-risk expansion targets: competitors have already validated "
        "consumer demand, yet total density remains below the national rate, and KKmart is the missing "
        "brand. Kota Kinabalu stands out — 547k people, 96 competitor outlets, zero KKmart stores."
    )

    # 4. Investment analyst relevance
    add_heading(doc, "4. Relevance for Investment Analysis", 1)
    for title, body in [
        ("Growth runway quantification",
         "Store-count growth is the primary earnings driver for convenience retail. This analysis converts "
         "a vague 'expansion story' into a measurable pipeline: 19 open-whitespace and 18 competitor-led "
         "districts define the addressable runway, while 20 saturated districts cap realistic same-format "
         "growth in the core. That supports store-rollout assumptions in a DCF or comparable-company model."),
        ("Unit-economics risk flags",
         "New stores in saturated districts (KL, Petaling, JB) face cannibalisation and rent pressure; the "
         "same capex deployed in underserved, competitor-validated districts should generate higher "
         "incremental revenue per store. Monitoring where a retailer actually opens stores versus this map "
         "is a leading indicator of future same-store-sales dilution."),
        ("Competitive positioning",
         "KKmart's 14% network share versus 99 Speedmart's 39% and 7-Eleven's 34%, and its absence from "
         "five states, quantify both the market-share gap and the differentiation of its footprint. The "
         "brand-level district counts allow head-to-head overlap analysis for any pair of chains."),
        ("Scalable, auditable framework",
         "All demand inputs are official DOSM open data with published vintages; the pipeline is fully "
         "reproducible in Python and re-runs in minutes when new store lists or census updates arrive. The "
         "same framework transfers directly to other retail, F&B, pharmacy or bank-branch networks — any "
         "business where physical distribution drives revenue."),
    ]:
        p = doc.add_paragraph()
        run = p.add_run(title + ". ")
        run.bold = True
        p.add_run(body)

    # 5. Caveats
    add_heading(doc, "5. Caveats", 1)
    for c in [
        "Data vintages differ: households are Census 2020, income/expenditure HIES 2022, population 2024. "
        "Rankings are robust to this, but absolute per-household figures mix reference years.",
        "Districts are coarse units; a large district can hide urban pockets that are locally saturated. "
        "A finer DUN-level or catchment-radius pass is the recommended next step for site selection.",
        "All five brands are weighted equally in the saturation measure, although 99 Speedmart's mini-market "
        "format overlaps only partially with convenience-store demand.",
        "Competitor lists are point-in-time snapshots; openings and closures since compilation are not reflected.",
    ]:
        doc.add_paragraph(c, style="List Bullet")

    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run(
        "Deliverables: interactive map (docs/index.html, deployable via GitHub Pages), full district "
        "ranking (output/whitespace_ranking.csv), reproducible pipeline (python -m src.pipeline)."
    )
    run.italic = True
    run.font.size = Pt(9)

    out = ROOT / "output" / "KKmart_Whitespace_Report.docx"
    doc.save(str(out))
    print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
