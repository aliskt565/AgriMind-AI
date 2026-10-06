> **UPDATE 2026-10-04:** the CNN described below (v2-alpha / V1) has been replaced by `agrimind_plant_disease_v3-field-research` and the V1/v2-alpha/r2 model files were deleted. See `DOCUMENTATION.md` and `CHANGES_2026_10_04.md`. The text below is historical.

# AgriMind AI — V2-alpha Evaluation Report

**Date:** 2026-09-21
**Status:** EXPERIMENTAL

---

## A. Internal held-out test evaluation

659 images, never used in training or for Stage 1/2 checkpoint selection (leakage-gated — see `docs/ml_v2_training_report.md` §4).

| Metric | Value |
|---|---|
| Overall accuracy | **92.11%** |
| Macro precision | 0.8876 |
| Macro recall | 0.9267 |
| **Macro F1** | **0.9020** |
| Weighted precision | 0.9298 |
| Weighted recall | 0.9211 |
| **Weighted F1** | **0.9230** |
| Mean confidence (all predictions) | 0.9477 |

### Per-class

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Corn___Common_Rust | 0.984 | 0.954 | 0.969 | 131 |
| Corn___Gray_Leaf_Spot | 0.658 | 0.862 | 0.746 | 58 |
| Corn___Healthy | 0.983 | 0.991 | 0.987 | 116 |
| Corn___Northern_Leaf_Blight | 0.903 | 0.788 | 0.842 | 118 |
| Potato___Early_Blight | 0.964 | 0.973 | 0.969 | 111 |
| Potato___Healthy | 0.750 | 1.000 | 0.857 | 15 |
| Potato___Late_Blight | 0.971 | 0.918 | 0.944 | 110 |

**Corn___Gray_Leaf_Spot has the weakest precision (0.658)** — driven directly by the confusion below. `Potato___Healthy`'s precision (0.750) reflects its small support (15 images) — a single misclassification moves this number substantially; treat it as noisier than the other rows.

### Confusion matrix (rows = true, columns = predicted)

|  | Common_Rust | Gray_Leaf_Spot | Healthy(Corn) | NLB | Early_Blight | Healthy(Potato) | Late_Blight |
|---|---|---|---|---|---|---|---|
| **Common_Rust** | 125 | 2 | 0 | 4 | 0 | 0 | 0 |
| **Gray_Leaf_Spot** | 2 | 50 | 0 | **6** | 0 | 0 | 0 |
| **Healthy(Corn)** | 0 | 1 | 115 | 0 | 0 | 0 | 0 |
| **NLB** | 0 | **23** | 2 | 93 | 0 | 0 | 0 |
| **Early_Blight** | 0 | 0 | 0 | 0 | 108 | 0 | 3 |
| **Healthy(Potato)** | 0 | 0 | 0 | 0 | 0 | 15 | 0 |
| **Late_Blight** | 0 | 0 | 0 | 0 | 4 | 5 | 101 |

**Corn Gray Leaf Spot ↔ Northern Leaf Blight confusion persists in V2** (23 NLB→GLS, 6 GLS→NLB) — this is the same confusion pair V1's own evidence flagged repeatedly. New training data and a fine-tuned backbone did **not** resolve it. This should be treated as a genuinely hard visual discrimination problem for this architecture/data combination, not a data-quantity problem alone.

### Source-separated breakdown — the most important, least flattering number in this report

| Source | n (of the 659 test images) | Accuracy | Mean confidence |
|---|---|---|---|
| PlantVillage (lab-style) | 596 | **95.13%** | 0.9681 |
| PlantDoc (real-world field) | 63 | **63.49%** | 0.7547 |

**Do not read the 92.11% overall figure as representative of real-world performance.** It is dominated by the much larger lab-image test count. The field-image subset — small (63 images) but the only real-world signal in this held-out test — shows accuracy 31.6 percentage points lower than the lab-image subset. **V1's demonstrated lab-to-field generalization gap is not resolved in V2-alpha**, despite V2 having been trained on some real field imagery (PlantDoc) that V1 never saw. Adding field data to training did not, by itself, close this gap in this pass.

## B. Source-separated external evaluation

The breakdown above **is** the source-separated evaluation available this session — PlantDoc and PlantVillage are different, independently-sourced datasets, and the split assignment (Section A) ensures a PlantDoc test image was never near-duplicate-adjacent to a PlantDoc training image (verified: 0 cross-split leakage violations). A fully separate "hold out an entire source" run (train on PlantVillage only, test entirely on PlantDoc) was not performed this session due to time — the source-breakdown above already surfaces the generalization gap without requiring it, though a dedicated run would give a cleaner isolation of the effect and is recommended as a next step.

## C. SAGE real-world matched evaluation — COULD NOT BE RUN

**This is a real blocker, disclosed rather than worked around with fabricated numbers.** The delivered `AgriMind-ML-Evaluation.zip` contains only V1's **prediction CSVs** for the SAGE real-world test — not the underlying source images. Verified directly this session: of every file in that archive, only `07_Manual_Test/test_corn_rust.jpg` is an actual image; `05_SAGE_Real_World/sage_strict_51_real_world_predictions.csv` and every other evaluation folder contain CSV output only. V2 cannot be scored against images it was never given. **To close this gap: the actual SAGE real-world image files are needed**, not just V1's recorded predictions on them.

As a substitute — not a replacement — for this specific test, Section A's PlantDoc-sourced test subset (63 real-world field images) provides comparable real-world-generalization signal for the classes V2-alpha actually covers (Corn/Potato). It is a different, smaller, differently-sourced set than V1's SAGE test, so **the numbers are not directly comparable** — see the V1-vs-V2 comparison in `docs/ml_v2_model_card.md`.

## D. 2,265-image unsupported/off-taxonomy dataset — COULD NOT BE RUN (same reason)

Same blocker as Section C: only V1's prediction CSV (`03_Full_Dataset_Test/all_2265_predictions.csv`) was delivered, not the source images. See `docs/ml_v2_ood_report.md` for what was used instead (a genuine, real, license-verified substitute OOD test built from other PlantVillage crops).

## E. 110-image Sugarcane OOD evaluation — COULD NOT BE RUN (same reason)

Same blocker. Additionally, Sugarcane is outside V2-alpha's trained taxonomy entirely this pass (Section 1 of the training report), so even with the source images this would only ever have been a generic OOD test for V2-alpha, not a taxonomy-relevant one the way it was for V1.

## F. Non-plant/noise test

100 synthetic images (25 each: pure random noise, solid color, half-split color block, linear gradient) were generated and evaluated as part of the OOD pass. See `docs/ml_v2_ood_report.md` for full results — summary: the embedding-distance OOD method rejects 89% of these; softmax confidence thresholding rejects 0% of them (confidently misclassifies every single one into a real disease class). This is a stark, real finding: **confidence alone is not a usable non-plant detector for this model**, echoing V1's own documented weakness in this exact area.

## Manual sanity check

The one real, standalone image provided (`07_Manual_Test/test_corn_rust.jpg`) was run through the full V2 inference pipeline: predicted `Corn___Common_Rust` at 99.9995% confidence — correct, per the filename. This is a single spot-check, not a statistic, and is reported as such.
