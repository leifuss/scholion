#!/usr/bin/env python3
"""
Sync inventory.json with what's actually on disk.

For each doc in inventory, checks data/texts/{key}/ and updates:
  extracted     — True if page_texts.json exists
  has_reader    — True if pages/001.jpg exists (rendered pages available)
  text_quality  — from meta.json if available
  page_count    — from meta.json if available (overrides inventory value)

Safe to run repeatedly — only updates fields where disk state differs.
Fast: just file-existence checks, no network, no ML.

Usage:
    python scripts/00_update_inventory_flags.py
    python scripts/00_update_inventory_flags.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
TEXTS_ROOT = _ROOT / "data" / "texts"
INV_PATH   = _ROOT / "data" / "inventory.json"


def check_doc(key: str) -> dict:
    """Return dict of flags to update in inventory for this key."""
    doc_dir    = TEXTS_ROOT / key
    pt_path    = doc_dir / "page_texts.json"
    meta_path  = doc_dir / "meta.json"
    page1_path = doc_dir / "pages" / "001.jpg"

    flags: dict = {}

    extracted  = pt_path.exists()
    has_reader = page1_path.exists()
    flags["extracted"]  = extracted
    flags["has_reader"] = has_reader

    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text("utf-8"))
            if meta.get("text_quality"):
                flags["text_quality"] = meta["text_quality"]
            if meta.get("chars_per_page") is not None:
                flags["chars_per_page"] = meta["chars_per_page"]
            if meta.get("page_count"):
                flags["page_count"] = meta["page_count"]
        except Exception:
            pass

    return flags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--inventory", default="data/inventory.json")
    args = parser.parse_args()

    inv_path  = _ROOT / args.inventory
    inventory = json.loads(inv_path.read_text("utf-8"))

    changed   = 0
    for item in inventory:
        key   = item["key"]
        flags = check_doc(key)
        for k, v in flags.items():
            if item.get(k) != v:
                item[k] = v
                changed += 1

    if args.dry_run:
        extracted  = sum(1 for x in inventory if x.get("extracted"))
        has_reader = sum(1 for x in inventory if x.get("has_reader"))
        print(f"Would update {changed} fields across {len(inventory)} items")
        print(f"  extracted:  {extracted}")
        print(f"  has_reader: {has_reader}")
        return

    if changed:
        tmp = inv_path.with_suffix(".tmp.json")
        tmp.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(inv_path)
        print(f"Updated {changed} fields in {inv_path.name}")
    else:
        print("No changes needed — inventory already up to date")

    extracted  = sum(1 for x in inventory if x.get("extracted"))
    has_reader = sum(1 for x in inventory if x.get("has_reader"))
    print(f"  extracted:  {extracted} / {len(inventory)}")
    print(f"  has_reader: {has_reader} / {len(inventory)}")


if __name__ == "__main__":
    main()
