# AgriMind AI — Complete Project Documentation
*AI-Based Smart Agriculture Advisory System — release of 2026-10-04*

## 1. What the project is
AgriMind AI is a full-stack smart-agriculture platform. Farmers register, create farms, fields and crops, log activities, see a dashboard with weather, risk and recommendations, scan leaf photos with a CNN (Plant Vision), and chat with a farm copilot.

## 2. Architecture
| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, Pydantic, JWT auth, Pytest |
| Frontend | Next.js 16, React, TypeScript, Tailwind CSS, Jest, React Testing Library |
| CNN | Keras 3.15.1, TensorFlow CPU 2.21.0, MobileNetV2, Pillow, NumPy |

```
AgriMind-AI/
├── apps/api/      FastAPI backend (routers in app/api/v1/endpoints, services, AI providers, models/ = the CNN)
├── apps/web/      Next.js frontend (dashboard, farms, fields, crops, scan, copilot)
├── ml/            training, evaluation, OOD, inference code, reports, experiments
├── docs/          historical reports (see banner at top of each; older ones describe replaced models)
├── DOCUMENTATION.md   this file        CHANGES_2026_10_04.md   what changed in this release
└── README.md      step-by-step setup (Windows/PowerShell)
```
Routers: auth, farms, fields, crops, dashboard, ai_crop_intelligence, ai_plant_vision, weather, risk, recommendations, copilot (see `apps/api/app/api/v1/router.py`). Interactive API docs at `/docs` when the backend runs.

## 3. Features and which parts are real vs mock
| Feature | Status |
|---|---|
| Auth, farms, fields, crops, activities, dashboard, risk engine, recommendation engine | Implemented |
| **Plant Vision / Quick Scan** | **Real CNN** (`plant_vision_cnn.py`) — Corn and Potato only |
| AI Crop Advisor, Weather Intelligence, AgriMind Copilot | **Mock providers** (provider factory ready for real ones) |
| Rice, Wheat, Sugarcane disease detection | Not available — rejected as unsupported crops |

## 4. The CNN in this release (one model only)
**Only one CNN model exists in the project now.** It sits at `apps/api/models/agrimind_plant_disease_model.keras` (identical copy at `ml/artifacts/agrimind_plant_disease_v2.keras`). Version string: `agrimind_plant_disease_v3-field-research`.

- Architecture: MobileNetV2 (ImageNet) → GlobalAveragePooling → Dense(128) → Dropout(0.3) → Dense(7, softmax). Input 224×224 RGB, `mobilenet_v2.preprocess_input`.
- Classes (7): Corn Common Rust, Corn Gray Leaf Spot, Corn Healthy, Corn Northern Leaf Blight, Potato Early Blight, Potato Healthy, Potato Late Blight.
- It was chosen because it scored highest on field photos among the three models compared (table below).
- Training data: PlantVillage (lab, CC BY-SA 3.0), PlantDoc (field, CC BY 4.0), and the gitergo "Natural_environment" corn field set (**no license stated**). Train/val/test were split by near-duplicate group so copies of one photo never straddle splits.

### 4.1 Three-model comparison (same test images, scored once)
| Model | Lab (PlantVillage, n=542) | PlantDoc field (n=57) | gitergo field (n=297) | All field (n=354) |
|---|---|---|---|---|
| v2-alpha (was in the app) | 95.2% | 73.7% | 36.7% | 42.7% |
| Model A (license-clean, new) | 89.1% | 66.7% | 50.5% | 53.1% |
| **Model B (new) — NOW IN THE APP** | 95.6% | 70.2% | 91.9% | 88.4% |

Notes: v2-alpha was trained on an earlier split of PlantVillage/PlantDoc, so some of these test images may have been seen by it — its numbers are, if anything, flattering. PlantDoc has only 57 test images, so differences of a few points there (v2-alpha 73.7% vs model B 70.2%) are within noise. Model B's 91.9% on gitergo comes from training on that set; Model A never saw it (50.5%) and shows what a model without that data does on unfamiliar field photos.

### 4.2 What the numbers do and do not show
- Combined field accuracy is 88.4% (95% range ≈ 84.7–91.4%), but 297 of the 354 field images come from one corn source similar to the training photos.
- On the mixed-source PlantDoc test (the better proxy for random farmer photos) model B scored 70.2% (95% range 57–80%). **An 80%+ accuracy on arbitrary real farmer photos is NOT demonstrated.**
- Weak classes: Corn Gray Leaf Spot (5/9 on gitergo, 4/6 on PlantDoc) and Potato Late Blight (4/10 on PlantDoc); test counts are tiny.
- Potato has no field-photo test beyond PlantDoc's ~10 images per class.
- Never tested on photos from your own farmers.

### 4.3 Unknown-image rejection (refit for this model)
- Confidence threshold: **0.4271**; embedding-distance threshold: **183.81** (both calibrated on the validation split only).
- In-distribution test images rejected: 7.0%.
- Other-crop plant images (Tomato/Apple/Grape) rejected: only 27.3% — **the model will often give a Corn/Potato answer for an unrelated crop leaf**; the crop selector in the UI is the real guard.
- Synthetic noise / non-plant images rejected: 100%.
Reports: `ml/reports/v2_ood_report.json`; the Mahalanobis fit is `ml/artifacts/ood_mahalanobis_fit.npz`. Both were refit for this model; the old ones belonged to v2-alpha (old report kept as `ml/reports/v2_alpha_ood_report_superseded.json`).

### 4.4 How a scan works
1. Client uploads a photo with the selected crop (Quick Scan: `POST /api/v1/ai/plant-vision/scan`; crop page: `POST /api/v1/ai/plant-vision/crops/{crop_id}/detect`).
2. `plant_vision_cnn.py` validates the image *before* loading TensorFlow, rejects unsupported crops, runs the model, and rejects the image if confidence < 0.4271 **or** embedding distance > 183.81.
3. Otherwise it returns the class, confidence (HIGH ≥ 80%, else LOW), top-3, and a crop-mismatch warning if the predicted class belongs to a different crop than selected.
4. The crop-linked route also saves the result and refreshes crop health, risk and recommendations.
The result is a screening aid, not a confirmed diagnosis.

## 5. Run it
Follow `README.md` (Node 22, Python 3.12, PostgreSQL 16): create the `agrimind_dev` and `agrimind_test` databases, copy `.env.example` to `.env`, `alembic upgrade head`, `uvicorn app.main:app --reload --port 8000`, then `npm install && npm run dev` in `apps/web`. Backend tests: `pytest` in `apps/api`. Frontend tests: `npm run test`.
**Verified for this release:** the CNN service was loaded and run on 12 real field images (12/12 correct, all accepted), rejected random noise and corrupt files, rejected Rice as unsupported, with OOD enabled; the `ml/tests` suite passes (15 passed, 2 skipped). **Not re-run:** the full backend (needs PostgreSQL) and frontend suites — please run them before release.

## 6. Retraining / reproducing
Scripts: `ml/experiments/field_robust_v3/scripts/{prep.py,hashes.py,train.py}` (paths are hard-coded to `/home/claude/...`; edit them). Data are not included; re-download PlantVillage, PlantDoc and gitergo from GitHub. `MODEL_CARD.md` in that folder lists the exact recipe. Reports for the two new models: `modelA_license_clean/` and `modelB_research_gitergo/` (the model files themselves were deleted as requested; model B is the one in `apps/api/models/`).

## 7. Known limitations and risks
1. **Licensing:** the model was trained on unlicensed gitergo images. Do not release commercially until that is resolved (or retrain without it — model A's recipe shows the cost: field accuracy falls to ~53%). PlantVillage is CC BY-SA 3.0: get legal review for model weights. Attribution to PlantDoc (CC BY 4.0) and PlantVillage is required.
2. Only Corn and Potato are covered.
3. The model often gives a Corn/Potato answer for other crops' leaves (only ~27% rejected) — rely on the crop selector.
4. Accuracy on varied real farmer photos is about 70% on the available test, not 80%+.
5. AI Crop Advisor, Weather and Copilot are mocks.
6. Docs in `docs/` written before 2026-10-04 describe the replaced v2-alpha/V1 models; each carries an update banner.

## 8. How to reach 80%+ on real farmer photos
Collect a few hundred labeled phone photos per class from your region (more for Gray Leaf Spot, Potato Late Blight and the healthy classes), hold out ~20% split by plant/field as the only test set that counts, add them to `prep.py`, retrain with `train.py`, and refit the rejection thresholds.
