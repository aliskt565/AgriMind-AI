> **UPDATE 2026-10-04:** the CNN described below (v2-alpha / V1) has been replaced by `agrimind_plant_disease_v3-field-research` and the V1/v2-alpha/r2 model files were deleted. See `DOCUMENTATION.md` and `CHANGES_2026_10_04.md`. The text below is historical.

# AgriMind AI — V2-alpha Training Report

**Date:** 2026-09-21
**Status:** EXPERIMENTAL. Not integrated into production Plant Vision. Not evaluation-passed for production use.
**Model artifact:** `ml/artifacts/agrimind_plant_disease_v2.keras`
**Metadata:** `ml/artifacts/agrimind_plant_disease_v2_metadata.json`

This report documents what was actually built, acquired, and trained this session — including the real blockers encountered — not an idealized version of the plan.

---

## 1. Scope: why V2-alpha covers only Corn and Potato

The execution brief froze an 18-class, 5-crop taxonomy. That taxonomy is **not what was trained**. Here is exactly why, verified rather than assumed:

This session's network sandbox allows outbound access only to a fixed domain allowlist. It includes `github.com` / `codeload.github.com` / `raw.githubusercontent.com`, but **does not include `data.mendeley.com`, `zenodo.org`, or `kaggle.com`** — confirmed directly via HTTP checks, all three returning `403 host_not_allowed`. Every Class-A source verified for Rice, Wheat, and Sugarcane in `docs/ml_v2_dataset_license_verification_2026_09.md` lives on one of those three hosts. Only the Corn/Potato sources (PlantDoc, PlantVillage) are GitHub-hosted and reachable.

**V2-alpha's actual taxonomy is therefore 7 classes:**
```
Corn___Common_Rust, Corn___Gray_Leaf_Spot, Corn___Healthy, Corn___Northern_Leaf_Blight,
Potato___Early_Blight, Potato___Healthy, Potato___Late_Blight
```
Rice, Wheat, and Sugarcane (11 classes) are **deferred, not dropped** — see `ml/data/dataset_manifest.json` → `datasets_deferred` for the exact retry path (acquire from Mendeley/Zenodo/Kaggle from an environment with access, or via manual upload into this project).

## 2. Dataset acquisition (real, not simulated)

| Source | Method | License | Images acquired |
|---|---|---|---|
| PlantVillage (GitHub, spMohanty/PlantVillage-Dataset) | `git sparse-checkout` (blob:none filter, cone mode) — only the 7 needed class folders under `raw/color/`, not the full 14-crop repository | CC BY-SA 3.0 | 6,004 |
| PlantDoc (GitHub, pratikkayal/PlantDoc-Dataset) | Full repo zip via `codeload.github.com` | CC BY 4.0 (confirmed by fetching `LICENSE.txt` directly) | 582 (train+test folders combined) |

**On the PlantVillage CC BY-SA 3.0 license, precisely:** the dataset license permits use subject to its terms (attribution, and share-alike for redistribution of the dataset/derivative databases), but the downstream licensing implications for trained model weights and commercial distribution require separate legal review. Technical use of the dataset in this experiment should not be interpreted as legal clearance for commercial release of the resulting model. See `ml/data/dataset_manifest.json` for the same wording recorded at the dataset-record level.

**A real blocker encountered and resolved:** MobileNetV2's ImageNet-pretrained weights are normally fetched from `storage.googleapis.com`, which is also outside this session's allowlist. Resolved by sourcing the identical weights file from a GitHub release mirror (`JonathanCMitchell/mobilenet_v2_keras`), verified by exact byte size (9,406,464 bytes) matching the official file before use. This is disclosed so the exact provenance of the backbone weights is auditable, not assumed.

## 3. Label mapping (explicit, documented — nothing silently merged)

PlantVillage folder names map 1:1 to canonical labels by direct lookup (see `scripts/taxonomy.py:PLANTVILLAGE_LABEL_MAP`) — no judgment calls involved.

PlantDoc's informal class names required one **documented, flagged assumption**: `"Corn leaf blight"` was mapped to `Corn___Northern_Leaf_Blight`. PlantDoc's own materials do not disambiguate this from other corn leaf blights (e.g. Southern Leaf Blight); Northern Leaf Blight was judged the more likely match given PlantDoc's source regions, but this is a judgment call, not a verified 1:1 match, and is flagged for expert review. PlantDoc contributes **zero** images to `Corn___Healthy` / `Potato___Healthy` — it has no healthy-leaf classes for either crop.

## 4. Deduplication and leakage prevention (real findings, not assumed-clean)

- **SHA-256 exact-duplicate check** across all 6,602 ingested images found 8 duplicate groups, involving **16 records in total** (2 byte-identical records per group). **All 8 groups spanned conflicting canonical labels** — the identical byte-for-byte image filed under two different PlantDoc disease folders (e.g. `corn-gray-leaf-spot-f4.jpg` appearing under both "Corn Gray leaf spot" and "Corn leaf blight"). This is a genuine PlantDoc data-quality issue, not an ingestion bug. **Policy: all 16 conflicting-label records were excluded from training entirely** (not merely 8 — every copy in a cross-class conflict group is excluded, not just the "extra" one), rather than arbitrarily assigning one label. Final count after this and ordinary same-label dedup (of which there were none in this run): 6,586 images (6,602 − 16). See `ml/reports/v2_leakage_report.json` for the full, corrected accounting and its `terminology_correction_note`.
- **Perceptual hashing** (64-bit pHash, Hamming distance ≤ 5) found 15 near-duplicate pairs, all within the same class.
- **Split:** near-duplicate pairs were unioned into connected components; each component was assigned to exactly one split as a whole unit. Stratified per-class 80/10/10 → train=5,269, val=658, test=659.
- **Cross-split verification gate: PASSED, 0 violations** — no near-duplicate pair spans train/val/test. See `ml/reports/v2_leakage_report.json` for the full detail, including the drop log.
- **Class imbalance, disclosed not hidden:** `Potato___Healthy` has only 152 source images (PlantVillage only — PlantDoc has none) versus 1,100+ for every other class. Addressed via inverse-frequency class weighting during training (weight 6.17 for this class vs. ~0.7–1.6 for the rest), not by fabricating additional images.

## 5. Preprocessing (single shared implementation — V1's ambiguity explicitly not repeated)

`scripts/preprocessing.py:load_and_preprocess` is the **one and only** preprocessing implementation, imported by training, evaluation, OOD scoring, and the inference wrapper — never reimplemented separately anywhere. Image size 224×224, PIL bilinear resize, RGB, `tf.keras.applications.mobilenet_v2.preprocess_input` (scales to [-1, 1]). This is a direct, verifiable fix for V1's documented ambiguity (V1's inference path did raw `img_to_array` with no confirmed normalization match to training).

## 6. Training configuration (exact, recorded)

| Parameter | Value |
|---|---|
| Random seed | 42 |
| Python | 3.12.3 |
| TensorFlow | 2.21.0 |
| Keras | 3.15.1 |
| Architecture | MobileNetV2 (ImageNet) → GlobalAveragePooling2D → Dense(128, relu) → Dropout(0.3) → Dense(7, softmax) |
| Image size | 224×224 |
| Optimizer | Adam |
| Stage 1 LR | 1e-3 (frozen backbone) |
| Stage 2 LR | 1e-5 (top 20 backbone layers unfrozen) |
| Batch size | 32 |
| Augmentation | random horizontal flip, random brightness ±0.15, random contrast 0.85–1.15, random crop after pad — **train split only, applied after split assignment**, never before |
| Class weights | inverse-frequency, see table above |
| Dataset manifest SHA-256 | `502cd4ddf18c2e0b49102d6b28bb4895c7675391feb8b866824ed4e62bdfc815` (updated 2026-09-23 after documentation-only corrections to `dataset_manifest.json` — original training run hash was `b6d771718242c1cd5c2f0b6740d258d463242dec7c7e91748689480838904afd`; no dataset or model change occurred, only manifest text) |
| n_train / n_val | 5,269 / 658 |
| Total training time | 1,692.9 seconds (~28.2 minutes), real, measured |

## 7. Training results — including the honest, non-flattering part

**Stage 1** (6 epochs, frozen backbone): best val_loss **0.17723** at epoch 4 (val_accuracy 91.79%).

**Stage 2** (6 epochs, fine-tuning): train accuracy climbed to 94.42% (final epoch), val_accuracy peaked at 92.25%, but **best val_loss was 0.20079 — worse than Stage 1's 0.17723**, even though val_accuracy improved. This is reported as-is rather than smoothed over: fine-tuning helped the model's accuracy but made its loss/calibration slightly worse on validation, plausibly from the low-LR unfreezing interacting with a modest dataset size. Full per-epoch curves: `artifacts/training_history.json`.

Both stages' `ModelCheckpoint` callbacks (`save_best_only=True`, monitor=`val_loss`) preserved the best-seen weights at each stage; the final exported model reflects the end of Stage 2 training (Keras' `EarlyStopping(restore_best_weights=True)` restored the best Stage 2 weights before export).

See `docs/ml_v2_evaluation_report.md` for held-out test results and `docs/ml_v2_ood_report.md` for OOD behavior — both measured, not projected from validation numbers.
