"""Run the full whitespace pipeline end to end.

Usage: python -m src.pipeline
Steps that need the store file are skipped gracefully until it exists.
"""
import sys
from pathlib import Path

from src import build_district_table, download_data, make_map, score
from src.clean_stores import load_config

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("== 1/4 Download DOSM data ==")
    sys.argv = ["download_data"]
    download_data.main()

    print("\n== 2/4 Build district demand table ==")
    build_district_table.main()

    cfg = load_config()
    stores_csv = ROOT / cfg["paths"]["stores_csv"]
    if stores_csv.exists():
        print("\n== 2b Clean + spatially join stores ==")
        from src import clean_stores
        clean_stores.main()
    else:
        print(f"\n== 2b SKIPPED: store file not found at {stores_csv} ==")

    print("\n== 3/4 Score districts ==")
    score.main()

    print("\n== 4/4 Build map ==")
    make_map.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
