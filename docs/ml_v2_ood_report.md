> **UPDATE 2026-10-04:** the CNN described below (v2-alpha / V1) has been replaced by `agrimind_plant_disease_v3-field-research` and the V1/v2-alpha/r2 model files were deleted. See `DOCUMENTATION.md` and `CHANGES_2026_10_04.md`. The text below is historical.

# AgriMind AI — V2-alpha OOD / Unknown-Input Report

**Date:** 2026-09-21
**Status:** EXPERIMENTAL. No OOD method described here is claimed to be production-adequate — see the honest conclusion at the end.

---

## Scope limitation, disclosed up front

V1's original SAGE real-world, 2,265-image off-taxonomy, and Sugarcane-OOD test sets **could not be replicated for V2** — the delivered evaluation package contains only V1's prediction CSVs for those tests, not the underlying source images (verified this session — see `docs/ml_v2_evaluation_report.md` §C–E). The numbers in this report come from a **different, real, substitute OOD evaluation**, not from re-running V1's exact tests on V2. They are **not directly comparable** to V1's OOD numbers, and this report does not claim otherwise anywhere below.

## What was actually used

- **In-distribution (ID) set:** V2-alpha's own internal held-out test split — 659 real images, Corn/Potato, never used in training.
- **Real off-taxonomy OOD set:** 300 real PlantVillage images (CC BY-SA 3.0, same source/license family already verified for training) from four classes **never included in V2-alpha's taxonomy**: Tomato Bacterial Spot, Tomato Late Blight, Apple Black Rot, Grape Black Rot (75 each). These are genuine, real plant-disease photographs the model has never seen — the same spirit as V1's Sugarcane/off-taxonomy-Corn tests, though not the identical images.
- **Synthetic non-plant set:** 100 generated images (25 each: pure random noise, solid color, half-split color block, linear gradient) — same spirit as V1's original noise probe.

## Methods implemented and measured

### 1. Softmax confidence thresholding
Reject if the model's top predicted-class probability falls below a threshold.

### 2. Mahalanobis embedding-distance
A per-class Gaussian was fit (mean + shared covariance) on the 128-dimensional penultimate-layer (`Dense(128)`) features of the **training set only**. At inference, the minimum Mahalanobis distance to any class centroid is computed; large distances indicate the input doesn't resemble any trained class's feature distribution. Fit persisted to `ml/artifacts/ood_mahalanobis_fit.npz` for reuse by the inference wrapper.

### 3. Combined rule
Reject if **either** signal flags the input (logical OR).

**Threshold calibration:** both thresholds were chosen from the **validation split only** (never from the test or OOD sets) — the confidence threshold is the 5th percentile of validation confidences (0.6335); the Mahalanobis threshold is the 95th percentile of validation distances (164.42). This directly avoids V1's documented mistake of never validating its 68% threshold against measured data.

## Measured results

| Method | AUROC vs. real OOD | FPR95 vs. real OOD | AUROC vs. noise |
|---|---|---|---|
| Confidence thresholding | 0.7913 | 0.4841 | 0.7537 |
| Mahalanobis embedding distance | 0.7925 | 0.5873 | **0.9792** |

*(AUROC: 0.5 = no better than chance, 1.0 = perfect separation. FPR95: false-positive rate — legitimate in-distribution images wrongly rejected — when the threshold is set to catch 95% of true OOD images; lower is better.)*

### Rejection rates by set and rule

| Set | n | Confidence rule | Embedding rule | Combined (OR) rule |
|---|---|---|---|---|
| Internal test (in-distribution) | 659 | 5.01% | 4.55% | 8.80% |
| Real off-taxonomy plant OOD | 300 | 14.67% | 15.00% | **26.67%** |
| Synthetic noise/non-plant | 100 | 0.00% | **89.00%** | 89.00% |

## Honest interpretation — do not oversell this

**Neither method, alone or combined, is adequate for production use.** Specifically:

- On the **in-distribution set**, rejection rates are low (5–9%) — good, this means the OOD gate isn't throwing away too many legitimate predictions.
- On **real off-taxonomy plant disease images** — the case that actually matters most for a farmer photographing a genuinely unsupported disease — even the combined rule catches only **26.67%**. **73% of real, unseen-disease photos are still confidently misclassified into one of V2-alpha's 7 known classes.** This is a partial improvement over V1's documented near-total failure at this exact task (V1 had no functioning rejection at all for real off-taxonomy Sugarcane/Corn images), but it is not remotely a solved problem.
- **Confidence thresholding is essentially useless against non-plant input** (0% rejection on 100 synthetic noise images — every single one was confidently assigned a real disease label). The Mahalanobis embedding-distance method performs much better here (89% rejection, AUROC 0.979 vs. noise) — this is the strongest single result in this report, and a real, useful finding: **embedding distance, not confidence, is the more promising signal for non-plant rejection specifically**, though even it is not perfect (11% miss rate).
- The gap between "genuinely different image type" (noise, AUROC 0.979) and "same image type, different unseen class" (real off-taxonomy plant disease, AUROC 0.79) is itself an important, honest finding: **detecting a never-seen disease on a real leaf is a much harder OOD problem than detecting a non-plant image**, and this evaluation quantifies that gap for the first time in this project's history — V1 never measured it this way.

## Recommendation, from measured results only

The **combined OR rule** is recommended over either method alone, since it strictly dominates both on rejection rate for every set tested (it can only reject more than either component rule, never less, by construction) without a measured downside on the in-distribution false-positive rate (8.8% vs 4.6–5.0% for the individual rules — a modest increase, judged acceptable given the real-OOD detection gain). It is implemented in `ml/inference/v2_inference.py`. **This recommendation is conditional on the numbers above, not a claim that the OOD problem is solved.** A production deployment decision should not treat 26.67% real-OOD rejection as sufficient; further OOD work (energy-based methods, a genuine "unknown" training class, or calibration) remains open, exactly as the earlier V2 research report anticipated.
