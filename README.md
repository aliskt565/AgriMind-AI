# AgriMind AI

**AI-Powered Smart Agriculture & Farm Intelligence Platform**
*(Formal academic title: AI-Based Smart Agriculture Advisory System)*

This is the full source for AgriMind AI: a FastAPI + PostgreSQL backend and a Next.js/TypeScript frontend, including the AI Crop Advisor, **real CNN-backed Plant Vision**, Weather Intelligence, Farm Risk Engine, Recommendation Engine, and AgriMind Copilot. The merged release keeps mock providers for features that are intentionally not yet connected to external/real AI services, while Plant Vision now uses the checked-in MobileNetV2 CNN.

```
agri-mind-ai/
├── apps/
│   ├── api/     FastAPI backend
│   └── web/     Next.js frontend
├── packages/    (reserved for future shared code)
├── infrastructure/
├── docs/
└── tests/
```

---

## 1. Prerequisites (versions this project was built and tested against)

| Tool | Version used | Notes |
|---|---|---|
| Node.js | **v22.x** | `node -v` |
| npm | **v10.x** | ships with Node 22 |
| Python | **3.12.x** | `python --version` |
| PostgreSQL | **16.x** | must be installed and running locally |

Windows: install Node.js and Python from their official installers (check "Add to PATH" during Python install), and PostgreSQL from https://www.postgresql.org/download/windows/ (the installer includes `psql` and lets you set the `postgres` superuser password — **set it to `postgres`** to match this project's default local config, or see step 6 below to use a different password).

---

## 2. Clone/extract and open in VS Code

Extract this archive, then open the `agri-mind-ai` folder in VS Code. Open **two terminals** inside VS Code (Terminal → New Terminal) — one for the backend, one for the frontend.

---

## 3. Backend setup (PowerShell)

```powershell
cd apps\api

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install exact dependency versions this project was built against
pip install -r requirements.txt
```

If PowerShell blocks the activation script, run this once as Administrator: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

**Note:** `requirements.txt` includes `tensorflow-cpu`/`keras`/`numpy`/`pillow`, required by the integrated Plant Vision CNN and the backward-compatible `/predict-disease` endpoint. Model loading is lazy, so TensorFlow is initialized only when an inference request is made.

---

## 4. Create the PostgreSQL databases

Open a terminal with `psql` on your PATH (or use "SQL Shell (psql)" from the Start Menu) and run:

```sql
CREATE DATABASE agrimind_dev;
CREATE DATABASE agrimind_test;
```

The dev database is used by the running app; the test database is used only by `pytest`.

---

## 5. Configure environment variables

```powershell
copy .env.example .env
```

Open `.env` and check `DATABASE_URL` matches your local PostgreSQL user/password/port, e.g.:

```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/agrimind_dev
```

Set a real `SECRET_KEY` for anything beyond local development — the example value is a placeholder only. `AI_MODE`, `WEATHER_PROVIDER`, and `COPILOT_PROVIDER` remain mock unless their separate real providers are implemented. Plant Vision does **not** use the mock provider anymore; it uses the checked-in CNN service.

**Note on the test database connection:** `apps/api/app/tests/conftest.py` connects to the test database using a hardcoded connection string (`postgresql+psycopg2://postgres:postgres@localhost:5432/agrimind_test`) rather than reading `.env`, so that test runs are never accidentally pointed at a real dev/prod database. If your local PostgreSQL `postgres` user has a different password, either set it to `postgres` for local dev, or edit `TEST_DATABASE_URL` near the top of that file.

---

## 6. Run database migrations

```powershell
cd apps\api
.venv\Scripts\Activate.ps1
alembic upgrade head
```

This creates all application tables (users, farms, fields, crops, activities, AI predictions, risks, recommendations, notifications, weather snapshots, timeline events, audit logs, Copilot conversations/messages) in `agrimind_dev`.

---

## 7. Start the backend

```powershell
cd apps\api
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

- API base URL: **http://localhost:8000/api/v1**
- Health check: **http://localhost:8000/health**
- Interactive API docs: **http://localhost:8000/docs**

---

## 8. Frontend setup

In your second terminal:

```powershell
cd apps\web
npm install
copy .env.example .env.local
```

`.env.local` should point at the backend:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## 9. Start the frontend

```powershell
npm run dev
```

- App URL: **http://localhost:3000**

With both the backend (step 7) and frontend running, open http://localhost:3000, register a farmer account, and use the app.

---

## 10. Running tests

**Backend** (from `apps/api`, venv activated, `agrimind_test` database created per step 4):
```powershell
pytest
```
Run the full backend suite after installing `requirements.txt`; the release also includes focused CNN-service tests that exercise preprocessing, confidence gating and crop-mismatch logic.

**Frontend** (from `apps/web`):
```powershell
npm run test
```
Expected: 51 tests pass.

---

## 11. Production build (frontend)

```powershell
cd apps\web
npm run build
```

## 12. Quality checks

```powershell
cd apps\web
npm run lint          # ESLint
npx tsc --noEmit       # TypeScript
```

---

## AI Provider Status — READ THIS

| Capability | Current provider | Notes |
|---|---|---|
| AI Crop Advisor | Mock | Provider abstraction retained for future real integration |
| **Plant Vision / Crop Scan** | **Real MobileNetV2 CNN** | Shared service powers both `/scan` and crop-specific detection |
| Weather Intelligence | Mock | Separate provider flag |
| AgriMind Copilot | Mock | Separate provider flag |

### Plant Vision architecture

`Quick Scan → POST /api/v1/ai/plant-vision/scan → shared CNN service`

`Field/Crop Plant Vision → POST /api/v1/ai/plant-vision/crops/{crop_id}/detect → same shared CNN service → persistence → health/risk/recommendation side effects`

The shared service lives at `apps/api/app/services/plant_vision_cnn.py` and is the single source of truth for image validation, MobileNetV2 preprocessing, model loading, confidence gating, class mapping and crop-family mismatch detection. The standalone `/predict-disease` endpoint remains as a backward-compatible direct API and now delegates to that same service instead of maintaining a second inference implementation.

The checked-in model at `apps/api/models/agrimind_plant_disease_model.keras` is the V3 field-robust 7-class MobileNetV2 artifact (`agrimind_plant_disease_v3-field-research`, see `DOCUMENTATION.md`). The canonical V2 copy is also preserved at `ml/artifacts/agrimind_plant_disease_v2.keras`; the two binaries are SHA-256 identical.

### Scan capabilities

- Standalone authenticated Quick Scan with explicit crop selection
- Crop/Field Plant Vision using the same CNN
- Crop-family mismatch warning
- Healthy vs disease classification
- Calibrated confidence + Mahalanobis OOD rejection (refit for the V3 model)
- Low-confidence, out-of-distribution and invalid-image rejection
- Disease detection persistence
- Crop health escalation on confirmed disease
- Risk engine refresh and active recommendation refresh after confirmed disease
- Scan result model/version metadata

The CNN remains an **AI screening tool, not a confirmed agricultural diagnosis**. Existing evaluation documents remain historical evidence and should not be presented as proof of production-grade generalization.

## Current Status

- **Backend:** FastAPI + PostgreSQL + SQLAlchemy + Alembic with the existing security/ownership regression coverage preserved.
- **Frontend:** Next.js 16 + React + TypeScript with the premium visual/motion system preserved.
- **Plant Vision:** real shared MobileNetV2 CNN integrated into both standalone Scan and crop-specific Field/Crop Plant Vision.
- **Scan:** standalone `/scan` page plus crop-specific scanning inside crop detail pages.
- **Farm/Field UX:** Farm Edit, Field Edit, and initial crop selection during field creation are included in the merged release.
- **AI Crop Advisor / Weather / Copilot:** remain explicitly mocked where no real provider was supplied.
- **Backward compatibility:** `/predict-disease` still exists and delegates to the shared CNN service.
- **Release hygiene:** local `.env`, virtual environments, `node_modules`, `.next`, caches and generated bytecode are excluded from the release archive.
- **Historical ML evidence:** retained under `docs/` without rewriting old evaluation results as current guarantees.

## Troubleshooting

- **`alembic upgrade head` fails with a connection error:** confirm PostgreSQL is running and `DATABASE_URL` in `.env` matches your local credentials/port.
- **`pytest` fails to connect to `agrimind_test`:** confirm that database exists (step 4) and your local `postgres` user password matches what's hardcoded in `conftest.py` (see step 5 note).
- **Frontend can't reach the API:** confirm the backend is running on port 8000 and `NEXT_PUBLIC_API_URL` in `apps/web/.env.local` is correct, then restart `npm run dev` (Next.js only reads env files at startup).
- **PowerShell won't run `Activate.ps1`:** see the execution-policy note in step 3.
