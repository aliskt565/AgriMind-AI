> **UPDATE 2026-10-04:** the CNN described below (v2-alpha / V1) has been replaced by `agrimind_plant_disease_v3-field-research` and the V1/v2-alpha/r2 model files were deleted. See `DOCUMENTATION.md` and `CHANGES_2026_10_04.md`. The text below is historical.

# Next Steps

This reflects the CURRENT repository state, not an old roadmap. The previous version of this
file described Farm Edit UI, initial-crop-selection UI, and the visual/motion overhaul as
upcoming work -- the visual overhaul is now **done** (see `docs/PROJECT_STATE.json`); the other
two are still genuinely missing. The ML/CNN track is new since that version was written.

## Two independent tracks

Frontend product-completeness work (below) and the experimental CNN validation work are
unrelated to each other and can proceed in either order or in parallel -- neither blocks
the other.

## Track C: V2 plant disease model — ALPHA TRAINED AND INTEGRATED

As of 2026-09-21, the V2-alpha model was actually trained and evaluated. It is now
integrated into the existing Plant Vision and Quick Scan flows for its current
7-class Corn/Potato taxonomy. See `docs/ml_v2_training_report.md`,
`docs/ml_v2_evaluation_report.md`, `docs/ml_v2_ood_report.md`, and
`docs/ml_v2_model_card.md`.

### C1. Current scope: Corn + Potato only
V2 currently covers:
- Corn Common Rust
- Corn Gray Leaf Spot
- Corn Healthy
- Corn Northern Leaf Blight
- Potato Early Blight
- Potato Healthy
- Potato Late Blight

Rice, Wheat, and Sugarcane remain explicitly deferred because their verified source
archives were not reachable in the training environment. The product now rejects those
crops for V2 Plant Vision instead of generating unsupported predictions.

### C2. Real-world generalization remains the main model limitation
V2's own held-out test measured 95.13% accuracy on PlantVillage-style images versus
63.49% on the PlantDoc real-world subset. The lab-to-field gap therefore remains
unresolved. This is the highest-priority ML improvement area before expanding the
taxonomy further.

### C3. OOD rejection remains limited
The calibrated combined confidence + Mahalanobis rule rejected 26.67% of the measured
real off-taxonomy plant OOD set and 89% of the synthetic non-plant/noise set. The rule is
implemented as a safety/rejection mechanism, not as proof of reliable unknown-disease
detection.

### C4. V1 is archived, not used for new training
The original V1 binary is preserved at
`ml/evaluation_archive/v1_legacy/agrimind_plant_disease_model_v1_legacy.keras`.
The production model path now contains the V2 binary. No further V1 Colab retraining is
planned unless a future controlled comparison specifically requires it.

### C5. Next ML work
1. Acquire the verified Rice/Wheat/Sugarcane datasets from an environment where their
   source hosts are reachable, or upload the verified archives directly.
2. Extend the V2 taxonomy without changing the existing measured classes silently.
3. Add more real field-phone imagery and evaluate the lab-to-field gap explicitly.
4. Re-run controlled V1-vs-V2 comparisons only when identical source images are available.
5. Do not interpret current V2 outputs as confirmed agricultural diagnoses.

## Track A: Remaining product gaps

### A1. Farm Edit frontend UI
Backend (`PATCH /farms/{farm_id}`) already exists and is tested. Build an Edit affordance on
each farm card in `apps/web/src/app/farms/page.tsx` — a form that pre-fills from the farm's
current values, calls `PATCH /farms/{id}` on save, and refreshes the list. Avoid nesting an
interactive edit button inside the card's `<Link>`.

### A2. Field crop-selection frontend UI
Also backend-complete and tested (`initial_crop_types` on `FieldCreate`, `crops: []` on
`FieldPublic`). In the field-creation form (`apps/web/src/app/farms/[farmId]/page.tsx`), add a
multi-select for crop types plus a custom-crop text input, feeding `initial_crop_types: string[]`
into `POST /farms/{farm_id}/fields`.

### A3. Tests + regression
Add frontend tests for A1/A2, then run the full regression (backend pytest, frontend jest,
`tsc --noEmit`, ESLint, `next build`) together.

---

## Track B: Experimental CNN (`/predict-disease`) — validation, not integration

**Retraining remains NOT justified by current evidence.** This holds after the 2026-09-18 expanded
evaluation (13,324 + 2,265 + 250 + 46 + 110 images — see `docs/ml_evaluation_report.md`'s
"2026-09-18 update" section and `docs/ml_evaluation_expanded_2026_09.json`), which now covers far
more than the original 7 classes on real, matched-taxonomy data (Corn 93.7%, Potato 97.6%, Wheat
86.8%, Rice 79.2%, generic Sugarcane-adjacent classes 53.3% on the 13,324-image test) plus two
genuine out-of-distribution datasets and one small real-world (non-lab-photo) test. The unknown-
overlap question about the *original* training run is still not resolved by any of this new data,
and retraining still would not resolve it either. **V2 is planned work only and has not been
started** — see the V2 section of `docs/PROJECT_STATE.json` and `docs/ml_evaluation_report.md`.

### B1. Documentation/source hygiene
Done for the original 280-image evaluation as of the prior snapshot, and **now extended** to cover
the much larger 2026-09-18 evaluation — see `docs/PROJECT_STATE.json`
(`features.experimental_cnn_endpoint.expanded_evaluation_2026_09_18`),
`docs/ml_evaluation_report.md`, and `docs/ml_evaluation_expanded_2026_09.json` for the current,
consolidated state. Note: the 250-image PlantVillage result (96.0%) in the new evaluation is a
**separate run** from the original 280-image result (92.86%) — same 7-class scope, different
sample, both valid, neither supersedes the other.

### B2. Decide the validation strategy going forward
Two honest options, not mutually exclusive, updated in light of the new evidence:
- Accept the now-larger body of evidence (matched-taxonomy accuracy across 5 crops, plus two OOD
  tests and one small real-world test) and scope any future integration accordingly — with Rice
  and the generic Sugarcane-adjacent classes flagged as materially weaker, and with the overlap
  caveat still disclosed for every figure.
- Treat this as a stronger, but still not held-out, pass, and continue toward B3 for the crops/
  classes still underserved (Sugarcane real disease taxonomy in particular — see E in the
  2026-09-18 evaluation update — remains almost entirely unsupported).

### B3. Obtain genuinely independent real-world/field photos
Still the only way to get a *provably* unseen evaluation. The 2026-09-18 update's SAGE real-world
test (46 images, 56.52% accuracy — Corn 12/25, Potato 13/15, Rice 1/6) is a first, small step in
this direction and is not lab-style PlantVillage imagery, but it is far too small to be conclusive
and does not resolve the overlap question for the *other* evaluation sets. Real Sugarcane disease
coverage (Yellow Spot, Grassy Shoot, Sett Rot, Pokkah Boeng, Sugarcane Mosaic Virus, and others —
see the SAGE Sugarcane OOD test) remains a genuine gap: the model's only sugarcane-adjacent
classes (generic Healthy/Bacterial Blight/Red Rot) do not cover these, and 45% of that 110-image
OOD test still passed the confidence gate anyway.

### B4. Only after sufficient validation, consider scoped integration
Not before B2/B3. If/when pursued: wire through the existing `PlantVisionProvider`/factory
abstraction (not a standalone route), add authentication, add persistence, and keep the mock
provider as the default/fallback — do not replace it outright.

### B5. Retraining
Remains not justified, including after the expanded evaluation. Revisit only if further
real-world data (B3) produces evidence that specific classes are genuinely underperforming on
real-world data, or once a genuine OOD/unknown-detection approach is designed (the green-pixel
filter and 68% confidence threshold are now confirmed, via two independent real off-taxonomy
datasets, not to reliably catch unsupported input).

---

## Process note

Every fix in this project's history was found and confirmed via a failing test, a live
reproduction against real PostgreSQL, or (for the visual work) an actual rendered screenshot —
not assumption. Every ML claim above is backed by an actually-executed evaluation, not
estimation. Continuing that discipline matters more than the specific ordering above.
