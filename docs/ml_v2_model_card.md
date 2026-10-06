> **UPDATE 2026-10-04:** the CNN described below (v2-alpha / V1) has been replaced by `agrimind_plant_disease_v3-field-research` and the V1/v2-alpha/r2 model files were deleted. See `DOCUMENTATION.md` and `CHANGES_2026_10_04.md`. The text below is historical.

# AgriMind AI — Plant Disease Model V2-alpha — Model Card

**Version:** `agrimind_plant_disease_v2-alpha`
**Status: ALPHA — integrated into the local Plant Vision and Quick Scan flows for Corn/Potato.** The model remains experimental in terms of field validation: its documented real-world/OOD limitations mean its outputs are not confirmed diagnoses.
**Created:** 2026-09-21

## What this model is

A MobileNetV2-based transfer-learning classifier covering **7 classes across 2 crops** (Corn, Potato) — see `docs/ml_v2_training_report.md` for exactly why the originally-planned 5-crop, 18-class taxonomy was reduced, and what would need to happen to complete it.

## What this model is NOT

- V2 now replaces the V1 binary at the active model path. The original V1 binary is preserved at `ml/evaluation_archive/v1_legacy/agrimind_plant_disease_model_v1_legacy.keras` for reference/rollback.
- Connected to the production Plant Vision flow (`POST /api/v1/ai/plant-vision/crops/{crop_id}/detect`) and Quick Scan (`POST /api/v1/ai/plant-vision/scan`) through the shared V2 CNN service.
- Not a 5-crop model. Rice, Wheat, and Sugarcane are not covered.
- Not validated as solving V1's real-world generalization gap — see the comparison below.

## V1 vs. V2-alpha — factual comparison

**Read this section carefully before drawing any "V2 is better" conclusion — the honest answer is more nuanced than any single number.**

| | V1 | V2-alpha |
|---|---|---|
| Classes | 18 (5 crops) | 7 (2 crops: Corn, Potato) |
| Training data provenance | **UNKNOWN** — dataset, script, split, seed all unrecoverable | Fully documented: `ml/data/dataset_manifest.json` (current content hash `502cd4ddf18c2e0b49102d6b28bb4895c7675391feb8b866824ed4e62bdfc815`; the manifest's content at the actual moment of training is separately frozen in `ml/artifacts/training_config.json` under hash `b6d771718242c1cd5c2f0b6740d258d463242dec7c7e91748689480838904afd` — the two differ only because of a 2026-09-23 documentation-only correction to the manifest text, not any data or model change), git-commit-traceable sources |
| Held-out status of any reported number | **Never established** for any V1 evaluation, old or new | V2-alpha's internal test (92.11% accuracy) is a genuine, leakage-gated (0 verified cross-split near-duplicate violations) held-out split of V2's *own* training data — this is real progress on reproducibility, independent of the accuracy number itself |
| Comparable evaluation on the same held-out data | N/A | N/A — **V1 and V2-alpha have never been scored on the identical test set.** V1's 13,324-image evaluation and V2's 659-image internal test are different images from different (though overlapping-in-source) pools. **No single number below should be read as "V2 beat V1" or vice versa on a like-for-like basis.** |
| Lab-image (PlantVillage-style) performance | 87.45% (13,324-image matched test, Corn/Potato/Rice/Wheat/Sugarcane combined) | 95.13% on the PlantVillage-sourced portion of V2's own held-out test (Corn/Potato only) — **not the same test, not the same classes, not directly comparable** |
| Real-world/field-image performance | 56.52% (V1's SAGE real-world test, 46 images, Corn/Potato/Rice) | 63.49% on the PlantDoc-sourced portion of V2's own held-out test (63 images, Corn/Potato only) — **again, a different test on different images; the two numbers are in the same rough range but are not a controlled comparison** |
| Corn Gray Leaf Spot ↔ Northern Leaf Blight confusion | Documented, repeated finding | **Still present** — 23 NLB→GLS and 6 GLS→NLB misclassifications in V2's own 659-image test. New data and fine-tuning did not resolve this. |
| OOD/unknown-input rejection | Confirmed unreliable on real off-taxonomy data (2,265-image test, Sugarcane OOD test) | Measured (not assumed) on a different, real off-taxonomy substitute set: combined-rule rejection is 26.67% on real unseen-disease images (up from V1's near-zero functional rejection, but still missing ~73% of cases) and 89% on non-plant/noise input |
| Preprocessing consistency between training and inference | Ambiguous — raw `img_to_array`, unconfirmed match to training | **Single shared implementation**, verified identical usage across training/validation/evaluation/inference (`scripts/preprocessing.py`) |

### The one-sentence honest summary

**V2-alpha is not a proven accuracy improvement over V1** — no controlled, same-test comparison exists to support that claim, and this card does not make it. What V2-alpha genuinely, verifiably improves on is **reproducibility and auditability**: known dataset provenance, a leakage-gated split, measured (not assumed) OOD behavior, and a single consistent preprocessing path — plus real, disclosed evidence (the PlantVillage-vs-PlantDoc test breakdown) that V1's lab-to-field generalization gap has **not** been closed simply by adding some real-world training images, which is itself a valuable, non-obvious finding for planning V2's next iteration.

## Current intended use

Farmer-facing plant disease identification for Corn and Potato, as an aid, not a sole diagnostic authority — subject to the OOD limitations above.

## Known limitations (full list)

1. Only Corn and Potato are covered; Rice, Wheat, Sugarcane are absent.
2. Real-world (field-photo) accuracy is materially lower than lab-image accuracy on V2's own held-out test (63.49% vs. 95.13%) — the core problem V2 was meant to address remains open.
3. Corn Gray Leaf Spot / Northern Leaf Blight confusion persists.
4. OOD rejection catches only ~27% of real unseen-disease photos (though ~89% of non-plant/noise input) — not adequate for unsupervised production deployment without further work.
5. `Potato___Healthy` has the smallest and most imbalanced training data (152 source images) of any class; its test-set precision (0.750, n=15) is the noisiest metric in this report.
6. The PlantDoc `"Corn leaf blight"` → `Corn___Northern_Leaf_Blight` label mapping is a documented assumption, not a verified fact, and should be reviewed by a domain expert.
7. V1's original SAGE/2,265-image/Sugarcane-OOD test sets could not be re-run against V2 (source images were never delivered, only V1's prediction CSVs) — this report's OOD numbers use a different, real substitute set instead.

## Where everything lives

- Model: `ml/artifacts/agrimind_plant_disease_v2.keras`
- Full metadata: `ml/artifacts/agrimind_plant_disease_v2_metadata.json`
- Dataset manifest: `ml/data/dataset_manifest.json`
- Leakage report: `ml/reports/v2_leakage_report.json`
- OOD report: `ml/reports/v2_ood_report.json`
- Internal test evaluation: `ml/reports/v2_internal_test_evaluation.json`
- Canonical inference wrapper: `ml/inference/v2_inference.py`; the production adapter is `apps/api/app/services/plant_vision_cnn.py`.
- Tests: `ml/tests/test_v2_pipeline.py` (17 tests, all passing)

## Documentation corrections (2026-09-23)

Two documentation/metadata-only corrections were made after initial delivery, with no change to the trained model, training data, or measured results:

1. **Duplicate-count terminology.** Earlier wording could be misread as "8 records dropped." The correct, unambiguous accounting: 8 exact-duplicate groups were identified, involving 16 records in total (2 byte-identical records per group, each a cross-class label conflict). All 16 records were excluded from the training dataset. `deduplicated_record_count` (6,586) was already correct and unchanged — only the surrounding terminology was clarified, in `ml/reports/v2_leakage_report.json`, `ml/data/dataset_manifest.json`, `ml/scripts/hashing.py`, and `docs/ml_v2_training_report.md`.
2. **PlantVillage licensing language.** Earlier wording ("does not restrict use for training or the resulting model weights beyond standard CC BY-SA norms") stated a legal conclusion beyond what the source license itself establishes. Corrected to: PlantVillage source material is licensed under CC BY-SA 3.0; the dataset license permits use subject to its terms, but the downstream licensing implications for trained model weights and commercial distribution require separate legal review. Technical use of the dataset in this experiment should not be interpreted as legal clearance for commercial release of the resulting model. Corrected in `ml/data/dataset_manifest.json` and `docs/ml_v2_training_report.md`.

Because correction 1 changed `dataset_manifest.json`'s text, its SHA-256 content hash changed (`b6d77171...` → `502cd4dd...`). This is reflected in `agrimind_plant_disease_v2_metadata.json` (documentation, corrected) but deliberately **not** in `training_config.json`, which is a frozen historical record of the manifest's content at the actual moment of training and is never modified after training. See that file's `dataset_manifest_sha256_note` for the full explanation.
