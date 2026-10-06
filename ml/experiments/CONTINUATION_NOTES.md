# V2 Accuracy-Improvement Experiments — Continuation Notes

**Purpose of this file:** if you are a new chat session picking this project up, read this first. It explains exactly what was tried, what worked, what didn't, and what an honest next step looks like. Nothing in this file is aspirational — every number here was actually measured by running code, not estimated.

## Background

The deployed model, `agrimind_plant_disease_v2.keras` (in `ml/artifacts/`, referred to as **v2-alpha**), covers only Corn and Potato (7 classes) because the other three crops' licensed datasets (Rice, Wheat, Sugarcane) live on Mendeley/Zenodo/Kaggle, which this project's working environment cannot reach (see `docs/ml_v2_dataset_license_verification_2026_09.md` and `ml/data/dataset_manifest.json` for exactly which datasets and why).

Separately, v2-alpha's accuracy on real-world (farmer phone photo) images was found to be much lower than its accuracy on lab-style training images. This folder (`ml/experiments/`) documents four attempts to close that gap.

## What was measured — the honest numbers

A large (n=3,380), real, license-unclear dataset of real-world Corn photos (`gitergo/Datasets` on GitHub, `Natural_environment/` folder) was used **for measurement only, never for training**, specifically because it has no LICENSE file and this is a live commercial product — see the full reasoning in the chat history / model card. This gave a much more statistically reliable read than the original 63-image PlantDoc-based test:

| Model | Real-world Corn accuracy (n=3,380) | 95% CI |
|---|---|---|
| v2-alpha (deployed) | 37.19% | [35.58%, 38.83%] |
| **v2-r2** (original run, 5+5 epochs) | **52.40%** (best result found) | [50.71%, 54.08%] |
| v2-r3 (gentler augmentation, lower weight) | 46.92% | [45.25%, 48.61%] |
| v2-r4 (pushed r2 further) | 49.79% | did not beat r2 |

**Conclusion from this experimentation:** augmentation intensity and real-image upweighting both genuinely help (v2-alpha → r2 is a real, statistically solid improvement), but pushing further (r4) did not improve on r2, and going gentler (r3) made things worse. r2 is a local optimum for this technique on this data. None of the four configurations get anywhere near 80% real-world accuracy. The limiting factor is the amount of genuine real-world training data (only 582 PlantDoc images), not the training technique — see the model card for the full argument.

## What is actually in `ml/experiments/` right now

- `experiments/scripts/train_v2_r2.py`, `train_v2_r3.py`, `train_v2_r4.py` — the three follow-up training scripts (reconstructed faithfully from the original session; see "A note on reproducibility" below).
- `scripts/validate_corn_natural_environment.py` — the large-scale, measurement-only validation script (not re-run this session; re-run it if you want fresh large-scale numbers — see "To re-run the large validation" below).
- `artifacts_v2_r2/agrimind_plant_disease_v2_r2.keras` — a **retrained** r2 model (see caveat below).
- `reports/v2_r2_internal_test_evaluation.json` — internal held-out test results for this retrained model.

## A note on reproducibility — please read before trusting the shipped r2 model file exactly

This project's working environment restarted itself multiple times during both the original experiments and this re-packaging session, wiping all in-progress work each time (this is a real, repeated, environment-level instability, not a one-off). Because of this:

- The **r2 training script was re-run from scratch** to produce the `agrimind_plant_disease_v2_r2.keras` file in this folder, using **3+3 epochs instead of the original 5+5** (to finish reliably within one working session given the instability). Its internal-test numbers are real and measured, but slightly different from the original 5+5 run:
  - This run: overall 85.43%, PlantVillage (lab) 87.64%, **PlantDoc (real-world, n=52) 59.62%**
  - Original 5+5 run: overall 88.01%, PlantVillage 90.10%, PlantDoc (n=63) 68.25%
  - Both are real, both clearly beat v2-alpha's real-world number; the exact figure depends on epoch count and should not be treated as more precise than ±5-10 points given the small PlantDoc test sample.
- The large-scale (n=3,380) external validation was **not re-run** in this packaging session (to avoid another multi-hour redo cycle) — the table above reflects the original run's numbers for v2-alpha/r2/r3/r4, not this retrained r2 file specifically. If you want a precise large-scale number for *this exact* r2 file, re-run the validation script (instructions below).
- `experiments/scripts/train_v2_r3.py` and `experiments/scripts/train_v2_r4.py` are included for reference/transparency but were **not re-run or re-verified** this session — treat their presence as "here is exactly what was tried" documentation, not as verified-working code against the current data split.

## If you want to pick this up

1. **To just use the current best model:** `ml/artifacts/agrimind_plant_disease_v2.keras` (v2-alpha) is what's actually deployed in the product right now. Swapping in r2 requires recalibrating the OOD/unknown-input rejection thresholds (they were fit specifically to v2-alpha) — do not swap the model file alone.
2. **To re-run the large validation** against the r2 model in this folder:
   ```
   cd <repo_root>
   git clone --filter=blob:none --sparse --depth 1 https://github.com/gitergo/Datasets.git /tmp/gitergo
   cd /tmp/gitergo && git sparse-checkout init --cone && git sparse-checkout set Natural_environment
   # then point validate_corn_natural_environment.py's BASE constant at /tmp/gitergo/Natural_environment and run it
   ```
3. **To get real gains past ~52%:** source more genuinely real-world, properly-licensed Corn/Potato field photos (the actual bottleneck — see above), or get the Rice/Wheat/Sugarcane datasets flowing (same licensing blocker, separate from this accuracy problem).
4. **Expect environment instability.** If you are re-running `train.py` or any `train_v2_r*.py` script, run it with a short epoch count first (2-3) to get a known-good baseline file before attempting a longer run, and check `ps aux` / the log file frequently rather than assuming a long background job survived.

---
## Update 2026-10-04 — field_robust_v3 (model B)

New folder `ml/experiments/field_robust_v3/` (see its MODEL_CARD.md). Rebuilt dataset from GitHub sources
(PlantVillage, PlantDoc, gitergo Natural_environment) with near-duplicate-group splitting; gitergo's own split leaks
(~29% of its test images have near-duplicates in train), so numbers are not comparable with the earlier 52.40% figure.
Model B test: gitergo field 91.92% (n=297), PlantDoc 70.18% (n=57, CI 57-80%), all field combined 88.42% (n=354).
The 80% target on mixed-source field photos is NOT demonstrated (PlantDoc). Trained on unlicensed gitergo data -> research only.
NOT deployed: the app still uses v2-alpha; OOD thresholds were not refit. License-clean model A (no gitergo): PlantDoc 66.67% (n=57), gitergo 50.51% (n=297, unseen), PlantVillage 89.11%. No other dataset was reachable (Kaggle/Mendeley/Zenodo are blocked in the sandbox).


## Update 2026-10-04 (final)
Model B was selected and installed as the production CNN; OOD refit; all other CNN model files (V1 legacy, r2, model A, v2-alpha) deleted. This file's earlier references to those .keras files are historical. See ../../DOCUMENTATION.md.
