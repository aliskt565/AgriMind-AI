> **UPDATE 2026-10-04:** the CNN described below (v2-alpha / V1) has been replaced by `agrimind_plant_disease_v3-field-research` and the V1/v2-alpha/r2 model files were deleted. See `DOCUMENTATION.md` and `CHANGES_2026_10_04.md`. The text below is historical.

> **Superseded by 2026-09-25 merge:** This release-status document describes the prior V1-model package. The current active model is V2-alpha; see `docs/ml_v2_model_card.md` and `docs/PROJECT_STATE.json`.\n\n# AgriMind AI — Merged Release Status

## Release purpose
This release merges the previous `AgriMind-AI-ML-Master` package with the later `AgriMind-AI` package while preserving the Master package as the baseline for existing platform functionality and regression fixes.

## Plant Vision architecture
The merged release has one canonical Plant Vision inference path: `apps/api/app/services/plant_vision_cnn.py`. Both the standalone Quick Scan and the Field/Crop Plant Vision flow use this service. The legacy `/predict-disease` endpoint delegates to the same service so preprocessing and model behavior cannot diverge.

## Model decision
The supplied newer ZIP contained a `.keras` artifact whose SHA-256 matched the Master artifact exactly (`c8fe7a2e4fdb165c112e41683e0c5891cea1ed8fad33ccdae8d0bd44054149ba`). Because the two artifacts are byte-identical, the release does not run two copies of the same model. One canonical model is used everywhere.

## New functionality merged
- Standalone authenticated `/scan` UI.
- Crop selection before Quick Scan.
- CNN-backed crop-family mismatch detection.
- Crop-specific CNN detection inside Field/Crop Plant Vision.
- Disease detection persistence.
- Health-status escalation after confirmed disease.
- Risk-engine refresh and recommendation refresh after confirmed disease.
- Farm Edit UI.
- Field Edit UI.
- Initial crop selection when creating a field.

## Engineering improvements
- Removed eager TensorFlow/Keras loading from `app.main`; model loading remains lazy and cached.
- Removed duplicated CNN preprocessing from `/predict-disease`; all inference uses the shared service.
- Preserved Master security and regression fixes.
- Preserved Master ML/evaluation documents as historical evidence.
- Added focused CNN service tests for preprocessing/gating behavior using an injected fake model.
- Excluded `.env`, `venv`, `.venv`, `node_modules`, `.next`, caches and bytecode from the release package.

## Verification performed during merge
- Python source compilation: PASS.
- Frontend TypeScript (`tsc --noEmit`): PASS.
- Frontend ESLint: PASS.
- Next.js production build could not be completed in the isolated build environment because the required Linux SWC binary was not cached and the environment could not reach npm to download it. This is an environment limitation, not a reported application compilation error.
- Full backend pytest suite could not run in the isolated environment because its PostgreSQL driver/database environment was unavailable there. The user's Windows setup already contains PostgreSQL 16.15 and the required Python dependencies.

## AI limitation
The checked-in CNN remains a screening model. Historical evaluation reports document accuracy and OOD limitations and state that original training-data provenance/held-out separation could not be proven. The UI/API therefore describe predictions as AI-generated screening results rather than confirmed diagnoses.
