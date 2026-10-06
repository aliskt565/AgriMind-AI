# AgriMind AI V2 — Dataset License & Provenance Verification

**Date:** 2026-09-19
**Scope:** Strict commercial-training-eligibility verification of every dataset flagged "B / needs verification" in the V2 research/design report, plus a dedicated re-check of the Five Crop Diseases Dataset (already used for V1 evaluation). No datasets were downloaded, no code or model files were changed, and no training was performed to produce this document.
**Companion file:** `docs/ml_v2_dataset_license_verification_2026_09.json` — structured, per-dataset records with full evidence citations.

Every conclusion below is tagged **CONFIRMED**, **INFERRED**, or **UNRESOLVED**:
- **CONFIRMED** — verified directly against the dataset's own authoritative page (license field, JSON-LD metadata, or explicit license text).
- **INFERRED** — strong circumstantial evidence supports the conclusion, but it was not independently confirmed at the exact byte/file level, or comes from a secondary source quoting the primary one.
- **UNRESOLVED** — could not be established this session; treated as a blocker, not a guess.

---

## 1. Potato Disease Leaf Dataset (PLD)

- **Kaggle:** https://www.kaggle.com/datasets/rizwan123456789/potato-disease-leaf-datasetpld
- **License (CONFIRMED):** "Database: Open Database, Contents: Database Contents" — i.e., the ODC Open Database License (ODbL 1.0) applied to the database, with the ODC Database Contents License (DbCL 1.0) applied to the individual images. Retrieved directly from the dataset's own Kaggle metadata.
- **Commercial use:** Not prohibited — ODbL/DbCL are not non-commercial licenses.
- **Commercial ML training:** **UNRESOLVED at the level of certainty this task requires.** ODbL distinguishes a "Derivative Database" (which must stay under ODbL if redistributed — copyleft) from a "Produced Work" (an output of *using* the database, such as a query result, a visualization, or arguably a trained model), which ODbL's own structure treats more permissively — typically requiring only attribution, not full share-alike. Whether a trained ML model is legally a "Produced Work" under ODbL 1.0 was **not independently confirmed against the primary license text this session**, and this is a genuinely less-common license family than the CC licenses seen elsewhere in this pass.
- **Provenance:** 4,062+ images, genuinely field-collected in Central Punjab, Pakistan — real value for closing V1's lab-to-field gap specifically for Potato.
- **Classification: B.** Do not treat as clear commercial-training-eligible without a specific legal review of ODbL/DbCL's Produced-Works provisions as applied to ML model training.

## 2. Five Crop Diseases Dataset (already used for V1 evaluation)

- **Kaggle:** https://www.kaggle.com/datasets/shubham2703/five-crop-diseases-dataset
- **License (CONFIRMED):** **CC BY-NC-SA 4.0** — directly stated on the dataset's own Kaggle page. This is a **NonCommercial** license.
- **Commercial ML training: NO.** The NC clause explicitly rules this out for a commercial product.
- **Provenance (CONFIRMED it is a compilation, via the dataset's own description text):**
  - Corn, Potato images: sourced from PlantVillage
  - Rice images: sourced from "Dhan-Shomadhan: A Dataset of Rice Leaf Disease Classification for Bangladeshi Local Rice" — the compiler's *own text* states this sub-source "has the license CC BY 4.0"
  - Wheat images: sourced from a "Wheat Disease Detection" dataset on Kaggle (a different dataset from "Wheat Disease Dataset - Small," verified separately below) — sub-source license not independently re-verified this session
  - Sugarcane images (300 total: 100 Red Rot, 100 Healthy, 100 Bacterial Blight): sourced from a "Sugarcane Disease Dataset" on Kaggle — sub-source license not independently re-verified this session
- **A notable finding:** this compilation's exact 300-image, 3-class Sugarcane breakdown (Red Rot/Healthy/Bacterial Blight, 100 each) is very likely **the direct origin of V1's own generic Sugarcane taxonomy** — the same three labels, in the same shape. This traces a real thread from "why does V1's Sugarcane taxonomy look like this" back to this specific compilation's sourcing choices.
- **A licensing inconsistency worth flagging:** the compiler's own text states the Rice sub-source (Dhan-Shomadhan) is independently CC BY 4.0, yet wraps the whole compilation — Rice included — under the more restrictive CC BY-NC-SA 4.0. This is precisely the aggregate-license-vs-source-license mismatch the task asked us to watch for. It does **not** make the compilation safe to train on; if anything, it means the Rice portion specifically might be independently obtainable under its original, more permissive terms — but **directly from Dhan-Shomadhan's own repository, not through this compilation.**
- **Classification: D — remains evaluation-only.** Its own stated license forbids commercial training use of the compilation as distributed. Status is **not** changed to training-eligible.

## 3. Wheat Disease Dataset - Small

- **Kaggle mirror:** https://www.kaggle.com/datasets/yasserhessein/wheat-disease-dataset-small (license tag: ambiguous "Other (specified in description)")
- **Authoritative source (per the task's instruction to check the original, not just the Kaggle mirror):** Zenodo, https://zenodo.org/records/7573133, DOI 10.5281/zenodo.7573133 — published directly by the original authors (Long, Hartley, Morris, Brown; John Innes Centre), underlying Long et al. 2023, *Plant Pathology*, DOI 10.1111/ppa.13684.
- **License (CONFIRMED, directly from the Zenodo record's own "Rights" section):** **Creative Commons Attribution 4.0 International (CC BY 4.0).**
- **Commercial ML training: YES**, with standard attribution.
- **Provenance:** 999 real field + glasshouse images (UK, Ireland, Ethiopia, Tanzania), 5 classes (BrownRust, Healthy, Mildew, Septoria, YellowRust) — a strong match to V1's existing Wheat taxonomy plus two new classes.
- **Caveat:** this 999-image set is stated to be a subset of a larger 19,172-image dataset, available only on direct request from the corresponding author. The larger set's license was **not** independently verified and should not be assumed identical without asking.
- **Classification: A**, for the 999-image Zenodo-hosted subset specifically. **Source from Zenodo, not the ambiguous Kaggle mirror.**

## 4. WheatRust21

- **Cited via:** https://www.sciencedirect.com/science/article/abs/pii/S1574954123000973 ("Deep transfer learning model for disease identification in wheat crop")
- **Original collection:** ICAR-Indian Agricultural Research Institute, New Delhi, and its Madhya Pradesh regional centre, 2019–2021, per the paper's own description.
- **Public repository:** **not located this session.** No Kaggle, Mendeley, Zenodo, or GitHub link for this dataset surfaced in searches.
- **License:** UNRESOLVED — cannot be assessed without a public release to inspect.
- **Classification: C.**
- **"Commercial training eligibility could not be established."** This dataset's existence and description are confirmed by the paper; its public accessibility and license are not. Do not pursue without first locating an authoritative public release or contacting the original authors.

## 5. Kaggle "Wheat Plant Diseases" (kushagra3204)

- **Kaggle:** https://www.kaggle.com/datasets/kushagra3204/wheat-plant-diseases
- **License (CONFIRMED, via a peer-reviewed citing paper's explicit quote — the Kaggle page's own JSON-LD was not independently retrieved this session):** **CC0 (Public Domain Dedication).**
- **Commercial ML training:** YES, if the license holds on direct re-verification (CC0 is maximally permissive — no attribution even required).
- **A provenance inconsistency found:** two independent citing papers describe *different* versions of this dataset — one (PMC, 2026) lists 9 disease-only classes; another (cited in the earlier research report) describes a 15-class, 14,000+ image version that adds pest categories (Aphid, Mite, Stem fly). This could reflect the dataset being expanded over time, or the two papers may describe genuinely different releases.
- **Classification: B**, held pending direct re-verification of the *current* class list and version on Kaggle, and a scope decision on whether pest-damage classes belong in a plant-disease taxonomy at all (same open question flagged for Rice/Hispa in the research report).

## 6. Sethy et al. Rice Leaf Disease Image Samples

- **Authoritative source (found directly, not merely cited):** Mendeley Data, https://data.mendeley.com/datasets/fwcj7stb8r/1, DOI 10.17632/fwcj7stb8r.1, published 2020-07-18 by Prabira Kumar Sethy (Sambalpur University / Bargarh district, Odisha, India), underlying Sethy et al. 2020, *Computers and Electronics in Agriculture* 175, 105527.
- **License (CONFIRMED, directly from Mendeley's own metadata):** **CC BY 4.0.**
- **Commercial ML training:** YES, with attribution.
- **Provenance:** 5,932 real field-collected images, 4 classes (Bacterial Blight, Blast, Brown Spot, Tungro) — multiple independent citing papers note real-world illumination/field-condition challenges in this set, confirming it is not lab-style imagery. Directly supports adding Bacterial Leaf Blight and Tungro to the proposed V2 Rice taxonomy.
- **Classification: A.** Source directly from the Mendeley DOI, not any Kaggle re-upload (several exist, self-tagged with varying licenses — going to the authoritative source avoids that ambiguity entirely).

## 7. Rice Leaf Disease (RLD), Roboflow

- **No single authoritative "RLD" project exists** — multiple distinct, differently-named "Rice Leaf Disease" projects were found on Roboflow Universe under different individual uploaders (Harsha, Rony, "Project," "RICE LEAF DISEASES," "SourceError," "Ho Huu Tuong K17 DN," "ASHIKUR RAHMAN"). The 6-class project at https://universe.roboflow.com/project-khcjh/rice-leaf-disease-detection-obj (Bacterial Leaf Blight, Brown Spot, Leaf Blast, Leaf Scald, Narrow Brown Spot, Healthy) most closely matches the dataset described in arXiv:2603.25006, which cites "the RLD dataset from the Roboflow platform, licensed under CC BY 4.0."
- **License (CONFIRMED as displayed):** every project checked self-declares **CC BY 4.0.**
- **The real issue:** Roboflow lets any uploader self-declare a license regardless of whether they hold rights to the underlying images. **None of the pages found this session document where the images actually originated** — they could be the uploader's own photography, or an unattributed re-upload/re-annotation of PlantVillage, Sethy et al., or another already-cataloged source. This is a direct instance of the exact SAGE-style aggregation-provenance risk the task called out: a license tag at the point of re-upload does not establish the uploader's right to apply it.
- **Classification: B.** Do not treat the self-declared license as sufficient provenance on its own. Where the same disease coverage is available from a confirmed-original source (PlantDoc, the Mendeley Rice sets, Sethy et al. above), prefer that source over an undocumented Roboflow re-upload.

## 8. Sugarcane Plant Diseases Dataset (akilesh253)

- **Kaggle:** https://www.kaggle.com/datasets/akilesh253/sugarcane-plant-diseases-dataset
- **License (CONFIRMED):** **CDLA-Sharing-1.0** (Community Data License Agreement – Sharing – Version 1.0).
- **What CDLA-Sharing-1.0 actually requires (verified against the Linux Foundation's own CDLA FAQ and the agreement's full text, not assumed):**
  - Commercial use of the data is **explicitly permitted** — "no prohibition on commercial use of data."
  - **Training an ML model creates no obligation on the trained model itself.** The CDLA FAQ states this in as many words: *"Training an ML model based on data under the agreement, even copyrighted data, creates no obligation under the agreement for the use or the distribution of the trained model or for the insights it generates."* The agreement's own Section 3.5 states: *"This Agreement imposes no obligations or restrictions on Your Use or Publication of Results."*
  - The copyleft/share-alike mechanic **only** applies if you redistribute the **data itself** (or a modified/"Enhanced" version of the data) — not to a model trained on it.
- **Commercial ML training: YES**, with no obligation carried into the trained model.
- **Caveat:** the dataset is explicitly described as heavily augmented (19,926 images total, via rotation/flip/zoom/crop/resize) from an undisclosed, smaller base — treat the effective unique-image contribution as meaningfully lower than 19,926, and original provenance (field vs. lab, geography) is not stated on the page.
- **Classification: A** — upgraded from the earlier research report's cautious "B" rating now that CDLA-Sharing-1.0's actual terms have been checked directly rather than assumed from its "Sharing" name alone.

## 9. Kamlesh11v Sugarcane Leaf Image Dataset — full provenance trace

Per the task's specific instruction, this was traced backward rather than assumed:

**Kaggle uploader "Kamlesh11v"** → dataset description text is a **verbatim match** to the abstract of → **Thite, S.; Suryawanshi, Y.; Patil, K.; Chumchu, P. (2024), "Sugarcane leaf dataset: A dataset for disease detection and classification for machine learning applications," *Data in Brief* 53, 110268, DOI 10.1016/j.dib.2024.110268** → whose underlying data repository is → **Mendeley Data, DOI 10.17632/355y629ynj.1**, https://data.mendeley.com/datasets/355y629ynj/1, published 2023-07-08.

- **License at the traced authoritative source (CONFIRMED, two independent ways):** (1) Mendeley's own metadata states `"license":{"text":"CC BY 4.0"}`; (2) the Data in Brief journal article itself states, in its own copyright line: *"This is an open access article under the CC BY license (http://creativecommons.org/licenses/by/4.0/)."*
- **Original creators/provenance:** Sandip Thite, Yogesh Suryawanshi, Kailas Patil (Vishwakarma University, Pune, India), Prawit Chumchu (Kasetsart University, Thailand). Images captured via mobile-phone camera in Kendur, Taluka Shirur, Pune district, Maharashtra, India — genuine field collection, not lab-controlled.
- **Evidence the Kaggle upload is the same dataset (INFERRED, not CONFIRMED at file level):** identical total image count (6,748), identical 11-class list in the identical order (smut, yellow leaf disease, pokkah boeng, mosaic, grassy shoot, brown spot, brown rust, banded chlorosis, sett rot, healthy, dried leaves), identical framing language in the description, and a plausible file size (790.03 MB) for 6,748 high-resolution (768×1024) images. **This is strong circumstantial evidence, not proof** — no files were downloaded or hash-compared this session, consistent with the task's explicit instruction not to assume that a similar dataset or paper establishes that an exact Kaggle upload contains those specific images. The Kaggle listing itself did not display a clear, independently-set license tag in what was retrieved this session.
- **Classification: B.**
- **Recommended action, and the actual resolution here:** commercial training eligibility for this *specific Kaggle upload* is not fully confirmed — but eligibility for **the underlying dataset it appears to be re-hosting** is confirmed, at its own authoritative Mendeley location. **The practical path forward is to acquire this dataset directly from the Mendeley DOI (10.17632/355y629ynj.1) rather than the Kaggle mirror.** This sidesteps the identity question entirely and yields a license-confirmed copy, and is the same resolution pattern used for the Wheat Disease Dataset - Small above (go to the authoritative original, not the ambiguous mirror).

---

## Special attention: SAGE

Per the task's instruction, this verification pass did not treat any SAGE-derived evaluation image as a training candidate, and none of the datasets verified above were found to be direct SAGE upstream sources under a different name — though the underlying *type* of risk (an aggregator's license tag not resolving individual image rights) recurred independently in **two** of the datasets checked here (Roboflow RLD, and to a lesser extent the Five Crop Diseases Dataset's own sub-compilation). This reinforces rather than resolves the original SAGE caution: **your existing SAGE-derived real-world/OOD evaluation images (Bugwood-, LeafNet-, CDDM-, "New_Plant_Di"-sourced) remain external-test-only.** No recommendation in this document proposes training on them.

---

## A. Training-eligible datasets (sufficiently established commercial-training rights)

| Dataset | Classification | Authoritative source |
|---|---|---|
| Wheat Disease Dataset - Small (999-image Zenodo subset) | **A** | https://zenodo.org/records/7573133 |
| Rice Leaf Disease Image Samples (Sethy et al.) | **A** | https://data.mendeley.com/datasets/fwcj7stb8r/1 |
| Sugarcane Plant Diseases Dataset (akilesh253) | **A** | https://www.kaggle.com/datasets/akilesh253/sugarcane-plant-diseases-dataset |

(Carried forward, unchanged, from the prior research report's own confirmed findings: PlantDoc — CC BY 4.0; the Mendeley Rice sets Hasan et al./Dhan-Shomadhan/RiceyLeafDisease — CC BY 4.0; Daphal & Koli Sugarcane (nirmalsankalana) — CC0. These were not re-verified in this pass since they were not on the "B" list, but nothing found here contradicts them.)

## B. Verification-required datasets (material questions remain unresolved)

| Dataset | Open question |
|---|---|
| Potato Disease Leaf Dataset (PLD) | Whether ODbL/DbCL's "Produced Works" provisions cover a trained ML model — needs specific legal review, not another web search |
| Kaggle "Wheat Plant Diseases" (kushagra3204) | Current class list/version inconsistency between citing sources; re-verify directly on Kaggle |
| Rice Leaf Disease (RLD), Roboflow | Underlying image provenance undocumented; self-declared license alone is not sufficient confirmation |
| Kamlesh11v Sugarcane Leaf Image Dataset | Identity between the Kaggle mirror and its traced Mendeley original is inferred, not file-confirmed — **resolved in practice by sourcing from Mendeley directly instead** |

## C. Training-blocked datasets (not suitable under currently established terms)

| Dataset | Reason |
|---|---|
| Five Crop Diseases Dataset | Explicitly CC BY-NC-SA 4.0 — NonCommercial. Remains evaluation-only; already correctly used only for V1 evaluation. |
| WheatRust21 | No public repository located — licensing cannot even be assessed. "Commercial training eligibility could not be established." |

## D. Recommended V2 training pool (based on verified evidence only)

Combining this verification pass with the prior research report's already-confirmed "A" sources, the current evidence-backed training pool is:

- **Corn:** PlantDoc (CC BY 4.0)
- **Wheat:** Wheat Disease Dataset - Small, 999 images, sourced from Zenodo (CC BY 4.0)
- **Rice:** Sethy et al. (CC BY 4.0, 5,932 images) + Hasan et al./Dhan-Shomadhan/RiceyLeafDisease (CC BY 4.0, from the prior report)
- **Sugarcane:** akilesh253 (CDLA-Sharing-1.0, confirmed training-safe) + Daphal & Koli (CC0, from the prior report) + the Thite et al. Mendeley dataset (CC BY 4.0), sourced directly from Mendeley rather than via the Kamlesh11v Kaggle mirror
- **Potato:** limited to PlantVillage (CC BY-SA 3.0 at its authoritative GitHub source, per the prior report) until PLD's ODbL/DbCL question is resolved

This pool is **narrower** than the full candidate list in the original research report, specifically because Five Crop Diseases Dataset (D) and WheatRust21 (C) are now confirmed excluded, and PLD, the Kaggle wheat set, Roboflow RLD, and the Kamlesh11v mirror remain unresolved rather than assumed safe.

## E. Remaining blockers before dataset acquisition

1. **Legal review of ODbL/DbCL's application to ML model training**, specifically for PLD — this is not resolvable by further web research alone.
2. **Direct re-verification on Kaggle** of the current Wheat Plant Diseases (kushagra3204) class list/version, to resolve the 9-class vs. 15-class discrepancy found between citing papers.
3. **A decision on whether to pursue Roboflow RLD at all**, given its provenance cannot be confirmed and equivalent disease coverage exists from confirmed-original sources.
4. **Acquire the Thite et al. Sugarcane dataset from its Mendeley DOI**, not the Kamlesh11v Kaggle mirror, to avoid depending on an unconfirmed identity match.
5. **Locate a public repository for WheatRust21, or abandon it as a candidate** — it cannot be assessed further without one.
6. No dataset acquisition should proceed until items 1–3 are closed for the specific datasets they affect; items 4–5 already have a clear resolution path (Mendeley DOI; abandon-or-locate) and are not blocking in the same sense.

Per the task's instructions, **no dataset downloading is recommended to begin from this document** — the above is a readiness map for the next phase, not an authorization to start acquiring data.
