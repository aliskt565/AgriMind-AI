> **This is now the PRODUCTION model** (installed 2026-10-04 at apps/api/models/). Model files for A and B were removed from this folder; B lives in apps/api/models/. 3-model comparison: model_comparison_3_models.json. OOD thresholds were refit for it.

# AgriMind V2 field-robust model B (research build) — 7 classes, Corn + Potato

**Status: research candidate. NOT cleared for commercial release, NOT field-validated, OOD thresholds NOT refit.**

## Test results (scored once, after training; selection used validation only)
| Test set | n | Accuracy | 95% Wilson CI |
|---|---|---|---|
| PlantVillage (lab) | 542 | 95.57% | 93.5–97.0 |
| gitergo Natural_environment (field, corn only) | 297 | 91.92% | 88.3–94.5 |
| PlantDoc (field, mixed sources) | 57 | 70.18% | 57.3–80.5 |
| All field combined | 354 | 88.42% | 84.7–91.4 |

Per-class recall (correct/total): PlantDoc — Corn rust 9/11, Corn GLS 4/6, Corn NLB 12/19, Potato early blight 11/11, Potato late blight 4/10.
gitergo — Corn rust 123/133, Corn GLS 5/9, Corn healthy 108/112, Corn NLB 37/43.
No Potato-healthy or Corn-healthy images exist in the PlantDoc test split; Potato-healthy has no field test images at all.

## Read this before quoting "80%+"
- 297 of 354 field test images come from one corn source (gitergo) that shares a similar setting with its training images. Treat 88% as optimistic.
- The independent mixed-source field set (PlantDoc, n=57) scored 70.2% (CI 57–80). The 80% target is NOT demonstrated there.
- gitergo's own train/test split leaked (~29% of its test images had near-duplicates in train). This build re-splits by near-duplicate group (dHash, Hamming <= 5, flips considered). Earlier numbers on the authors' split are not comparable.
- gitergo has no license file. Model B is trained on it => do not ship commercially without resolving that. The license-clean model A (PlantVillage + PlantDoc only) is in ../modelA_license_clean and is much weaker on field photos (see below).
- Not tested on real farmer photos from your own fields. That is the test that matters.

## Training recipe
MobileNetV2 (ImageNet weights) -> GAP -> Dense128 -> Dropout0.3 -> Dense7. 224x224. Stage1 head-only (3 ep, lr 1e-3), stage2 top-80 layers unfrozen, BN frozen (4 ep, lr 3e-5). Field images (PlantDoc, gitergo) weight x3, class weights clipped 0.4–4, label smoothing 0.1. Augmentation: random scale/aspect crop, flips, rot90, brightness/contrast/saturation/hue, gamma, colour cast, JPEG 25–85, blur, random erasing. Seed 42.
Data: PlantVillage raw/color 6,004 (CC BY-SA 3.0), PlantDoc 598 (CC BY 4.0), gitergo 3,380 (unlicensed).
Preprocessing is mobilenet_v2.preprocess_input, same as scripts/preprocessing.py in the repo.

## Reproduce
Paths in scripts are hard-coded to /home/claude/{data,proj}; edit them. Run prep.py (builds records.json + uint8 cache), then
`python train.py --name modelB_research_gitergo --use_gitergo 1 --s1_epochs 3 --s2_epochs 4` (~35 min on 1 CPU).
Remove `--use_gitergo 1` for the license-clean variant.

## Model A (license-clean: PlantVillage + PlantDoc only) — same recipe, no gitergo
| Test set | n | Accuracy | 95% CI |
|---|---|---|---|
| PlantVillage (lab) | 542 | 89.11% | 86.2-91.5 |
| PlantDoc (field) | 57 | 66.67% | 53.7-77.5 |
| gitergo field (corn; NOT in training) | 297 | 50.51% | 44.9-56.2 |
| All field combined | 354 | 53.11% | 47.9-58.2 |
Epoch was chosen on PlantDoc validation only (n=60), so selection is noisy. This is the realistic expectation for farmer photos
when the model has seen only ~480 real-world training images: ~50-67%, far below 80%. The jump to 88% for model B comes from
training on gitergo's field photos, not from the recipe.
Attribution needed if used: PlantDoc CC BY 4.0; PlantVillage CC BY-SA 3.0 (share-alike implications need legal review).
