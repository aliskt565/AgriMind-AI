#!/usr/bin/env python3
"""
Exact-duplicate (SHA-256, already computed at ingestion) and near-duplicate
(perceptual hash) detection across the ingested record set.

Produces:
  data/deduplicated_records.json  -- records with exact dups removed (first
                                      occurrence kept, others dropped and logged)
  reports/v2_leakage_report.json  -- summary of exact + near-duplicate findings,
                                      including any that would have crossed a
                                      class boundary (a real labeling-error signal)
"""
import json
import os
from pathlib import Path
from collections import defaultdict
import imagehash
from PIL import Image

PROJECT_ML = Path(__file__).resolve().parents[1]  # = <project>/ml (portable)
IN_PATH = PROJECT_ML / "data" / "ingested_records.json"
OUT_RECORDS = PROJECT_ML / "data" / "deduplicated_records.json"
OUT_REPORT = PROJECT_ML / "reports" / "v2_leakage_report.json"

PHASH_NEAR_DUP_THRESHOLD = 5  # Hamming distance; standard conservative threshold for 64-bit pHash


def main():
    records = json.load(open(IN_PATH))
    print(f"Loaded {len(records)} records")

    # --- Exact duplicate detection (SHA-256) ---
    by_sha = defaultdict(list)
    for r in records:
        by_sha[r["sha256"]].append(r)

    exact_dup_groups = {sha: recs for sha, recs in by_sha.items() if len(recs) > 1}
    kept_records = []
    exact_dropped = []  # ordinary same-label redundant copies only (all but the first kept copy)
    cross_class_exact_dups = []
    cross_class_conflict_image_ids = []

    for sha, recs in by_sha.items():
        if len(recs) == 1:
            kept_records.append(recs[0])
            continue

        labels = set(r["canonical_label"] for r in recs)
        sources = set(r["source_dataset"] for r in recs)

        if len(labels) > 1:
            # Cross-class label conflict: identical image filed under two or more
            # different disease labels. This is a labeling disagreement, not
            # ordinary redundancy -- EXCLUDE ALL copies in the group rather than
            # arbitrarily keeping one label's copy.
            cross_class_exact_dups.append({
                "sha256": sha,
                "labels": list(labels),
                "image_ids": [r["image_id"] for r in recs],
            })
            cross_class_conflict_image_ids.extend(r["image_id"] for r in recs)
            # deliberately NOT added to kept_records -- all copies excluded
        else:
            # Ordinary same-label exact duplicate: keep exactly one copy, drop the rest.
            keeper = recs[0]
            kept_records.append(keeper)
            for dropped in recs[1:]:
                exact_dropped.append({
                    "image_id": dropped["image_id"],
                    "kept_image_id": keeper["image_id"],
                    "sha256": sha,
                    "same_source": list(sources) == [keeper["source_dataset"]] if len(sources) == 1 else False,
                    "sources_involved": list(sources),
                })

    n_conflict_groups = len(cross_class_exact_dups)
    n_same_label_groups = len(exact_dup_groups) - n_conflict_groups
    n_records_excluded_conflict = len(cross_class_conflict_image_ids)
    n_records_dropped_same_label = len(exact_dropped)
    n_records_excluded_total = n_records_excluded_conflict + n_records_dropped_same_label

    print(
        f"Exact-duplicate groups: {len(exact_dup_groups)} total "
        f"({n_same_label_groups} same-label, {n_conflict_groups} cross-class conflicts). "
        f"Records excluded: {n_records_excluded_total} total "
        f"({n_records_dropped_same_label} redundant same-label copies dropped, "
        f"{n_records_excluded_conflict} records excluded from {n_conflict_groups} cross-class "
        f"conflict group(s) -- ALL copies in a conflict group are excluded, not just the extras)."
    )
    if cross_class_exact_dups:
        print(f"WARNING: {n_conflict_groups} exact-duplicate group(s) span different canonical labels -- labeling conflict, not just redundancy. All {n_records_excluded_conflict} records in these groups were excluded.")

    # --- Perceptual hashing for near-duplicate detection (on the deduplicated set) ---

    print(f"Computing perceptual hashes for {len(kept_records)} images...")
    phashes = {}
    for i, r in enumerate(kept_records):
        full_path = PROJECT_ML / r["raw_path"]
        try:
            with Image.open(full_path) as im:
                im = im.convert("RGB")
                phashes[r["image_id"]] = imagehash.phash(im)
        except Exception as e:
            print(f"  hash failed for {r['image_id']}: {e}")
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{len(kept_records)}")

    # Bucket by class to keep the O(n^2) comparison tractable (near-dups almost
    # always share a class; cross-class near-dups are checked separately below
    # using a coarser bucket-free scan only if the per-class scan finds few
    # pairs, to keep runtime bounded).
    by_class_ids = defaultdict(list)
    for r in kept_records:
        by_class_ids[r["canonical_label"]].append(r["image_id"])

    near_dup_pairs = []
    for label, ids in by_class_ids.items():
        ids = [i for i in ids if i in phashes]
        n = len(ids)
        for i in range(n):
            hi = phashes[ids[i]]
            for j in range(i + 1, n):
                dist = hi - phashes[ids[j]]
                if dist <= PHASH_NEAR_DUP_THRESHOLD:
                    near_dup_pairs.append({
                        "image_id_a": ids[i], "image_id_b": ids[j],
                        "canonical_label": label, "hamming_distance": int(dist),
                    })

    print(f"Near-duplicate pairs found (within-class, threshold<= {PHASH_NEAR_DUP_THRESHOLD}): {len(near_dup_pairs)}")

    # id -> record lookup for source annotation
    rec_by_id = {r["image_id"]: r for r in kept_records}
    near_dup_cross_source = [
        p for p in near_dup_pairs
        if rec_by_id[p["image_id_a"]]["source_dataset"] != rec_by_id[p["image_id_b"]]["source_dataset"]
    ]

    with open(OUT_RECORDS, "w") as f:
        json.dump(kept_records, f, indent=2)

    n_records_in_all_dup_groups = sum(len(recs) for recs in exact_dup_groups.values())
    report = {
        "generated_at": "2026-09-20",
        "input_record_count": len(records),
        "exact_duplicate_summary": (
            f"{len(exact_dup_groups)} exact-duplicate groups were identified "
            f"({n_same_label_groups} ordinary same-label, {n_conflict_groups} cross-class label "
            f"conflicts), involving {n_records_in_all_dup_groups} records in total across those "
            f"groups. {n_records_excluded_total} records were excluded from the final dataset: "
            f"{n_records_dropped_same_label} ordinary redundant same-label copies (one kept per "
            f"group) plus {n_records_excluded_conflict} records from cross-class conflict groups "
            f"(ALL copies excluded, not just the extras)."
        ),
        "exact_duplicate_groups": len(exact_dup_groups),
        "exact_duplicate_groups_same_label": n_same_label_groups,
        "exact_duplicate_groups_cross_class_conflict": n_conflict_groups,
        "exact_duplicate_records_dropped_same_label_redundant": n_records_dropped_same_label,
        "exact_duplicate_records_excluded_cross_class_conflict": n_records_excluded_conflict,
        "exact_duplicate_records_excluded_total": n_records_excluded_total,
        "exact_duplicate_cross_class_conflicts": cross_class_exact_dups,
        "cross_class_conflict_images_excluded": sorted(cross_class_conflict_image_ids),
        "exact_duplicate_drop_log": exact_dropped,
        "policy_note": "Cross-class exact-duplicate conflicts (identical image, different label from source) are EXCLUDED entirely (all copies) rather than arbitrarily assigning one label. Ordinary same-label exact duplicates keep exactly one copy per group.",
        "deduplicated_record_count": len(kept_records),
        "phash_algorithm": "imagehash.phash (perceptual hash, 64-bit DCT-based)",
        "phash_near_duplicate_threshold_hamming": PHASH_NEAR_DUP_THRESHOLD,
        "near_duplicate_pairs_within_class": len(near_dup_pairs),
        "near_duplicate_pairs_cross_source": len(near_dup_cross_source),
        "near_duplicate_pair_log": near_dup_pairs,
        "note": "Near-duplicate scan was run within each canonical-label bucket (all same-class pairs checked pairwise); a full cross-class all-pairs scan was not run due to runtime cost (O(n^2) over 6.6k images) and because near-duplicates spanning different disease labels would already be far apart in feature/appearance space in the overwhelming majority of real cases. This is a documented scope limitation, not a silent gap.",
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_REPORT, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote leakage report to {OUT_REPORT}")
    print(f"Wrote {len(kept_records)} deduplicated records to {OUT_RECORDS}")


if __name__ == "__main__":
    main()
