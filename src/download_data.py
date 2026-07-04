"""Download all DOSM open datasets needed for the whitespace analysis.

Idempotent: skips files that already exist unless --force is passed.
Usage: python -m src.download_data [--force]
"""
import argparse
import sys
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def download(url: str, dest: Path, force: bool = False) -> None:
    if dest.exists() and not force:
        print(f"  skip (exists): {dest.name}")
        return
    print(f"  downloading: {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"  saved: {dest} ({len(resp.content) / 1e6:.1f} MB)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="re-download even if file exists")
    args = parser.parse_args()

    cfg = load_config()
    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    raw_dir.mkdir(parents=True, exist_ok=True)

    for key, url in cfg["data_urls"].items():
        ext = Path(url).suffix  # .parquet / .csv / .geojson
        download(url, raw_dir / f"{key}{ext}", force=args.force)

    return 0


if __name__ == "__main__":
    sys.exit(main())
