#!/usr/bin/env python3
"""
Source-aware, near-duplicate-safe stratified split.

Near-duplicate pairs (from hashing.py's report) are unioned into connected
components; each component is assigned to exactly one split as a whole unit,
so no near-duplicate can ever cross a train/val/test boundary. Split
assignment is stratified per canonical class at ~80/10/10.

Both PlantVillage (lab) and PlantDoc (real-world field) images can land in
any split, but test-set metrics are reported BOTH overall AND broken down by
source_dataset, which is how source-generalization is measured here given
PlantDoc's small per-class counts don't support holding it out entirely
without destroying the training signal for field-style imagery.
"""
import json
import os
import random
from pathlib import Path
from collections import defaultdict

PROJECT_ML = Path(__file__).resolve().parents[1]  # = <project>/ml (portable)
RECORDS_PATH = PROJECT_ML / "data" / "deduplicated_records.json"
LEAKAGE_REPORT_PATH = PROJECT_ML / "reports" / "v2_leakage_report.json"
OUT_PATH = PROJECT_ML / "data" / "split_records.json"

RANDOM_SEED = 42
TRAIN_FRAC, VAL_FRAC, TEST_FRAC = 0.80, 0.10, 0.10


class UnionFind:
    def __init__(self, ids):
        self.parent = {i: i for i in ids}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def main():
    records = json.load(open(RECORDS_PATH))
    leakage = json.load(open(LEAKAGE_REPORT_PATH))
    ids = [r["image_id"] for r in records]
    uf = UnionFind(ids)
    id_set = set(ids)
    unioned = 0
    for pair in leakage["near_duplicate_pair_log"]:
        a, b = pair["image_id_a"], pair["image_id_b"]
        if a in id_set and b in id_set:
            uf.union(a, b)
            unioned += 1
    print(f"Unioned {unioned} near-duplicate pairs into connected components")

    components = defaultdict(list)
    for r in records:
        components[uf.find(r["image_id"])].append(r)
    print(f"{len(components)} connected components from {len(records)} images")

    # Stratify components by their (majority) canonical label
    comps_by_label = defaultdict(list)
    for comp_id, recs in components.items():
        label = recs[0]["canonical_label"]  # near-dups are within-class by construction
        comps_by_label[label].append(recs)

    rng = random.Random(RANDOM_SEED)
    split_assignment = {}
    split_counts = defaultdict(lambda: defaultdict(int))

    for label, comp_list in comps_by_label.items():
        comp_list = sorted(comp_list, key=lambda recs: recs[0]["image_id"])  # deterministic order
        rng.shuffle(comp_list)
        n_images = sum(len(recs) for recs in comp_list)
        n_train_target = round(n_images * TRAIN_FRAC)
        n_val_target = round(n_images * VAL_FRAC)

        running = 0
        for recs in comp_list:
            if running < n_train_target:
                split = "train"
            elif running < n_train_target + n_val_target:
                split = "val"
            else:
                split = "test"
            for r in recs:
                split_assignment[r["image_id"]] = split
            running += len(recs)
            split_counts[label][split] += len(recs)

    for r in records:
        r["split"] = split_assignment[r["image_id"]]
        r["split_random_seed"] = RANDOM_SEED

    # --- Cross-split near-duplicate verification gate ---
    violations = []
    for pair in leakage["near_duplicate_pair_log"]:
        a, b = pair["image_id_a"], pair["image_id_b"]
        if a in split_assignment and b in split_assignment:
            if split_assignment[a] != split_assignment[b]:
                violations.append(pair)
    if violations:
        raise RuntimeError(f"LEAKAGE GATE FAILED: {len(violations)} near-duplicate pairs span different splits: {violations}")
    print("Cross-split near-duplicate verification: PASSED (0 violations)")

    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2)

    print("\nPer-class split counts:")
    for label, counts in sorted(split_counts.items()):
        print(f"  {label}: train={counts['train']} val={counts['val']} test={counts['test']}")

    # Source breakdown of the test split specifically
    test_by_source = defaultdict(int)
    for r in records:
        if r["split"] == "test":
            test_by_source[r["source_dataset"]] += 1
    print("\nTest-split source breakdown:", dict(test_by_source))

    # Persist the verification result into the leakage report
    leakage["split_random_seed"] = RANDOM_SEED
    leakage["split_fractions"] = {"train": TRAIN_FRAC, "val": VAL_FRAC, "test": TEST_FRAC}
    leakage["connected_components"] = len(components)
    leakage["cross_split_near_duplicate_violations"] = len(violations)
    leakage["cross_split_verification_status"] = "PASSED" if not violations else "FAILED"
    leakage["per_class_split_counts"] = {k: dict(v) for k, v in split_counts.items()}
    leakage["test_split_source_breakdown"] = dict(test_by_source)
    with open(LEAKAGE_REPORT_PATH, "w") as f:
        json.dump(leakage, f, indent=2)
    print(f"\nUpdated {LEAKAGE_REPORT_PATH} with split verification results")


if __name__ == "__main__":
    main()
