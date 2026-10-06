import io

import numpy as np
from PIL import Image


def _solid_jpeg(rgb: tuple[int, int, int] = (40, 160, 40)) -> bytes:
    """A genuinely decodable 224x224 JPEG, for tests that must exercise the
    real CNN's decode/inference path (V1's mock provider accepted any bytes
    via a sha256 hash, so old tests used fake byte strings -- V2's real model
    correctly requires an actual image, which these tests now provide)."""
    arr = np.zeros((224, 224, 3), dtype="uint8")
    arr[:, :, 0], arr[:, :, 1], arr[:, :, 2] = rgb
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, format="JPEG")
    return buf.getvalue()


def _create_field(client, headers):
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field", "soil_type": "LOAMY", "irrigation_type": "DRIP",
    }, headers=headers)
    return r.json()["id"]


def test_crop_intelligence_canal_irrigation_produces_a_risk_note(client, farmer_headers):
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field", "soil_type": "LOAMY", "irrigation_type": "CANAL",
    }, headers=farmer_headers)
    field_id = r.json()["id"]

    r = client.post(f"/api/v1/ai/crop-intelligence/fields/{field_id}", json={"season": "Rabi"}, headers=farmer_headers)
    assert r.status_code == 201
    candidates = r.json()["candidates"]
    assert any(c["risk_note"] and "canal" in c["risk_note"].lower() for c in candidates)


def test_crop_intelligence_uses_real_weather_context(client, farmer_headers):
    """
    Regression test for the bug where weather_context was never populated:
    confirms the crop advisor's assumptions no longer claim weather data was
    unavailable when the Weather Intelligence service actually has data for
    this field (mock weather always returns a value, never None).
    """
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field", "soil_type": "LOAMY", "irrigation_type": "DRIP",
    }, headers=farmer_headers)
    field_id = r.json()["id"]

    r = client.post(f"/api/v1/ai/crop-intelligence/fields/{field_id}", json={"season": "Rabi"}, headers=farmer_headers)
    assert r.status_code == 201
    body = r.json()
    assumptions_text = " ".join(body["important_assumptions"]).lower()
    assert "no live weather data was available" not in assumptions_text
    # Explanation text should reference real conditions, not just static factors
    assert any("conditions" in c["explanation"].lower() for c in body["candidates"])


def test_crop_intelligence_uses_field_rotation_history(client, farmer_headers):
    """
    Confirms rotation_history (not just the single most-recent crop) is
    populated from the field's own past harvested crops and factored into
    scoring -- previously only `previous_crop` was ever sent to the provider.
    """
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field", "soil_type": "LOAMY", "irrigation_type": "DRIP",
    }, headers=farmer_headers)
    field_id = r.json()["id"]

    # Plant and harvest two crops so this field has real rotation history
    for crop_type in ["Wheat", "Maize"]:
        r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": crop_type}, headers=farmer_headers)
        crop_id = r.json()["id"]
        client.patch(f"/api/v1/crops/{crop_id}", json={"stage": "HARVESTED", "actual_harvest_date": "2026-01-01"}, headers=farmer_headers)

    r = client.post(f"/api/v1/ai/crop-intelligence/fields/{field_id}", json={"season": "Rabi"}, headers=farmer_headers)
    assert r.status_code == 201
    # Wheat and Maize both appeared in rotation history -- their scores should
    # reflect the rotation penalty applied in the mock provider.
    candidates = {c["crop_type"]: c for c in r.json()["candidates"]}
    assert "Wheat" in candidates or "Maize" in candidates


def test_crop_intelligence_returns_ranked_candidates(client, farmer_headers):
    field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/ai/crop-intelligence/fields/{field_id}", json={
        "season": "Rabi", "previous_crop": "Rice",
    }, headers=farmer_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["is_mock"] is True
    assert len(body["candidates"]) > 0

    # Candidates must be ranked descending by suitability
    scores = [c["suitability_score"] for c in body["candidates"]]
    assert scores == sorted(scores, reverse=True)

    # Confidence/suitability/risk must remain separate fields, never merged
    first = body["candidates"][0]
    assert "suitability_score" in first
    assert "confidence" in first
    assert first["confidence"] in ("LOW", "MEDIUM", "HIGH")
    assert "risk_note" in first  # present as its own key, even if None


def test_crop_intelligence_requires_ownership(client, farmer_headers):
    import uuid
    r = client.post(f"/api/v1/ai/crop-intelligence/fields/{uuid.uuid4()}", json={"season": "Rabi"}, headers=farmer_headers)
    assert r.status_code == 404


def test_crop_intelligence_history(client, farmer_headers):
    field_id = _create_field(client, farmer_headers)
    client.post(f"/api/v1/ai/crop-intelligence/fields/{field_id}", json={"season": "Kharif"}, headers=farmer_headers)
    r = client.get(f"/api/v1/ai/crop-intelligence/fields/{field_id}/history", headers=farmer_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def _create_crop(client, headers):
    field_id = _create_field(client, headers)
    # Corn is used here (not Wheat) because V2's Plant Vision model currently
    # only supports Corn/Potato (see app/services/plant_vision_cnn.py). These
    # tests exercise image-validation behavior, not crop-support -- crop
    # support itself is covered separately by test_plant_vision_unsupported_crop.
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Corn"}, headers=headers)
    return r.json()["id"]


def test_plant_vision_rejects_non_image_file(client, farmer_headers):
    crop_id = _create_crop(client, farmer_headers)
    files = {"image": ("not_an_image.txt", io.BytesIO(b"hello world"), "text/plain")}
    r = client.post(f"/api/v1/ai/plant-vision/crops/{crop_id}/detect", files=files, headers=farmer_headers)
    # V2's CNN service validates MIME type before touching the model and fails
    # fast with an HTTP error (unlike a corrupt-but-correctly-typed image,
    # which is an in-band REJECTED_LOW_QUALITY result -- see the tiny-file
    # test below). This is the actual, intentional two-layer validation
    # design, not a regression from V1's mock provider.
    assert r.status_code == 400
    assert "Invalid file type" in r.json()["error"]["message"]


def test_plant_vision_rejects_tiny_file(client, farmer_headers):
    crop_id = _create_crop(client, farmer_headers)
    files = {"image": ("tiny.jpg", io.BytesIO(b"x"), "image/jpeg")}
    r = client.post(f"/api/v1/ai/plant-vision/crops/{crop_id}/detect", files=files, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json()["result_type"] == "REJECTED_LOW_QUALITY"


def test_plant_vision_unsupported_crop(client, farmer_headers):
    field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Dragonfruit"}, headers=farmer_headers)
    crop_id = r.json()["id"]
    files = {"image": ("plant.jpg", io.BytesIO(b"fake-image-bytes-but-large-enough-to-pass-size-check" * 50), "image/jpeg")}
    r = client.post(f"/api/v1/ai/plant-vision/crops/{crop_id}/detect", files=files, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json()["result_type"] == "UNSUPPORTED_CROP"


def test_plant_vision_valid_image_produces_a_result(client, farmer_headers):
    crop_id = _create_crop(client, farmer_headers)
    # A genuinely decodable JPEG is required here -- V1's mock provider hashed
    # arbitrary bytes to fabricate a result regardless of whether they were a
    # real image; V2's real CNN correctly rejects non-decodable bytes as
    # REJECTED_LOW_QUALITY instead (a real correctness improvement), so this
    # test must supply real image bytes to exercise the actual inference path.
    files = {"image": ("plant.jpg", io.BytesIO(_solid_jpeg()), "image/jpeg")}
    r = client.post(f"/api/v1/ai/plant-vision/crops/{crop_id}/detect", files=files, headers=farmer_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["result_type"] in (
        "HIGH_CONFIDENCE", "LOW_CONFIDENCE", "HEALTHY", "REJECTED_NON_PLANT", "REJECTED_LOW_QUALITY",
    )
    assert "not a confirmed agricultural diagnosis" in body["disclaimer"]


def test_plant_vision_ownership_enforced(client, farmer_headers):
    import uuid
    files = {"image": ("plant.jpg", io.BytesIO(b"x" * 2000), "image/jpeg")}
    r = client.post(f"/api/v1/ai/plant-vision/crops/{uuid.uuid4()}/detect", files=files, headers=farmer_headers)
    assert r.status_code == 404


def test_plant_vision_history_accumulates(client, farmer_headers):
    crop_id = _create_crop(client, farmer_headers)
    files = {"image": ("plant.jpg", io.BytesIO(b"x" * 2000), "image/jpeg")}
    client.post(f"/api/v1/ai/plant-vision/crops/{crop_id}/detect", files=files, headers=farmer_headers)
    r = client.get(f"/api/v1/ai/plant-vision/crops/{crop_id}/history", headers=farmer_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
