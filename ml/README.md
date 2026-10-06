# ml/ — AgriMind Plant Disease V2 pipeline

This directory contains the V2-alpha plant disease training, evaluation, OOD and
inference pipeline. The trained V2 model is now integrated into the local product's
Plant Vision service for Corn and Potato.

## Current status

- V2 model version: `agrimind_plant_disease_v3-field-research` (model B, see experiments/field_robust_v3/MODEL_CARD.md)
- 7 trained classes: 4 Corn + 3 Potato
- Production model path: `apps/api/models/agrimind_plant_disease_model.keras`
- Canonical V2 artifact: `artifacts/agrimind_plant_disease_v2.keras`
- Quick Scan: `/api/v1/ai/plant-vision/scan`
- Crop-linked Plant Vision: `/api/v1/ai/plant-vision/crops/{crop_id}/detect`
- OOD: calibrated confidence + Mahalanobis embedding-distance rule
- V1 binary and all other superseded CNN model files were deleted on 2026-10-04

## Evaluation

Current model test (field_robust_v3, near-duplicate-safe split): 95.6% lab, 70.2% PlantDoc field (n=57), 91.9% gitergo field corn (n=297). Earlier 92.11% figure belonged to the replaced v2-alpha model.
OOD results and limitations are documented in `reports/v2_ood_report.json` and
`docs/ml_v2_ood_report.md`.

This integration is an alpha product integration, not a claim of field-validated
diagnosis or commercial legal clearance.

## Layout

- `data/dataset_manifest.json` — acquired/deferred source and license evidence.
- `scripts/` — taxonomy, ingestion, hashing, splitting, preprocessing, training,
  evaluation and OOD scripts.
- `artifacts/` — trained model, metadata, training history/config and Mahalanobis fit.
- `reports/` — measured leakage, internal-test and OOD reports.
- `inference/v2_inference.py` — canonical V2 inference reference.
- `tests/test_v2_pipeline.py` — V2 pipeline tests.

## Scope limitation

Rice, Wheat and Sugarcane are deferred. They are not silently mapped to the current
Corn/Potato classes.
