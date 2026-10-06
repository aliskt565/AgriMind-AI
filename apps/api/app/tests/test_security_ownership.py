"""
Security regression tests: genuine IDOR scenarios where Farmer B holds a
REAL resource ID belonging to Farmer A (not a random UUID) and attempts to
access it. This is the scenario random-UUID 404 tests don't cover -- a
resource ID guessed, leaked, or reused from another session.
"""
import io


def _register_and_login(client, email, password="TestPass123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Farmer"})
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _full_setup_for_farmer_a(client, headers):
    """Creates a farm -> field -> crop -> activity chain for farmer A, returns all IDs."""
    r = client.post("/api/v1/farms", json={"name": "A's Farm"}, headers=headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "A's Field", "soil_type": "UNKNOWN", "irrigation_type": "UNKNOWN",
    }, headers=headers)
    field_id = r.json()["id"]
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=headers)
    crop_id = r.json()["id"]
    client.post(f"/api/v1/crops/{crop_id}/activities", json={
        "activity_type": "IRRIGATION", "activity_date": "2026-08-01",
    }, headers=headers)
    return farm_id, field_id, crop_id


def test_idor_weather_cannot_be_read_by_other_farmer(client, farmer_headers):
    _, field_id, _ = _full_setup_for_farmer_a(client, farmer_headers)
    b_headers = _register_and_login(client, "farmer.b.weather@example.com")
    r = client.get(f"/api/v1/weather/fields/{field_id}", headers=b_headers)
    assert r.status_code == 404


def test_idor_crop_intelligence_cannot_be_requested_by_other_farmer(client, farmer_headers):
    _, field_id, _ = _full_setup_for_farmer_a(client, farmer_headers)
    b_headers = _register_and_login(client, "farmer.b.ci@example.com")
    r = client.post(f"/api/v1/ai/crop-intelligence/fields/{field_id}", json={"season": "Rabi"}, headers=b_headers)
    assert r.status_code == 404


def test_idor_crop_intelligence_history_cannot_be_read_by_other_farmer(client, farmer_headers):
    _, field_id, _ = _full_setup_for_farmer_a(client, farmer_headers)
    client.post(f"/api/v1/ai/crop-intelligence/fields/{field_id}", json={"season": "Rabi"}, headers=farmer_headers)
    b_headers = _register_and_login(client, "farmer.b.cih@example.com")
    r = client.get(f"/api/v1/ai/crop-intelligence/fields/{field_id}/history", headers=b_headers)
    assert r.status_code == 404


def test_idor_plant_vision_cannot_be_requested_by_other_farmer(client, farmer_headers):
    _, _, crop_id = _full_setup_for_farmer_a(client, farmer_headers)
    b_headers = _register_and_login(client, "farmer.b.pv@example.com")
    files = {"image": ("plant.jpg", io.BytesIO(b"x" * 2000), "image/jpeg")}
    r = client.post(f"/api/v1/ai/plant-vision/crops/{crop_id}/detect", files=files, headers=b_headers)
    assert r.status_code == 404


def test_idor_plant_vision_history_cannot_be_read_by_other_farmer(client, farmer_headers):
    _, _, crop_id = _full_setup_for_farmer_a(client, farmer_headers)
    files = {"image": ("plant.jpg", io.BytesIO(b"x" * 2000), "image/jpeg")}
    client.post(f"/api/v1/ai/plant-vision/crops/{crop_id}/detect", files=files, headers=farmer_headers)
    b_headers = _register_and_login(client, "farmer.b.pvh@example.com")
    r = client.get(f"/api/v1/ai/plant-vision/crops/{crop_id}/history", headers=b_headers)
    assert r.status_code == 404


def test_idor_risk_scan_cannot_be_triggered_by_other_farmer(client, farmer_headers):
    _, field_id, _ = _full_setup_for_farmer_a(client, farmer_headers)
    b_headers = _register_and_login(client, "farmer.b.risk@example.com")
    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=b_headers)
    assert r.status_code == 404


def test_idor_risk_list_does_not_leak_other_farmers_risks(client, farmer_headers):
    _, field_id, _ = _full_setup_for_farmer_a(client, farmer_headers)
    client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)  # A has a DATA_QUALITY risk now

    b_headers = _register_and_login(client, "farmer.b.risklist@example.com")
    r = client.get("/api/v1/risk", headers=b_headers)
    assert r.status_code == 200
    assert r.json() == []  # B must see none of A's risks


def test_idor_risk_acknowledge_cannot_be_done_by_other_farmer(client, farmer_headers):
    _, field_id, _ = _full_setup_for_farmer_a(client, farmer_headers)
    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    risk_id = r.json()[0]["id"]

    b_headers = _register_and_login(client, "farmer.b.riskack@example.com")
    r = client.post(f"/api/v1/risk/{risk_id}/acknowledge", headers=b_headers)
    assert r.status_code == 404

    # Confirm it's genuinely untouched -- still active from A's perspective
    r = client.get("/api/v1/risk", headers=farmer_headers)
    assert any(risk["id"] == risk_id and risk["status"] == "ACTIVE" for risk in r.json())


def test_idor_recommendations_list_does_not_leak_other_farmers_data(client, farmer_headers):
    _, field_id, crop_id = _full_setup_for_farmer_a(client, farmer_headers)
    client.patch(f"/api/v1/crops/{crop_id}", json={"stage": "MATURITY"}, headers=farmer_headers)
    client.post("/api/v1/recommendations/generate", headers=farmer_headers)

    b_headers = _register_and_login(client, "farmer.b.reclist@example.com")
    r = client.get("/api/v1/recommendations", headers=b_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_idor_recommendation_dismiss_cannot_be_done_by_other_farmer(client, farmer_headers):
    _, field_id, crop_id = _full_setup_for_farmer_a(client, farmer_headers)
    client.patch(f"/api/v1/crops/{crop_id}", json={"stage": "MATURITY"}, headers=farmer_headers)
    recs = client.post("/api/v1/recommendations/generate", headers=farmer_headers).json()
    rec_id = recs[0]["id"]

    b_headers = _register_and_login(client, "farmer.b.recdismiss@example.com")
    r = client.post(f"/api/v1/recommendations/{rec_id}/dismiss", headers=b_headers)
    assert r.status_code == 404

    r = client.get("/api/v1/recommendations", headers=farmer_headers)
    assert any(rec["id"] == rec_id and rec["status"] == "ACTIVE" for rec in r.json())


def test_idor_recommendations_generate_only_touches_own_data(client, farmer_headers):
    """generate() must never create or return recommendations scoped to another farmer's resources."""
    _, field_id, crop_id = _full_setup_for_farmer_a(client, farmer_headers)
    client.patch(f"/api/v1/crops/{crop_id}", json={"stage": "MATURITY"}, headers=farmer_headers)

    b_headers = _register_and_login(client, "farmer.b.recgen@example.com")
    r = client.post("/api/v1/recommendations/generate", headers=b_headers)
    assert r.status_code == 200
    assert r.json() == []  # B has no crops/risks of their own -- nothing to generate, and none of A's leak through


def test_idor_activity_log_cannot_be_read_by_other_farmer(client, farmer_headers):
    _, _, crop_id = _full_setup_for_farmer_a(client, farmer_headers)
    b_headers = _register_and_login(client, "farmer.b.activity@example.com")
    r = client.get(f"/api/v1/crops/{crop_id}/activities", headers=b_headers)
    assert r.status_code == 404


def test_idor_dashboard_summary_is_scoped_per_farmer(client, farmer_headers):
    _full_setup_for_farmer_a(client, farmer_headers)
    b_headers = _register_and_login(client, "farmer.b.dash@example.com")
    r = client.get("/api/v1/dashboard/summary", headers=b_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["farm_count"] == 0
    assert body["field_count"] == 0
    assert body["active_crop_count"] == 0
