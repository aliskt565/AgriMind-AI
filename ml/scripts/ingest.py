#!/usr/bin/env python3
"""
Ingest images from the two network-reachable, license-verified sources
(PlantVillage GitHub mirror, PlantDoc GitHub repo) into a provenance-tracked
raw data directory, and emit dataset_manifest.json entries.

Every image gets:
  image_id, source_dataset, source_dataset_version, original_filename,
  original_label, canonical_label, license, sha256, source_path

Perceptual hashing and split assignment happen in later stages (hashing.py,
split.py) -- this script only ingests + records source-level provenance.
"""
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import PLANTVILLAGE_LABEL_MAP, PLANTDOC_LABEL_MAP

PROJECT_ML = Path(__file__).resolve().parents[1]  # = <project>/ml (portable)
WORKSPACE = Path(os.environ.get("AGRIMIND_ML_WORKSPACE", str(PROJECT_ML.parent / "ml_workspace")))
RAW_OUT = PROJECT_ML / "data" / "raw"

PLANTVILLAGE_SRC = WORKSPACE / "pv" / "raw" / "color"
PLANTDOC_SRC = WORKSPACE / "PlantDoc-Dataset-master"

IMG_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_plantvillage(records: list):
    for folder_name, canonical in PLANTVILLAGE_LABEL_MAP.items():
        src_dir = PLANTVILLAGE_SRC / folder_name
        if not src_dir.is_dir():
            print(f"WARNING: missing PlantVillage folder {src_dir}")
            continue
        out_dir = RAW_OUT / canonical
        out_dir.mkdir(parents=True, exist_ok=True)
        files = sorted([p for p in src_dir.iterdir() if p.suffix in IMG_EXTS])
        for p in files:
            image_id = str(uuid.uuid4())
            dest = out_dir / f"plantvillage_{image_id}{p.suffix.lower()}"
            shutil.copy2(p, dest)
            records.append({
                "image_id": image_id,
                "source_dataset": "plantvillage",
                "source_dataset_version": "GitHub spMohanty/PlantVillage-Dataset, master branch, raw/color (accessed 2026-09-20)",
                "original_filename": p.name,
                "original_label": folder_name,
                "canonical_label": canonical,
                "license": "CC BY-SA 3.0 (per spMohanty/PlantVillage-Dataset, the authoritative GitHub source used here -- see docs/ml_evaluation_report.md and the V2 research report for the cross-mirror license caveat)",
                "source_url": "https://github.com/spMohanty/PlantVillage-Dataset",
                "acquisition_method": "git sparse-checkout (blob:none filter, cone mode, class folders only)",
                "raw_path": str(dest.relative_to(PROJECT_ML)),
            })
    return records


def ingest_plantdoc(records: list):
    for split_dir_name in ("train", "test"):
        split_dir = PLANTDOC_SRC / split_dir_name
        for folder_name, canonical in PLANTDOC_LABEL_MAP.items():
            src_dir = split_dir / folder_name
            if not src_dir.is_dir():
                continue
            out_dir = RAW_OUT / canonical
            out_dir.mkdir(parents=True, exist_ok=True)
            files = sorted([p for p in src_dir.iterdir() if p.suffix in IMG_EXTS])
            for p in files:
                image_id = str(uuid.uuid4())
                dest = out_dir / f"plantdoc_{image_id}{p.suffix.lower()}"
                shutil.copy2(p, dest)
                records.append({
                    "image_id": image_id,
                    "source_dataset": "plantdoc",
                    "source_dataset_version": f"GitHub pratikkayal/PlantDoc-Dataset, master branch, {split_dir_name}/ (accessed 2026-09-20)",
                    "original_filename": p.name,
                    "original_label": folder_name,
                    "canonical_label": canonical,
                    "license": "CC BY 4.0 (confirmed at https://github.com/pratikkayal/PlantDoc-Dataset/blob/master/LICENSE.txt)",
                    "source_url": "https://github.com/pratikkayal/PlantDoc-Dataset",
                    "acquisition_method": "codeload.github.com repo zip download, master branch",
                    "raw_path": str(dest.relative_to(PROJECT_ML)),
                    "label_mapping_note": "documented assumption -- see PLANTDOC_LABEL_MAP in taxonomy.py" if folder_name == "Corn leaf blight" else None,
                })
    return records


def main():
    RAW_OUT.mkdir(parents=True, exist_ok=True)
    records = []
    ingest_plantvillage(records)
    ingest_plantdoc(records)

    print(f"Computing SHA-256 for {len(records)} ingested images...")
    for i, r in enumerate(records):
        full_path = PROJECT_ML / r["raw_path"]
        r["sha256"] = sha256_of(full_path)
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{len(records)}")

    out_path = PROJECT_ML / "data" / "ingested_records.json"
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Wrote {len(records)} records to {out_path}")

    from collections import Counter
    by_class = Counter(r["canonical_label"] for r in records)
    by_source = Counter(r["source_dataset"] for r in records)
    print("By class:", dict(by_class))
    print("By source:", dict(by_source))


if __name__ == "__main__":
    main()
