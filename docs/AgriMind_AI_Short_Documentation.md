> **UPDATE 2026-10-04:** the CNN described below (v2-alpha / V1) has been replaced by `agrimind_plant_disease_v3-field-research` and the V1/v2-alpha/r2 model files were deleted. See `DOCUMENTATION.md` and `CHANGES_2026_10_04.md`. The text below is historical.

> **Current-state notice (2026-09-25):** This document contains historical V1 evaluation details. The active Plant Vision model is now V2-alpha (7 Corn/Potato classes), integrated through `apps/api/app/services/plant_vision_cnn.py`. See `ml_v2_model_card.md` and `ml_v2_evaluation_report.md` for current V2 status.\n\n# AgriMind AI — Short Project Documentation

**Formal Title:** AI-Based Smart Agriculture Advisory System  
**Project:** AgriMind AI — AI-Powered Smart Agriculture & Farm Intelligence Platform

## 1. Project Overview

AgriMind AI is a full-stack smart agriculture platform designed to help farmers manage farms, fields and crops and receive agriculture-related intelligence through a web application.

The system contains:

- User authentication and role/ownership controls
- Farm, field, crop and activity management
- Dashboard and farm information
- Weather Intelligence
- AI Crop Advisor
- Plant Vision
- Farm Risk Engine
- Recommendation Engine
- AgriMind Copilot

The platform uses a **FastAPI + PostgreSQL** backend and a **Next.js + React + TypeScript** frontend.

## 2. Technology Stack

### Backend
- Python 3.12
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL 16
- Pydantic
- JWT-based authentication
- Pytest

### Frontend
- Next.js 16
- React
- TypeScript
- Tailwind CSS
- Jest
- React Testing Library

### ML / Experimental Plant Disease Model
- Keras 3.15.1
- TensorFlow CPU 2.21.0
- MobileNetV2
- V2-alpha 7-class softmax classifier (Corn + Potato)
- Pillow / NumPy

## 3. Current System Status

The core application is implemented and verified.

- **Backend:** 136 tests passing
- **Frontend:** 51 tests passing
- **TypeScript:** PASS
- **ESLint:** PASS
- **Production build:** PASS
- **Database migrations:** configured with a single current Alembic head
- Authentication, authorization/ownership and major farm-management features are implemented.
- The visual/motion design overhaul is implemented and visually verified.

Two small frontend gaps remain:
1. Farm Edit UI
2. Initial crop-selection UI when creating a field

Their backend support already exists and is tested.

## 4. AI Feature Status

The product AI features currently use explicitly labeled mock providers:

| Feature | Current Status |
|---|---|
| AI Crop Advisor | Mock |
| Plant Vision | V2-alpha CNN for Corn/Potato |
| Weather Intelligence | Mock |
| AgriMind Copilot | Mock |

The project uses provider/factory abstractions so real providers can be added later without redesigning the whole application.

## 5. Plant Disease CNN — V1 (Historical)

A separate experimental CNN exists at:

`apps/api/models/agrimind_plant_disease_model.keras`

It uses MobileNetV2 with an 18-class output.

The model is exposed through:

`POST /predict-disease`

This endpoint is **not connected to the product Plant Vision feature**. The current frontend uses the integrated V2 CNN Plant Vision service for supported Corn/Potato crops.

The CNN is therefore experimental and is **not production-ready or a verified diagnostic system**.

## 6. V1 Evaluation Results (Historical)

The same unchanged V1 model was evaluated using several datasets.

### 13,324-image matched-taxonomy evaluation
- Accuracy: **87.45%**
- Macro F1: **0.82**
- Weighted F1: **0.87**
- Corn: **93.7%**
- Potato: **97.6%**
- Wheat: **86.8%**
- Rice: **79.2%**
- Generic Sugarcane-adjacent classes: **53.3%**

### PlantVillage evaluation
A separate 250-image run achieved **96.0% accuracy** on the same 7-class scope as the original evaluation.

The earlier 280-image evaluation achieved **92.86% accuracy**.

These figures are separate evaluations and should not be treated as replacements for one another.

### Real-world SAGE evaluation
- 46 usable images
- **26/46 = 56.52% accuracy**
- Corn: 12/25
- Potato: 13/15
- Rice: 1/6

This provides directional evidence that performance drops on more varied real-world imagery.

### OOD / unsupported-input evaluation
Two important OOD tests showed that the current confidence threshold is not a reliable unknown-class detector:

- 2,265 off-taxonomy images produced confident predictions instead of rejection.
- In the 110-image real Sugarcane OOD set, **45%** still exceeded the existing 68% confidence threshold.

Therefore, confidence should not be treated as a calibrated probability of correctness.

## 7. Important ML Limitation

The original training dataset, training script and original class-index mapping of V1 could not be recovered.

Because of this, the evaluation datasets **cannot be proven to be completely unseen/held-out** from the original training data.

Therefore, the reported V1 metrics are valid measurements on the tested datasets, but they should **not** be presented as proven held-out generalization results.

## 8. V2 Dataset / Licensing Status

A separate licensing and provenance review was completed.

### Training-eligible sources identified
- Wheat Disease Dataset — Small (Zenodo)
- Rice Leaf Disease Image Samples — Sethy et al. (Mendeley)
- Sugarcane Plant Diseases Dataset — CDLA-Sharing-1.0

Previously confirmed compatible sources also include selected CC BY 4.0 / CC0 datasets such as PlantDoc and specific original Rice/Sugarcane sources.

### Not suitable for commercial training under the currently established terms
- Five Crop Diseases Dataset — **CC BY-NC-SA 4.0**
- WheatRust21 — license/provenance unresolved

Some other datasets remain verification-required rather than automatically approved.

The licensing review recommends using authoritative original sources instead of ambiguous mirrors where possible.

## 9. V2 Status

**V2 has not been trained yet.**

The planned V2 direction is:

1. Reproducible dataset manifest and provenance tracking
2. Explicit canonical taxonomy
3. SHA-256 and perceptual duplicate detection
4. Leakage-safe source-aware train/validation/test split
5. Shared training/inference preprocessing
6. MobileNetV2 transfer learning with staged fine-tuning
7. Proper held-out and source-separated evaluation
8. Real-world field-image evaluation
9. OOD / unknown-class rejection
10. Model metadata, versioning and reproducible documentation

## 10. Final Current Status

**AgriMind AI application:** Core platform implemented and tested.  
**Product AI:** Most external AI/LLM/weather providers remain mock by design.  
**Plant Vision:** V2-alpha CNN integrated for Corn/Potato; Rice/Wheat/Sugarcane are deferred.  
**V2 disease model:** Planned, not yet implemented.  
**Remaining immediate product work:** Farm Edit UI, initial crop-selection UI, followed by final regression testing and release documentation.

---

**Documentation basis:** repository snapshot, ML evaluation package, V2 dataset licensing/provenance report, and project-state/next-step documents supplied for review.
