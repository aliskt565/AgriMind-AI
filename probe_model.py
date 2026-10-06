"""
Diagnostic probe for the /predict-disease model and its pre/post-processing
heuristics (green-pixel filter, 68% confidence cutoff).

IMPORTANT — WHAT THIS IS NOT:
This is NOT an accuracy evaluation. There is no labeled test set anywhere in
this project (see the provenance audit). None of the images below have
verified ground-truth labels. This script exists only to empirically
characterize BEHAVIOR: does the green-pixel filter fire on constructed edge
cases, what does the confidence distribution look like, does the endpoint
crash on malformed input, etc. Treat every "prediction" below as an
unverified model output, not a correctness claim.
"""
import io
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "apps/api"))
os.chdir(os.path.join(os.path.dirname(__file__), "apps/api"))

from PIL import Image
import numpy as np

RESULTS = []


def green_ratio(img: Image.Image) -> float:
    np_img = np.array(img.convert("RGB"))
    r, g, b = np_img[:, :, 0], np_img[:, :, 1], np_img[:, :, 2]
    green_mask = (g > r.astype(int) + 12) & (g > b.astype(int) + 12)
    return float(np.sum(green_mask) / green_mask.size)


def run_case(name: str, img_bytes: bytes, content_type: str, note: str):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.post("/predict-disease", files={"file": (name, io.BytesIO(img_bytes), content_type)})
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:200]}
    RESULTS.append({"case": name, "note": note, "status_code": r.status_code, "body": body})
    print(f"[{name}] note={note!r} -> HTTP {r.status_code} :: {body}")


def make_jpeg(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr.astype("uint8"), "RGB").save(buf, format="JPEG")
    return buf.getvalue()


if __name__ == "__main__":
    print("=== SYNTHETIC EDGE CASES (constructed, not real photos) ===")

    # 1. Solid green square -- should pass the green-pixel filter easily
    solid_green = np.zeros((224, 224, 3), dtype="uint8")
    solid_green[:, :, 1] = 160  # pure green channel
    gr = green_ratio(Image.fromarray(solid_green))
    run_case("solid_green.jpg", make_jpeg(solid_green), "image/jpeg", f"solid green, green_ratio={gr:.3f}")

    # 2. Solid brown/necrotic-colored square -- simulates a leaf with severe
    #    blight/necrosis covering the whole frame (no green left at all)
    solid_brown = np.zeros((224, 224, 3), dtype="uint8")
    solid_brown[:, :, 0] = 120
    solid_brown[:, :, 1] = 80
    solid_brown[:, :, 2] = 40
    gr = green_ratio(Image.fromarray(solid_brown))
    run_case("solid_brown_necrotic.jpg", make_jpeg(solid_brown), "image/jpeg", f"solid brown/necrotic, green_ratio={gr:.3f}")

    # 3. Green leaf with a large brown lesion covering ~60% of the frame
    #    (simulates a realistic partially-diseased leaf, majority still green)
    mostly_green_some_lesion = np.zeros((224, 224, 3), dtype="uint8")
    mostly_green_some_lesion[:, :, 1] = 160
    mostly_green_some_lesion[60:170, 60:170] = [120, 80, 40]  # brown lesion block
    gr = green_ratio(Image.fromarray(mostly_green_some_lesion))
    run_case("green_leaf_partial_lesion.jpg", make_jpeg(mostly_green_some_lesion), "image/jpeg", f"~40% brown lesion on green leaf, green_ratio={gr:.3f}")

    # 4. Green leaf with a large brown lesion covering ~85% of the frame
    #    (simulates SEVERE disease -- the case the audit flagged as highest risk)
    severe_lesion = np.zeros((224, 224, 3), dtype="uint8")
    severe_lesion[:, :, 1] = 160
    severe_lesion[15:210, 15:210] = [120, 80, 40]
    gr = green_ratio(Image.fromarray(severe_lesion))
    run_case("green_leaf_severe_lesion.jpg", make_jpeg(severe_lesion), "image/jpeg", f"~85% brown lesion on green leaf (severe disease simulation), green_ratio={gr:.3f}")

    # 5. Solid gray -- non-plant background
    solid_gray = np.full((224, 224, 3), 128, dtype="uint8")
    gr = green_ratio(Image.fromarray(solid_gray))
    run_case("solid_gray_background.jpg", make_jpeg(solid_gray), "image/jpeg", f"solid gray non-plant, green_ratio={gr:.3f}")

    # 6. Random noise -- adversarial/garbage input
    rng = np.random.default_rng(42)
    noise = rng.integers(0, 255, (224, 224, 3), dtype="uint8")
    gr = green_ratio(Image.fromarray(noise))
    run_case("random_noise.jpg", make_jpeg(noise), "image/jpeg", f"random noise, green_ratio={gr:.3f}")

    # 7. Invalid content-type (spoofed)
    run_case("fake.jpg", b"not an image at all", "image/jpeg", "corrupt/non-image bytes with image/jpeg content-type")

    # 8. Wrong content-type header entirely (should be rejected before inference)
    run_case("doc.pdf", make_jpeg(solid_green), "application/pdf", "real jpeg bytes but content-type says application/pdf")

    print("\n=== REAL-WORLD-STYLE IMAGES (unlabeled -- no verified ground truth) ===")
    real_dir = "storage/plant-vision"
    # Only the 3 originally-sized images from actual manual testing; the rest
    # in this folder are tiny synthetic artifacts from unrelated QA sessions.
    real_files = [
        "0d6f08f1-7004-4ac4-b1ed-682381f12ea9.jpg",
        "6b0b34c8-f927-4686-81db-7ccd77e8d5c0.jpg",
        "dad03e17-9564-456c-9b85-535977100ef9.jpg",
    ]
    for fname in real_files:
        path = os.path.join(real_dir, fname)
        with open(path, "rb") as f:
            data = f.read()
        img = Image.open(io.BytesIO(data))
        gr = green_ratio(img)
        run_case(fname, data, "image/jpeg", f"unlabeled real-world-style photo, green_ratio={gr:.3f}, size={img.size}")

    with open("/home/claude/probe_results.json", "w") as f:
        json.dump(RESULTS, f, indent=2)
    print("\nResults written to /home/claude/probe_results.json")
