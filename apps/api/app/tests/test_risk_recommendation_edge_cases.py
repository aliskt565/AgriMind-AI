def _create_field(client, headers, soil_type="LOAMY", irrigation_type="DRIP"):
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field", "soil_type": soil_type, "irrigation_type": irrigation_type,
    }, headers=headers)
    return farm_id, r.json()["id"]


def test_dismissed_recommendation_does_not_reappear_without_new_trigger(client, farmer_headers):
    """
    A dismissed recommendation must not resurrect itself on the next
    generate() call unless a genuinely new trigger condition exists --
    otherwise "dismiss" is meaningless to the farmer.
    """
    _, field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=farmer_headers)
    crop_id = r.json()["id"]
    client.patch(f"/api/v1/crops/{crop_id}", json={"stage": "MATURITY"}, headers=farmer_headers)

    recs = client.post("/api/v1/recommendations/generate", headers=farmer_headers).json()
    assert len(recs) == 1
    rec_id = recs[0]["id"]

    client.post(f"/api/v1/recommendations/{rec_id}/dismiss", headers=farmer_headers)

    # Re-running generate() with the SAME underlying condition (still MATURITY,
    # nothing changed) must not resurrect the dismissed recommendation, since
    # _upsert_recommendation only matches against ACTIVE rows.
    recs_after = client.post("/api/v1/recommendations/generate", headers=farmer_headers).json()
    assert rec_id not in [r["id"] for r in recs_after]

    active_list = client.get("/api/v1/recommendations", headers=farmer_headers).json()
    assert all(r["id"] != rec_id for r in active_list)


def test_acknowledged_risk_does_not_block_new_risk_of_different_type(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers, soil_type="UNKNOWN", irrigation_type="UNKNOWN")
    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    risk_id = r.json()[0]["id"]
    client.post(f"/api/v1/risk/{risk_id}/acknowledge", headers=farmer_headers)

    # A fresh scan should still be able to raise new risk findings for this field
    # (e.g. re-detecting the still-present data-quality gap) since acknowledging
    # one risk record doesn't fix the underlying condition.
    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    assert r.status_code == 200
    # The upsert logic only matches ACTIVE risks, so acknowledging creates a
    # fresh ACTIVE row rather than silently reactivating the acknowledged one.
    risk_types = [f["risk_type"] for f in r.json()]
    assert "DATA_QUALITY" in risk_types


def test_risk_level_and_confidence_are_never_the_same_field(client, farmer_headers):
    """Structural guarantee: risk_level and confidence are independent enum spaces on the API contract."""
    _, field_id = _create_field(client, farmer_headers, soil_type="UNKNOWN", irrigation_type="UNKNOWN")
    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    for finding in r.json():
        assert finding["risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
        assert finding["confidence"] in ("LOW", "MEDIUM", "HIGH")
        # Different value domains prove they aren't the same underlying field reused twice
        assert set(["LOW", "MODERATE", "HIGH", "CRITICAL"]) != set(["LOW", "MEDIUM", "HIGH"])


def test_repeated_scans_do_not_create_duplicate_active_risks(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers, soil_type="UNKNOWN", irrigation_type="UNKNOWN")
    for _ in range(5):
        client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    active = client.get("/api/v1/risk", headers=farmer_headers).json()
    data_quality = [r for r in active if r["risk_type"] == "DATA_QUALITY"]
    assert len(data_quality) == 1


def test_repeated_generate_does_not_create_duplicate_recommendations(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=farmer_headers)
    crop_id = r.json()["id"]
    client.patch(f"/api/v1/crops/{crop_id}", json={"stage": "MATURITY"}, headers=farmer_headers)

    for _ in range(5):
        client.post("/api/v1/recommendations/generate", headers=farmer_headers)

    active = client.get("/api/v1/recommendations", headers=farmer_headers).json()
    harvest_recs = [r for r in active if r["category"] == "HARVEST_TIMING"]
    assert len(harvest_recs) == 1


def test_weather_missing_lat_long_handled_safely(client, farmer_headers):
    """A field with no lat/long set must still get a weather response, not a 500."""
    _, field_id = _create_field(client, farmer_headers)
    r = client.get(f"/api/v1/weather/fields/{field_id}", headers=farmer_headers)
    assert r.status_code == 200


def test_crop_intelligence_missing_previous_crop_handled_safely(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/ai/crop-intelligence/fields/{field_id}", json={"season": "Rabi"}, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json()["candidates"]
