> **UPDATE 2026-10-04:** the CNN described below (v2-alpha / V1) has been replaced by `agrimind_plant_disease_v3-field-research` and the V1/v2-alpha/r2 model files were deleted. See `DOCUMENTATION.md` and `CHANGES_2026_10_04.md`. The text below is historical.

# AgriMind AI — V2/V1 Merge Report — 2026-09-25

## Merge result

The supplied full AgriMind project was merged with the supplied V2 ML pipeline.

### Active model

The active production model path is:

`apps/api/models/agrimind_plant_disease_model.keras`

It now contains the V2-alpha model.

Canonical V2 artifact:

`ml/artifacts/agrimind_plant_disease_v2.keras`

SHA-256:

`674e2f89742f93340b80fb1f901c1bfdf550ec9922307c79dc3d9b421cf50387`

The two V2 model copies were verified byte-identical.

### V1 preservation

The original V1 binary was preserved at:

`ml/evaluation_archive/v1_legacy/agrimind_plant_disease_model_v1_legacy.keras`

V1 SHA-256:

`c8fe7a2e4fdb165c112e41683e0c5891cea1ed8fad33ccdae8d0bd44054149ba`

No V1 binary was silently destroyed.

## Plant Vision integration

The shared production service is:

`apps/api/app/services/plant_vision_cnn.py`

It uses:
- V2 preprocessing
- V2 seven-class taxonomy
- calibrated confidence threshold
- calibrated Mahalanobis embedding-distance rejection
- crop-family validation
- low-confidence handling
- invalid-image handling

The same service powers:
- `/api/v1/ai/plant-vision/scan`
- `/api/v1/ai/plant-vision/crops/{crop_id}/detect`
- `/predict-disease`

## Scan feature

The existing Quick Scan feature was preserved and updated for V2.

V2 Scan currently offers:
- Corn
- Potato

Rice, Wheat and Sugarcane are intentionally unavailable because V2 has not yet been trained/evaluated for those classes.

Crop-linked Plant Vision also avoids generating unsupported predictions for those deferred crops.

## Existing application functionality

The existing farms, fields, crops, risk engine, recommendation engine, weather,
Copilot, authentication/ownership and visual/UI work were preserved.

No original project files were removed during the merge.

## V2 artifacts added

The merge includes the V2:
- trained model
- metadata
- training configuration/history
- dataset manifest
- leakage report
- internal evaluation report
- OOD report
- Mahalanobis fit
- training/evaluation/OOD scripts
- canonical inference wrapper
- V2 tests
- V2 documentation

## Verification performed

- Python source compilation: PASS.
- JSON parsing: PASS.
- Keras archive integrity: PASS.
- Keras config inspection: final Dense layers `[128, 7]`.
- Mahalanobis fit shapes: class means `(7, 128)`, inverse covariance `(128, 128)`.
- V2 artifact and active production model SHA-256: MATCH.
- Original V1 backup SHA-256 preserved.
- No `.env`, `node_modules`, `.next`, `.venv`, or Python cache artifacts included.
- Original project files: none removed.
- V2 model was not retrained during this merge.

### Runtime test limitation

The merge environment does not contain the project's PostgreSQL Python driver/TensorFlow runtime, so the full backend pytest suite and live TensorFlow inference were not re-executed in this packaging environment.

The supplied V2 package already contained its reported training/evaluation results and 17 passing V2 pipeline tests. Static/source/artifact validation was performed during this merge.

## Important model limitation

V2-alpha is an integrated alpha model, not a claim of field-validated diagnosis.

Measured internal test:
- Overall: 92.11%
- PlantVillage-style subset: 95.13%
- PlantDoc real-world subset: 63.49%

Measured OOD:
- Real off-taxonomy plant set: 26.67% rejected by the combined rule
- Synthetic non-plant/noise: 89% rejected

Rice/Wheat/Sugarcane remain deferred.
