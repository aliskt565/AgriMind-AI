> **UPDATE 2026-10-04:** the CNN described below (v2-alpha / V1) has been replaced by `agrimind_plant_disease_v3-field-research` and the V1/v2-alpha/r2 model files were deleted. See `DOCUMENTATION.md` and `CHANGES_2026_10_04.md`. The text below is historical.

# ML Evaluation Report — agrimind_plant_disease_model.keras

**Date:** 2026-09-18 (expanded evaluation added; see new top section below). Original report dated 2026-09-15 (corrected/forensic update; original evaluation run 2026-09-14) is preserved further down, unchanged.
**Model evaluated:** `apps/api/models/agrimind_plant_disease_model.keras` — unchanged across all phases and across this update; nothing has been retrained or modified. This model remains **V1**.

---

## 2026-09-18 update — expanded Colab evaluation evidence

A much larger evaluation run (Google Colab) was performed against this same, unmodified V1 model and is now the primary evidence base alongside the original 280-image evaluation below. Full per-image data lives in the delivered `AgriMind-ML-Evaluation.zip`; a structured machine-readable summary is at `docs/ml_evaluation_expanded_2026_09.json`. Nothing in this update changes or retracts the original 280-image evaluation — it stands alongside it as a separate, additional data point.

### A. Full Five Crop Diseases Dataset (13,324 images) — valid accuracy benchmark

- **11,652 / 13,324 correct — 87.45% micro accuracy.** Macro precision 0.84, macro recall 0.81, **macro F1 0.82**, weighted F1 0.87.
- Covers all 17 in-taxonomy classes for which this dataset has ground truth (`Background___Non_Plant` never appears as a true label in this set).
- **Crop-level accuracy:** Corn 93.7%, Potato 97.6%, Wheat 86.8%, **Rice 79.2%**, **generic Sugarcane-adjacent classes (Healthy/Bacterial Blight/Red Rot) 53.3%**.
- **Notable class-level weaknesses:** `Rice___Leaf_Blast` (54.0% recall — largest single confusion is with `Rice___Healthy`, 359 images); `Corn___Gray_Leaf_Spot` ↔ `Corn___Northern_Leaf_Blight` remains a strong bidirectional confusion (112 + 104 misclassifications), consistent with the original 280-image report.
- **Training-data overlap: UNKNOWN**, exactly as with the original evaluation — images are sourced from a public Kaggle dataset per the recorded paths; no way to establish overlap with this model's original (unrecoverable) training data.

### B. PlantVillage 250-image evaluation — valid accuracy benchmark, DISTINCT from the original 280-image test

- **240 / 250 correct — 96.0% accuracy**, same 7-class scope as the original evaluation (Corn ×4, Potato ×3).
- **This is a separate, newer run, not a restatement of the 92.86%/280-image figure below.** Different sample (250 vs. 280 images), different result (96.0% vs. 92.86%). Both numbers should be reported; neither supersedes the other. Both carry the same unresolved train/test-overlap caveat.

### C. 2,265-image external dataset — NOT a valid accuracy benchmark (taxonomy mismatch)

- Both ground-truth labels present in this dataset — `Corn_(Maize)___Leaf_Spot` and `Corn_(Maize)___Maize_Streak_Virus` — are **outside the model's 18-class taxonomy**. There is no correct answer the model could give for any of these 2,265 images.
- **Do not report this as "0% accuracy."** The correct framing is: taxonomy-mismatch / out-of-distribution evidence only.
- Observed behavior: the model does not abstain. Predictions scattered across 18 known classes (`Wheat___Healthy` 656×, `Corn___Healthy` 408×, `Wheat___Brown_Rust` 359×, and 15 others) at a fairly high average confidence (0.78, up to 0.9999).

### D. SAGE real-world matched evaluation (46 usable images) — valid accuracy benchmark, small sample

- **26 / 46 correct — 56.52% accuracy.** Crop breakdown: **Corn 12/25, Potato 13/15, Rice 1/6.**
- Classes covered are all in-taxonomy (Corn: Common_Rust/Gray_Leaf_Spot/Northern_Leaf_Blight; Potato: Early_Blight/Late_Blight; Rice: Brown_Spot).
- This is a small external real-world evaluation, but it is the only evaluation sourced from diverse real-world image origins (Bugwood, LeafNet, CDDM, "New_Plant_Di" — not single-source lab photography like PlantVillage). Accuracy drops sharply versus the lab-image evaluations above, and several errors sit above 99% confidence (e.g., a true Corn Common Rust image predicted Corn Healthy at 99.99% confidence). Treat as directional evidence of a lab-to-real-world generalization gap, not a precise accuracy figure, given the small N.

### E. SAGE Sugarcane OOD (110 images) — NOT an accuracy test

- 17 distinct real sugarcane disease labels were tested (Yellow_Spot, Grassy_Shoot, Sett_Rot, Banded_Chlorosis, Pokkah_Boeng, Sugarcane_Mosaic_Virus, and others), **none of which map cleanly onto the model's only sugarcane-adjacent classes** (generic `Healthy` / `Bacterial Blight` / `Red Rot`).
- Average confidence: **66.04%**.
- **45% (50 / 110) of these unsupported-class images still exceeded the model's 68% confidence gate** — the existing threshold does not reliably reject this class of out-of-taxonomy input.
- This is explicitly OOD evidence, not an accuracy measurement — there is no valid ground-truth label for these images under the current taxonomy.

### Error analysis corrections and findings from this expanded evaluation

- **Correction to an evaluation-package artifact:** `AgriMind-ML-Evaluation.zip`'s `02_Error_Analysis/high_confidence_wrong_predictions.csv` is **not actually filtered to high-confidence predictions**. Direct comparison confirms it contains the identical 1,672 rows as `all_wrong_predictions.csv` (confidence range 22.0%–99.998%), merely sorted by confidence descending. Anyone using this file should treat it as "all wrong predictions, sorted by confidence," not a pre-filtered high-confidence-only sample. (Not renamed or altered here — the correction is documentation-only, per the source data.)
- **Confidence is not a calibrated probability.** Across the 13,324-image test, the SAGE real-world test, and the SAGE Sugarcane OOD test, correct and incorrect predictions have substantially overlapping confidence ranges, and numerous wrong predictions exceed 99% confidence.
- **OOD/unknown-class rejection remains unreliable — now confirmed three separate ways**: (1) the original synthetic-noise probe (`ml_probe_results.json`), (2) the 2,265-image off-taxonomy Corn test (C above), (3) the 110-image off-taxonomy Sugarcane test (E above). No threshold-based fix has been evidence-backed by any of these.

### V1 vs. product Plant Vision — unchanged, restated for clarity

This expanded evaluation changes nothing about integration status. **The V1 CNN (`apps/api/models/agrimind_plant_disease_model.keras`, served only via `POST /predict-disease`) is not, and remains not, connected to the product's Plant Vision feature** (`POST /api/v1/ai/plant-vision/crops/{crop_id}/detect`, which always uses `MockPlantVisionProvider`). No architecture change was made or is proposed here.

### V2 status

**V2 does not exist yet.** No retraining, new architecture, or new pipeline has been implemented. The evidence above is scoped to characterizing V1 more thoroughly, to inform a future V2 effort. Planned (not yet started) V2 direction: reproducible dataset acquisition with explicit provenance/licensing, a canonical taxonomy (including real Sugarcane disease classes), duplicate detection, leakage-safe source-aware splitting, consistent preprocessing, transfer learning with staged fine-tuning, stronger real-world evaluation, genuine OOD/unknown detection, calibrated uncertainty, and experiment tracking/model versioning.

---

## Original evaluation (280 images, 2026-09-14/15) — preserved below, unchanged

## ⚠️ Correction to the previous version of this report

The previous version of this report described the 280-image PlantVillage evaluation as a "held-out" test. **That characterization was not justified and has been corrected.** "Held-out" implies provable separation from the model's original training data. As the forensic audit below establishes, **the original training dataset, script, and class-index mapping are not recoverable from this project by any means available**, so there is no way to prove these 280 images were not part of whatever the model was originally trained on. The correct, honest description is:

> **92.86% accuracy on a 280-image PlantVillage evaluation sample covering 7 of the model's 18 classes.**

This is a real, correctly-computed number on real, correctly-labeled images. What it is *not* is proof of held-out generalization performance — it could be inflated by undetectable train/test overlap, or it could be a genuine indicator of real generalization. There is no way to distinguish which from what's available.

## Forensic provenance audit (new this session)

Beyond the exhaustive project-wide text search already performed in prior phases (still valid — no new files have appeared), I went deeper into the `.keras` artifact itself:

**A. Model provenance found:**
- `metadata.json`: `keras_version: 3.13.2`, saved `2026-09-07 10:26:59`. No dataset reference.
- `config.json` → `compile_config`: optimizer = Adam (default learning rate 0.001, default β₁/β₂/ε — no evidence of custom LR tuning), loss = `sparse_categorical_crossentropy` (implies integer, not one-hot, labels — consistent with a standard `flow_from_directory`/`image_dataset_from_directory` pipeline, but this doesn't identify *which* dataset).
- `model.weights.h5` → **optimizer state (Adam momentum/velocity buffers) is present and its variable shapes exactly match only the `Dense(128)` and `Dense(18)` head layers** (shapes `(1280,128)`, `(128,)`, `(128,18)`, `(18,)`, each ×2 for momentum+velocity, plus 2 scalar tracking vars = 10 total). **The saved artifact strongly indicates that, in the training state represented by this saved optimizer, only the classification head was being optimized and the MobileNetV2 backbone was frozen.** This is a more direct signal than the static `"trainable": false` config flag alone (which only records the model's state at save time). It does **not** prove the backbone was never fine-tuned at an earlier stage — a prior training run could have updated the backbone, been re-frozen, and re-compiled with a fresh optimizer before this file was saved; the saved optimizer state has no memory of any such earlier stage.
- Full HDF5 attribute dump (161 attributes): every single one is a standard Keras-internal MobileNetV2 layer name (`block_14_depthwise_BN`, etc.) — **no dataset paths, usernames, file references, or custom identifiers of any kind.**

**B. Original dataset found:** **Not found.** No path, name, or reference anywhere in the model file or project.

**C. Original training code found:** **Not found.** (Re-confirmed; see prior phases' exhaustive content search — still zero matches for training/dataset keywords across the whole project.)

**D. Original preprocessing found:** **Partially inferable, not confirmed.** `img_to_array` + raw resize is used at inference (in `main.py`); there is no artifact proving training used the same raw-pixel approach rather than MobileNetV2's standard `preprocess_input` ([-1,1] scaling). If training used `preprocess_input` and inference doesn't (or vice versa), every prediction would be systematically degraded by a preprocessing mismatch — and the strong evaluation accuracy (92.86%) argues *against* a severe mismatch existing, since a badly mismatched preprocessing pipeline typically degrades accuracy substantially, not subtly. This is **plausible inference**, not proof.

**E. Original class mapping found:** **Not found.** No `class_indices.json` or equivalent exists anywhere.

**F. Evidence of PlantVillage training overlap:** **Genuinely ambiguous — laid out honestly below, not resolved:**
- *Evidence against a direct, naive PlantVillage `flow_from_directory` training run:* the model's `CLASS_NAMES` strings for the 7 overlapping classes are **not** byte-identical to PlantVillage's real folder names (verified directly: real folder is `Corn_(maize)___Common_rust_`, model's label is `Corn___Common_Rust` — different casing, no `(maize)` qualifier, different trailing punctuation). If training had run directly against the real PlantVillage folder structure via a standard Keras data loader, the class list would ordinarily be auto-derived verbatim from those folder names, not manually retyped.
- *This does not rule out overlap*, however: (a) the developer may have manually renamed folders or retyped a class list after training on the real images (introducing a transcription risk, but not ruling out the same underlying photos being used), or (b) training may have used a *different* repackaging of the same underlying PlantVillage photography under simplified folder names (such re-packaged mirrors are common on Kaggle) — which would mean the same physical images, differently organized.
- **I cannot distinguish between "trained on these exact images," "trained on a different collection of the same real diseases," or "trained on something else entirely that happens to generalize similarly."** All three remain plausible. Stating a conclusion beyond this would be exactly the kind of inferred-certainty the audit was meant to prevent.

**G. Can the 92.86% be considered unseen/held-out?** **No — cannot be established either way.** Treat it as: *a real accuracy measurement on real labeled images, of unknown overlap status with training data.*

## Data source (verified, unchanged from before)

- **Dataset used for this evaluation:** PlantVillage Dataset (Mohanty, Hughes, Salathé 2016, DOI: 10.3389/fpls.2016.01419), github.com/spMohanty/PlantVillage-Dataset
- **License:** CC-BY-SA-3.0 (declared on the dataset's Hugging Face mirror; no LICENSE file exists in the GitHub repo itself). Commercial use permitted with attribution; ShareAlike implications for a trained model are a genuinely unsettled legal question, not resolved here.

## Scope

Of the model's 18 classes, only 7 have any legitimate, verifiable real-image source available in this environment (Corn ×4, Potato ×3). The other 11 — `Background___Non_Plant`, `Bacterial Blight`, `Healthy` (bare), `Red Rot`, all 4 Rice classes, all 3 Wheat classes — **remain completely unevaluated.** A search this session for alternative GitHub-hosted rice/wheat-disease datasets with real checked-in images and clear licensing found several candidates, none of which cleanly matched this model's exact class taxonomy with verifiable licensing without disproportionate further effort. No additional coverage was responsibly obtainable.

## Corrected metrics — strict 7-class scope

The previous report's macro F1 (0.813) was **artificially deflated** by including a phantom 8th label (`Wheat___Healthy`, the one out-of-scope prediction) with zero true support in the averaging denominator. Recomputed with the label set correctly restricted to the 7 actually-evaluated classes (the out-of-scope prediction is still counted as an error against its true class's recall — it is not dropped from accuracy):

- **Overall accuracy: 92.86%** (260/280) — unchanged, this was always correct.
- **Macro precision: 0.938 | Macro recall: 0.929 | Macro F1: 0.929** (corrected from 0.813) | **Weighted F1: 0.929**

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Corn___Common_Rust | 1.000 | 1.000 | 1.000 | 40 |
| Corn___Gray_Leaf_Spot | 0.900 | 0.675 | 0.771 | 40 |
| Corn___Healthy | 1.000 | 1.000 | 1.000 | 40 |
| Corn___Northern_Leaf_Blight | 0.755 | 0.925 | 0.831 | 40 |
| Potato___Early_Blight | 1.000 | 0.975 | 0.987 | 40 |
| Potato___Healthy | 1.000 | 0.925 | 0.961 | 40 |
| Potato___Late_Blight | 0.909 | 1.000 | 0.952 | 40 |

**Out-of-scope prediction (reported separately, not blended into the 7-class averages):** 1 of 280 images (a `Corn___Gray_Leaf_Spot` image, 66.3% confidence) was predicted as `Wheat___Healthy` — a class this evaluation has no ground truth for. This is a real, concrete example of cross-crop confusion risk, and is counted as an error in `Corn___Gray_Leaf_Spot`'s recall above.

Confusion matrix (7×7, rows=true, columns=predicted):
```
                              Rust  GLS  Hlthy  NLB  E.Blt  P.Hlth  L.Blt
Corn___Common_Rust            40    0     0     0     0      0      0
Corn___Gray_Leaf_Spot          0   27     0    12     0      0      0
Corn___Healthy                 0    0    40     0     0      0      0
Corn___Northern_Leaf_Blight    0    3     0    37     0      0      0
Potato___Early_Blight          0    0     0     0    39      0      1
Potato___Healthy               0    0     0     0     0     37      3
Potato___Late_Blight           0    0     0     0     0      0     40
```
(The 1 out-of-scope Gray_Leaf_Spot→Wheat___Healthy prediction is not a column in this 7×7 matrix; see the note above.)

Dominant error pattern remains Gray_Leaf_Spot ↔ Northern_Leaf_Blight — a scientifically sensible confusion between two visually similar real corn diseases.

## Confidence threshold (68%) — unchanged findings

15/260 correct predictions (5.8%) fall below 68% confidence (would be wrongly rejected); 7/20 incorrect predictions (35%) sit at or above 68% (including two confident healthy→Late-Blight false alarms). Correct and incorrect confidence ranges substantially overlap (correct as low as 50.2%; incorrect as high as 92.9%). No single threshold in this data cleanly separates correct from incorrect.

## OOD / noise — unchanged, negative result on margin/entropy

Random noise still passes the green-pixel filter and 68% gate (81–88% confidence across runs). Investigated whether prediction margin (top-1 vs top-2 gap) or entropy could serve as an additional rejection signal: **it cannot, based on actual evidence** — the noise prediction is sharply peaked (75.9-point margin, 0.386 entropy), not diffuse. This is the standard, well-documented overconfidence-on-OOD-input behavior of softmax classifiers. No threshold-based fix is implemented, because none is evidence-backed.

## Was retraining performed?

**No.** The forensic audit found nothing that changes this call: no legitimate additional training data exists for the 11 unevaluated classes, and the 7 evaluated classes perform reasonably well, so retraining isn't evidence-justified for them either. Retraining would also not resolve the train/test-overlap ambiguity above — that ambiguity is about the *original* training run, which no amount of new training can retroactively clarify.

## Is real Plant Vision integration justified?

**Not yet, and not fully even if a decision is made to proceed.** If you choose to move forward: only the 7 evaluated classes have any real evidence behind them, and even that evidence carries the unresolved train/test-overlap caveat above — it is suggestive, not proof of generalization. The other 11 classes have zero evidence. Any integration decision should treat this as a partial, caveated signal, not a validated model.

## Exact recommended next step

Two independent paths, either is reasonable:
1. **Accept the uncertainty and scope a first integration to only the 7 evaluated classes**, clearly labeling the feature's real limitations to end users, while treating the 92.86% figure internally as "real but not provably held-out."
2. **Obtain genuinely new photos of these same 7 classes that you personally collect or source with known provenance** (not from any existing public dataset) — this is the only way to get a true, provably-unseen evaluation, since it would be data the model's original training run could not possibly have included.

Either way, the 11 unevaluated classes remain a real product-honesty issue until real data is found for them.

**2026-09-18 note:** the expanded evaluation added at the top of this document (13,324-image, 250-image, 2,265-image, and two SAGE evaluations) provides much of the additional real-world signal path 2 above called for, though not via personally-collected photos — see that section for what it does and does not resolve. Neither option above is fully closed out by it: the Sugarcane and Rice weaknesses it surfaces, and the confirmed-unreliable OOD rejection, are new open items for V2 planning rather than a resolution of the original recommendation.
