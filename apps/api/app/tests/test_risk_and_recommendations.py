def _create_field(client, headers, soil_type="LOAMY", irrigation_type="DRIP"):
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field", "soil_type": soil_type, "irrigation_type": irrigation_type,
    }, headers=headers)
    return farm_id, r.json()["id"]


# --- Weather ---

def test_weather_returns_contract_shaped_data(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers)
    r = client.get(f"/api/v1/weather/fields/{field_id}", headers=farmer_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "mock-weather"
    assert body["is_stale"] is False
    assert "fetched_at" in body


def test_weather_is_cached_on_second_call(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers)
    r1 = client.get(f"/api/v1/weather/fields/{field_id}", headers=farmer_headers)
    r2 = client.get(f"/api/v1/weather/fields/{field_id}", headers=farmer_headers)
    assert r1.json()["fetched_at"] == r2.json()["fetched_at"]


def test_weather_requires_ownership(client, farmer_headers):
    import uuid
    r = client.get(f"/api/v1/weather/fields/{uuid.uuid4()}", headers=farmer_headers)
    assert r.status_code == 404


# --- Risk Engine ---

def test_risk_scan_flags_missing_soil_irrigation(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers, soil_type="UNKNOWN", irrigation_type="UNKNOWN")
    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    assert r.status_code == 200
    risk_types = [f["risk_type"] for f in r.json()]
    assert "DATA_QUALITY" in risk_types
    # Confidence and risk_level must be separate fields, never merged
    dq_risk = next(f for f in r.json() if f["risk_type"] == "DATA_QUALITY")
    assert "risk_level" in dq_risk and "confidence" in dq_risk


def test_risk_scan_no_data_quality_issue_when_fully_specified(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers, soil_type="CLAY", irrigation_type="FLOOD")
    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    assert r.status_code == 200
    risk_types = [f["risk_type"] for f in r.json()]
    assert "DATA_QUALITY" not in risk_types


def test_risk_scan_is_idempotent_not_duplicating(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers, soil_type="UNKNOWN", irrigation_type="UNKNOWN")
    client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    r = client.get("/api/v1/risk", headers=farmer_headers)
    data_quality_risks = [f for f in r.json() if f["risk_type"] == "DATA_QUALITY"]
    assert len(data_quality_risks) == 1  # upserted, not duplicated


def test_risk_scan_requires_ownership(client, farmer_headers):
    import uuid
    r = client.post(f"/api/v1/risk/fields/{uuid.uuid4()}/scan", headers=farmer_headers)
    assert r.status_code == 404


def test_freshly_planted_crop_does_not_immediately_trigger_activity_gap_risk(client, farmer_headers):
    """
    Regression test for the demo-readiness audit finding: a crop planted
    today (auto-logging its own PLANTING activity, per the crops.py fix)
    must NOT immediately show as at-risk for lack of activity.
    """
    import datetime
    _, field_id = _create_field(client, farmer_headers)
    today = datetime.date.today().isoformat()
    client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat", "planting_date": today}, headers=farmer_headers)

    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    assert r.status_code == 200
    risk_types = [f["risk_type"] for f in r.json()]
    assert "ACTIVITY_GAP" not in risk_types


def test_old_planting_with_no_further_activity_still_triggers_activity_gap_risk(client, farmer_headers):
    """
    Confirms the fix doesn't weaken real detection: a crop planted well
    over ACTIVITY_GAP_DAYS ago, with genuinely no activity since, must
    still be flagged.
    """
    import datetime
    _, field_id = _create_field(client, farmer_headers)
    old_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat", "planting_date": old_date}, headers=farmer_headers)

    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    assert r.status_code == 200
    risk_types = [f["risk_type"] for f in r.json()]
    assert "ACTIVITY_GAP" in risk_types


def test_activity_gap_risk_clears_once_a_recent_activity_is_logged(client, farmer_headers):
    """A subsequent recent activity should reset the activity-gap clock, not just the original planting."""
    import datetime
    _, field_id = _create_field(client, farmer_headers)
    old_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat", "planting_date": old_date}, headers=farmer_headers)
    crop_id = r.json()["id"]

    # Confirm the gap risk exists before logging a recent activity
    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    assert "ACTIVITY_GAP" in [f["risk_type"] for f in r.json()]

    today = datetime.date.today().isoformat()
    client.post(f"/api/v1/crops/{crop_id}/activities", json={"activity_type": "IRRIGATION", "activity_date": today}, headers=farmer_headers)

    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    risk_types = [f["risk_type"] for f in r.json()]
    assert "ACTIVITY_GAP" not in risk_types


def test_risk_scan_uses_meaningful_weather_context(client, farmer_headers, monkeypatch):
    """
    Directly exercises the Risk Engine's weather-threshold logic (heat
    stress, waterlogging, moisture stress, humidity) by forcing a
    deterministic weather snapshot, since the mock weather provider is
    otherwise randomized per-day and per-field. Confirms multiple distinct
    weather findings can coexist for the same field without one silently
    overwriting another (the signal_key dedup fix).
    """
    _, field_id = _create_field(client, farmer_headers, soil_type="CLAY", irrigation_type="FLOOD")

    def fake_get_weather_for_field(field, db):
        from types import SimpleNamespace
        from datetime import datetime, timezone
        return SimpleNamespace(
            data={
                "temperature_celsius": 40.0,      # >= HEAT_STRESS_TEMP_C
                "rainfall_mm_last_24h": 30.0,      # >= HEAVY_RAINFALL_MM, clay+flood -> waterlogging
                "humidity_percent": 80.0,          # >= HIGH_HUMIDITY_PERCENT
                "extreme_weather_alert": None,
            },
            is_stale=False,
            source="mock-weather",
            fetched_at=datetime.now(timezone.utc),
        )

    import app.services.risk_engine as risk_engine_module
    monkeypatch.setattr(risk_engine_module, "get_weather_for_field", fake_get_weather_for_field)

    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    assert r.status_code == 200
    risk_types_and_reasons = [(f["risk_type"], f["reason"]) for f in r.json()]

    # All three distinct weather findings must be present simultaneously --
    # this is exactly what would break without the signal_key dedup fix.
    assert any("temperature" in reason.lower() for _, reason in risk_types_and_reasons)
    assert any("waterlogging" in reason.lower() for _, reason in risk_types_and_reasons)
    assert any("humid" in reason.lower() for _, reason in risk_types_and_reasons)

    weather_findings = [f for f in r.json() if f["risk_type"] == "WEATHER"]
    assert len(weather_findings) >= 3


def test_risk_scan_low_rainfall_rainfed_produces_moisture_stress(client, farmer_headers, monkeypatch):
    _, field_id = _create_field(client, farmer_headers, soil_type="SANDY", irrigation_type="RAINFED")

    def fake_get_weather_for_field(field, db):
        from types import SimpleNamespace
        from datetime import datetime, timezone
        return SimpleNamespace(
            data={"temperature_celsius": 25.0, "rainfall_mm_last_24h": 1.0, "humidity_percent": 40.0, "extreme_weather_alert": None},
            is_stale=False, source="mock-weather", fetched_at=datetime.now(timezone.utc),
        )

    import app.services.risk_engine as risk_engine_module
    monkeypatch.setattr(risk_engine_module, "get_weather_for_field", fake_get_weather_for_field)

    r = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    assert r.status_code == 200
    reasons = [f["reason"].lower() for f in r.json()]
    assert any("rainfall" in reason and "no active irrigation" in reason for reason in reasons)


def test_risk_scan_repeated_weather_scans_do_not_duplicate_findings(client, farmer_headers, monkeypatch):
    """Regression test for the signal_key fix: re-scanning must update in place, not accumulate duplicates."""
    _, field_id = _create_field(client, farmer_headers, soil_type="CLAY", irrigation_type="FLOOD")

    def fake_get_weather_for_field(field, db):
        from types import SimpleNamespace
        from datetime import datetime, timezone
        return SimpleNamespace(
            data={"temperature_celsius": 40.0, "rainfall_mm_last_24h": 30.0, "humidity_percent": 80.0, "extreme_weather_alert": None},
            is_stale=False, source="mock-weather", fetched_at=datetime.now(timezone.utc),
        )

    import app.services.risk_engine as risk_engine_module
    monkeypatch.setattr(risk_engine_module, "get_weather_for_field", fake_get_weather_for_field)

    for _ in range(3):
        client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)

    r = client.get("/api/v1/risk", headers=farmer_headers)
    weather_findings = [f for f in r.json() if f["risk_type"] == "WEATHER"]
    # Exactly 3 distinct weather findings (heat, waterlogging, humidity) --
    # not 9 (3 scans x 3 findings) and not 1 (collapsed by a shared key).
    assert len(weather_findings) == 3


def test_acknowledge_risk(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers, soil_type="UNKNOWN", irrigation_type="UNKNOWN")
    client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    r = client.get("/api/v1/risk", headers=farmer_headers)
    risk_id = r.json()[0]["id"]
    r = client.post(f"/api/v1/risk/{risk_id}/acknowledge", headers=farmer_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "ACKNOWLEDGED"

    r = client.get("/api/v1/risk", headers=farmer_headers)
    assert all(f["id"] != risk_id for f in r.json())  # no longer active


# --- Recommendation Engine ---

def test_no_recommendations_without_a_trigger(client, farmer_headers):
    """Core principle: no recommendation is generated without a real signal."""
    _, field_id = _create_field(client, farmer_headers, soil_type="CLAY", irrigation_type="DRIP")
    client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=farmer_headers)
    r = client.post("/api/v1/recommendations/generate", headers=farmer_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_recommendation_generated_from_data_quality_risk(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers, soil_type="UNKNOWN", irrigation_type="UNKNOWN")
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=farmer_headers)
    crop_id = r.json()["id"]

    # Activity gap risk requires a planting date in the past; skip for this test,
    # but a data-quality risk requires a scan of the field itself (not crop-bound in our model),
    # so directly verify risk->recommendation linkage using activity gap instead, which is crop-bound.
    client.patch(f"/api/v1/crops/{crop_id}", json={"planting_date": "2020-01-01"}, headers=farmer_headers)
    client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)

    r = client.post("/api/v1/recommendations/generate", headers=farmer_headers)
    assert r.status_code == 200
    reasons = [rec["trigger_reason"] for rec in r.json()]
    assert any("risk" in reason.lower() for reason in reasons)
    # every recommendation must carry a non-empty trigger_reason
    assert all(rec["trigger_reason"] for rec in r.json())


def test_recommendation_generated_from_maturity_stage(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers, soil_type="CLAY", irrigation_type="DRIP")
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=farmer_headers)
    crop_id = r.json()["id"]
    client.patch(f"/api/v1/crops/{crop_id}", json={"stage": "MATURITY"}, headers=farmer_headers)

    r = client.post("/api/v1/recommendations/generate", headers=farmer_headers)
    assert r.status_code == 200
    categories = [rec["category"] for rec in r.json()]
    assert "HARVEST_TIMING" in categories


def test_dismiss_recommendation(client, farmer_headers):
    _, field_id = _create_field(client, farmer_headers, soil_type="CLAY", irrigation_type="DRIP")
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=farmer_headers)
    crop_id = r.json()["id"]
    client.patch(f"/api/v1/crops/{crop_id}", json={"stage": "MATURITY"}, headers=farmer_headers)
    client.post("/api/v1/recommendations/generate", headers=farmer_headers)

    r = client.get("/api/v1/recommendations", headers=farmer_headers)
    rec_id = r.json()[0]["id"]
    r = client.post(f"/api/v1/recommendations/{rec_id}/dismiss", headers=farmer_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "DISMISSED"

    r = client.get("/api/v1/recommendations", headers=farmer_headers)
    assert all(rec["id"] != rec_id for rec in r.json())


def test_recommendations_require_auth(client):
    r = client.get("/api/v1/recommendations")
    assert r.status_code == 401


# --- Cross-tenant recommendation integrity (CRITICAL regression coverage) ---
#
# Root cause: `_upsert_recommendation`'s dedup lookup originally matched on
# only (crop_id, category, status=ACTIVE) -- with no farmer_id or field_id
# in the key. Since every field-level risk (DATA_QUALITY, all WEATHER
# threshold findings) has crop_id=None, this meant one farmer's risk scan
# could silently find and OVERWRITE a different farmer's existing
# recommendation row instead of creating their own -- confirmed live
# against the real dev database before the fix. The fix adds both
# farmer_id and field_id to the dedup key.

def _register_and_login(client, email, password="TestPass123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Farmer"})
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _force_weather(monkeypatch, temperature=None, rainfall=None, humidity=None, extreme_alert=None):
    from types import SimpleNamespace
    from datetime import datetime, timezone
    import app.services.risk_engine as risk_engine_module

    def fake_get_weather_for_field(field, db):
        return SimpleNamespace(
            data={
                "temperature_celsius": temperature, "rainfall_mm_last_24h": rainfall,
                "humidity_percent": humidity, "extreme_weather_alert": extreme_alert,
            },
            is_stale=False, source="mock-weather", fetched_at=datetime.now(timezone.utc),
        )
    monkeypatch.setattr(risk_engine_module, "get_weather_for_field", fake_get_weather_for_field)


def test_cross_tenant_recommendation_isolation_with_same_category_field_level_risk(client, farmer_headers, monkeypatch):
    """
    The exact scenario that reproduced the bug: two different farmers each
    trigger a field-level risk (heat stress -> CROP_HEALTH category,
    crop_id=None) around the same time. Farmer A's recommendation must
    remain completely untouched after Farmer B generates their own.
    """
    _force_weather(monkeypatch, temperature=40.0, rainfall=0.0, humidity=40.0)

    r = client.post("/api/v1/farms", json={"name": "A's Farm"}, headers=farmer_headers)
    farm_a = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_a}/fields", json={"name": "A's Field", "soil_type": "CLAY", "irrigation_type": "DRIP"}, headers=farmer_headers)
    field_a = r.json()["id"]
    client.post(f"/api/v1/risk/fields/{field_a}/scan", headers=farmer_headers)
    recs_a_before = client.post("/api/v1/recommendations/generate", headers=farmer_headers).json()
    assert len(recs_a_before) == 1
    rec_a_id = recs_a_before[0]["id"]
    rec_a_text = recs_a_before[0]["text"]

    b_headers = _register_and_login(client, "farmer.b.crosstenant@example.com")
    r = client.post("/api/v1/farms", json={"name": "B's Farm"}, headers=b_headers)
    farm_b = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_b}/fields", json={"name": "B's Field", "soil_type": "SANDY", "irrigation_type": "DRIP"}, headers=b_headers)
    field_b = r.json()["id"]
    client.post(f"/api/v1/risk/fields/{field_b}/scan", headers=b_headers)
    recs_b = client.post("/api/v1/recommendations/generate", headers=b_headers).json()

    assert len(recs_b) == 1
    rec_b_id = recs_b[0]["id"]
    assert rec_b_id != rec_a_id

    recs_a_after = client.get("/api/v1/recommendations", headers=farmer_headers).json()
    assert len(recs_a_after) == 1
    assert recs_a_after[0]["id"] == rec_a_id
    assert recs_a_after[0]["text"] == rec_a_text

    assert all(r["id"] != rec_b_id for r in recs_a_after)
    b_visible_ids = [r["id"] for r in client.get("/api/v1/recommendations", headers=b_headers).json()]
    assert rec_a_id not in b_visible_ids


def test_two_fields_same_farmer_do_not_collide_on_field_level_recommendation(client, farmer_headers):
    """
    Same class of bug, one level down: two DIFFERENT FIELDS belonging to
    the SAME farmer both missing soil/irrigation info both produce a
    crop_id=None, category=SOIL recommendation. Without field_id in the
    dedup key, the second field's finding would silently overwrite the
    first field's recommendation, losing it.
    """
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "Field 1", "soil_type": "UNKNOWN", "irrigation_type": "UNKNOWN"}, headers=farmer_headers)
    field_1 = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "Field 2", "soil_type": "UNKNOWN", "irrigation_type": "UNKNOWN"}, headers=farmer_headers)
    field_2 = r.json()["id"]

    client.post(f"/api/v1/risk/fields/{field_1}/scan", headers=farmer_headers)
    client.post(f"/api/v1/risk/fields/{field_2}/scan", headers=farmer_headers)
    recs = client.post("/api/v1/recommendations/generate", headers=farmer_headers).json()

    soil_recs = [r for r in recs if r["category"] == "SOIL"]
    assert len(soil_recs) == 2
    assert {r["field_id"] for r in soil_recs} == {field_1, field_2}


def test_repeated_scan_and_generate_for_same_farmer_updates_in_place_not_duplicates(client, farmer_headers, monkeypatch):
    """Same-farmer repeated scans must still dedup correctly after the farmer_id/field_id fix -- not regress into spam."""
    _force_weather(monkeypatch, temperature=40.0, rainfall=0.0, humidity=40.0)
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "Field", "soil_type": "CLAY", "irrigation_type": "DRIP"}, headers=farmer_headers)
    field_id = r.json()["id"]

    for _ in range(4):
        client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
        client.post("/api/v1/recommendations/generate", headers=farmer_headers)

    recs = client.get("/api/v1/recommendations", headers=farmer_headers).json()
    heat_recs = [r for r in recs if r["category"] == "CROP_HEALTH"]
    assert len(heat_recs) == 1


def test_multiple_simultaneous_weather_conditions_produce_accurate_distinct_recommendations(client, farmer_headers, monkeypatch):
    """
    Full coverage of the originally-flagged UX concern: heat stress +
    waterlogging + high humidity simultaneously must each produce their own
    accurate, non-generic recommendation -- not one generic "adjust
    irrigation" recommendation repeated three times (the original bug), and
    not silently dropped either.
    """
    _force_weather(monkeypatch, temperature=40.0, rainfall=30.0, humidity=80.0)
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "Field", "soil_type": "CLAY", "irrigation_type": "FLOOD"}, headers=farmer_headers)
    field_id = r.json()["id"]

    findings = client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers).json()
    assert len(findings) == 3

    recs = client.post("/api/v1/recommendations/generate", headers=farmer_headers).json()
    categories = sorted(r["category"] for r in recs)
    assert categories == ["CROP_HEALTH", "DISEASE_PREVENTION", "IRRIGATION"]

    texts = {r["category"]: r["text"] for r in recs}
    assert "temperature" in texts["CROP_HEALTH"].lower() or "heat" in texts["CROP_HEALTH"].lower()
    assert "waterlogging" in texts["IRRIGATION"].lower() or "drainage" in texts["IRRIGATION"].lower()
    assert "humid" in texts["DISEASE_PREVENTION"].lower() or "fungal" in texts["DISEASE_PREVENTION"].lower()
    assert not any("adjust your irrigation plan ahead of the forecast" in r["text"].lower() for r in recs)


def test_moisture_stress_condition_produces_its_own_accurate_recommendation(client, farmer_headers, monkeypatch):
    _force_weather(monkeypatch, temperature=25.0, rainfall=1.0, humidity=40.0)
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "Field", "soil_type": "SANDY", "irrigation_type": "RAINFED"}, headers=farmer_headers)
    field_id = r.json()["id"]

    client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)
    recs = client.post("/api/v1/recommendations/generate", headers=farmer_headers).json()
    assert len(recs) == 1
    assert recs[0]["category"] == "IRRIGATION"
    assert "rainfall" in recs[0]["text"].lower() and "irrigation" in recs[0]["text"].lower()


def test_upsert_risk_cannot_cross_farmer_boundaries(client, farmer_headers, monkeypatch):
    """
    Positive confirmation that _upsert_risk (unlike the recommendation
    engine before this fix) was never vulnerable to this class of bug: its
    dedup key always includes field_id, which is a globally unique UUID
    that can never be shared between two different farmers' fields.
    """
    _force_weather(monkeypatch, temperature=40.0, rainfall=0.0, humidity=40.0)
    r = client.post("/api/v1/farms", json={"name": "A's Farm"}, headers=farmer_headers)
    farm_a = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_a}/fields", json={"name": "A's Field", "soil_type": "CLAY", "irrigation_type": "DRIP"}, headers=farmer_headers)
    field_a = r.json()["id"]
    client.post(f"/api/v1/risk/fields/{field_a}/scan", headers=farmer_headers)
    risks_a_before = client.get("/api/v1/risk", headers=farmer_headers).json()

    b_headers = _register_and_login(client, "farmer.b.riskisolation@example.com")
    r = client.post("/api/v1/farms", json={"name": "B's Farm"}, headers=b_headers)
    farm_b = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_b}/fields", json={"name": "B's Field", "soil_type": "CLAY", "irrigation_type": "DRIP"}, headers=b_headers)
    field_b = r.json()["id"]
    client.post(f"/api/v1/risk/fields/{field_b}/scan", headers=b_headers)

    risks_a_after = client.get("/api/v1/risk", headers=farmer_headers).json()
    assert risks_a_before == risks_a_after
