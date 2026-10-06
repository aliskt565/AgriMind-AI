"""
V2 canonical taxonomy and explicit label-mapping tables.

IMPORTANT (documented per the no-silent-merge requirement):
The full frozen taxonomy requested for V2 spans Corn, Potato, Rice, Wheat, and
Sugarcane (18 classes). This session's network sandbox allows outbound access
only to a fixed domain allowlist (see /mnt/user-data -- network_configuration).
That allowlist includes github.com/codeload.github.com/raw.githubusercontent.com,
but does NOT include data.mendeley.com, zenodo.org, or kaggle.com -- confirmed
this session via direct HTTP checks (403 host_not_allowed for all three).

Every Class-A source verified in docs/ml_v2_dataset_license_verification_2026_09.md
for Rice (Sethy et al., Mendeley), Wheat (Long et al., Zenodo), and Sugarcane
(akilesh253 CDLA-Sharing-1.0 and Thite et al., both on Kaggle/Mendeley) is
UNREACHABLE from this environment. The only two verified Class-A/near-A sources
reachable this session are GitHub-hosted: PlantDoc (CC BY 4.0) and the
PlantVillage GitHub mirror (CC BY-SA 3.0), which together only cover Corn and
Potato.

V2-ALPHA THEREFORE COVERS CORN AND POTATO ONLY (7 classes). Rice, Wheat, and
Sugarcane are explicitly DEFERRED, not silently dropped -- see
docs/ml_v2_training_report.md for the full explanation and the exact retry
path once Mendeley/Zenodo/Kaggle access is available.
"""

# Canonical V2-alpha taxonomy actually trained this session.
V2_ALPHA_CLASSES = [
    "Corn___Common_Rust",
    "Corn___Gray_Leaf_Spot",
    "Corn___Healthy",
    "Corn___Northern_Leaf_Blight",
    "Potato___Early_Blight",
    "Potato___Healthy",
    "Potato___Late_Blight",
]

# Full frozen taxonomy from the execution brief, kept here for traceability.
# Classes not in V2_ALPHA_CLASSES are DEFERRED (see module docstring), not merged
# into anything and not silently dropped from the design.
V2_FULL_TARGET_TAXONOMY = [
    "Corn___Common_Rust", "Corn___Gray_Leaf_Spot", "Corn___Healthy", "Corn___Northern_Leaf_Blight",
    "Potato___Early_Blight", "Potato___Healthy", "Potato___Late_Blight",
    "Rice___Brown_Spot", "Rice___Healthy", "Rice___Leaf_Blast", "Rice___Neck_Blast", "Rice___Bacterial_Leaf_Blight",
    "Wheat___Brown_Rust", "Wheat___Healthy", "Wheat___Yellow_Rust", "Wheat___Mildew", "Wheat___Septoria",
    "Sugarcane___Red_Rot", "Sugarcane___Healthy", "Sugarcane___Mosaic", "Sugarcane___Rust", "Sugarcane___Yellow_Leaf",
]

DEFERRED_CLASSES = [c for c in V2_FULL_TARGET_TAXONOMY if c not in V2_ALPHA_CLASSES]

# Explicit, documented source-folder -> canonical-label mappings.
# Nothing here is inferred silently; every mapping is a literal folder-name lookup.

PLANTVILLAGE_LABEL_MAP = {
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "Corn___Gray_Leaf_Spot",
    "Corn_(maize)___Common_rust_": "Corn___Common_Rust",
    "Corn_(maize)___Northern_Leaf_Blight": "Corn___Northern_Leaf_Blight",
    "Corn_(maize)___healthy": "Corn___Healthy",
    "Potato___Early_blight": "Potato___Early_Blight",
    "Potato___Late_blight": "Potato___Late_Blight",
    "Potato___healthy": "Potato___Healthy",
}

# PlantDoc's class names are informal (internet-scraped, human-annotated) and do
# not use PlantVillage-style canonical disease names. The mapping below is an
# EXPLICIT, DOCUMENTED assumption, flagged rather than silently applied:
#   - "Corn leaf blight" is mapped to Corn___Northern_Leaf_Blight. PlantDoc's
#     own paper/readme does not disambiguate this from other corn blights
#     (e.g. Southern Leaf Blight). Northern Leaf Blight is by far the more
#     common corn leaf blight in the source regions PlantDoc scraped from
#     (India-focused agricultural imagery), which is the basis for this
#     mapping, but it is a judgment call, not a verified 1:1 label match.
#     Flagged here and in docs/ml_v2_training_report.md for expert review.
#   - PlantDoc has NO healthy-leaf classes for Corn or Potato, so it
#     contributes zero images to Corn___Healthy / Potato___Healthy.
PLANTDOC_LABEL_MAP = {
    "Corn Gray leaf spot": "Corn___Gray_Leaf_Spot",
    "Corn rust leaf": "Corn___Common_Rust",
    "Corn leaf blight": "Corn___Northern_Leaf_Blight",  # documented assumption, see above
    "Potato leaf early blight": "Potato___Early_Blight",
    "Potato leaf late blight": "Potato___Late_Blight",
}
