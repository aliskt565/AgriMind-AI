# AgriMind AI — Master Working Package

This package contains the full AgriMind AI application plus the integrated V2 plant
disease ML pipeline and its evidence/documentation.

## Included

- Full AgriMind-AI backend and frontend source
- V3 field-robust MobileNetV2 plant disease model (the only CNN model; older ones deleted)
- V2 training/evaluation/OOD artifacts and reports
- V2 inference pipeline and tests
- Existing ML evaluation archive
- Original V1 model preserved as a legacy reference
- Quick Scan feature using the same V2 Plant Vision service
- Crop-linked Plant Vision using the V2 model
- Existing farms/fields/crops/risk/recommendation functionality
- V2 dataset licensing/provenance documentation

## Current Plant Vision scope

V2 currently supports seven classes across:
- Corn
- Potato

Rice, Wheat and Sugarcane are intentionally deferred until their V2 datasets are
acquired and evaluated. The UI and API reject unsupported crops rather than producing
predictions outside the trained taxonomy.

## Important

The current model is a research build with documented limitations: 70.2% on the mixed PlantDoc field test (n=57) and 91.9% on a single corn field set it was trained on; trained partly on unlicensed data. See DOCUMENTATION.md.

The original V1 and other superseded models were deleted on 2026-10-04.

The active production model path:
`apps/api/models/agrimind_plant_disease_model.keras`
contains the V2 model.

Commercial release requires separate review of the applicable dataset/model licensing
terms; technical integration does not constitute legal clearance.
