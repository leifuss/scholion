#!/usr/bin/env python3
"""
Patch _page_sizes into Vision-processed layout_elements.json files.

Vision OCR stores bboxes in pixel coordinates (image pixel space).  The old
Docling _page_sizes (PDF points) must be REPLACED with pixel dimensions so
reader.html bbox overlays normalise correctly.

Strategy:
  - Docs with a layout_elements.docling.json backup were Vision-processed;
    their bboxes are now in pixel space, so we always overwrite _page_sizes.
  - Docs WITHOUT a backup still have Docling bboxes/sizes — skip them.
"""

import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow not installed. Run: pip install Pillow")


TEXTS_ROOT = Path(__file__).parent.parent / "data" / "texts"


def get_image_size(img_path: Path) -> tuple[int, int]:
    with Image.open(img_path) as img:
        return img.size  # (width, height)


def page_num_from_path(p: Path) -> int:
    stem = p.stem.lstrip("0") or "0"
    return int(stem)


def patch_doc(doc_dir: Path, force: bool = False, dry_run: bool = False) -> dict:
    le_path    = doc_dir / "layout_elements.json"
    pages_dir  = doc_dir / "pages"
    backup     = doc_dir / "layout_elements.docling.json"

    if not le_path.exists():
        return {"key": doc_dir.name, "status": "no_layout_elements"}
    if not pages_dir.is_dir():
        return {"key": doc_dir.name, "status": "no_pages_dir"}

    # Only patch Vision-processed docs (those with a .docling.json backup),
    # unless --force was given.
    vision_processed = backup.exists()
    if not vision_processed and not force:
        return {"key": doc_dir.name, "status": "docling_only_skipped"}

    with open(le_path) as f:
        layout_elements = json.load(f)

    # Collect pixel dimensions from page images
    page_images = sorted(pages_dir.glob("*.jpg")) + sorted(pages_dir.glob("*.png"))
    page_sizes = {}
    for img_path in sorted(page_images):
        pnum = page_num_from_path(img_path)
        w, h = get_image_size(img_path)
        page_sizes[str(pnum)] = {"w": w, "h": h}

    if not page_sizes:
        return {"key": doc_dir.name, "status": "no_images"}

    old_ps = layout_elements.get("_page_sizes")
    layout_elements["_page_sizes"] = page_sizes

    if not dry_run:
        with open(le_path, "w", encoding="utf-8") as f:
            json.dump(layout_elements, f, ensure_ascii=False, indent=2)

    sample_pg, sample_sz = next(iter(page_sizes.items()))
    old_sample = old_ps.get(sample_pg) if old_ps else None
    return {
        "key": doc_dir.name,
        "status": "patched" if not dry_run else "dry_run",
        "pages": len(page_sizes),
        "sample": (sample_pg, sample_sz),
        "old_sample": old_sample,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Patch _page_sizes into Vision-processed layout_elements.json")
    parser.add_argument("keys", nargs="*", help="Specific doc keys (default: all Vision-processed)")
    parser.add_argument("--force",   action="store_true",
                        help="Also patch docs without a .docling.json backup")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.keys:
        doc_dirs = [TEXTS_ROOT / k for k in args.keys]
    else:
        doc_dirs = sorted(
            d for d in TEXTS_ROOT.iterdir()
            if d.is_dir() and (d / "layout_elements.json").exists()
        )

    for doc_dir in doc_dirs:
        result = patch_doc(doc_dir, force=args.force, dry_run=args.dry_run)
        status = result["status"]
        key    = result["key"]

        if status in ("patched", "dry_run"):
            sample_pg, sample_sz = result["sample"]
            old = result.get("old_sample")
            prefix = "[dry] " if status == "dry_run" else "✓ "
            old_info = f" (was {old['w']}×{old['h']} pts)" if old else " (none before)"
            print(f"{prefix}{key}: {result['pages']} pages, "
                  f"p{sample_pg}={sample_sz['w']}×{sample_sz['h']} px{old_info}")
        elif status == "docling_only_skipped":
            print(f"  {key}: Docling-only, skipped")
        else:
            print(f"  {key}: {status}")


if __name__ == "__main__":
    main()
