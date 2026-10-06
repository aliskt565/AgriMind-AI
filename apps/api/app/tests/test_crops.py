def _create_field(client, headers):
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "Field"}, headers=headers)
    return r.json()["id"]


def test_create_crop_with_planting_date_auto_logs_planting_activity(client, farmer_headers):
    """
    Regression test: planting is a real farming activity, and creating a
    crop with a planting_date should auto-log a PLANTING CropActivity so
    the Farm Risk Engine has a genuine reference point from day one
    (previously, crops created with no manually-logged activity had no
    activity-gap reference at all).
    """
    field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={
        "crop_type": "Wheat", "planting_date": "2026-08-15",
    }, headers=farmer_headers)
    assert r.status_code == 201
    crop_id = r.json()["id"]

    r = client.get(f"/api/v1/crops/{crop_id}/activities", headers=farmer_headers)
    assert r.status_code == 200
    activities = r.json()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == "PLANTING"
    assert activities[0]["activity_date"] == "2026-08-15"


def test_create_crop_without_planting_date_does_not_auto_log_activity(client, farmer_headers):
    """A crop created with no planting_date at all should not get a fabricated activity entry."""
    field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=farmer_headers)
    crop_id = r.json()["id"]

    r = client.get(f"/api/v1/crops/{crop_id}/activities", headers=farmer_headers)
    assert r.json() == []


def test_create_crop(client, farmer_headers):
    field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={
        "crop_type": "Rice", "variety": "Basmati", "planting_date": "2026-06-01",
    }, headers=farmer_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["stage"] == "PLANNED"
    assert body["source"] == "MANUAL"
    assert body["health_status"] == "HEALTHY"


def test_crop_stage_update(client, farmer_headers):
    field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Cotton"}, headers=farmer_headers)
    crop_id = r.json()["id"]

    r = client.patch(f"/api/v1/crops/{crop_id}", json={"stage": "VEGETATIVE"}, headers=farmer_headers)
    assert r.status_code == 200
    assert r.json()["stage"] == "VEGETATIVE"


def test_crop_harvest_closes_lifecycle(client, farmer_headers):
    field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Maize"}, headers=farmer_headers)
    crop_id = r.json()["id"]

    r = client.patch(f"/api/v1/crops/{crop_id}", json={
        "stage": "HARVESTED", "actual_harvest_date": "2026-10-01", "actual_yield": 1200, "yield_unit": "kg",
    }, headers=farmer_headers)
    assert r.status_code == 200
    assert r.json()["stage"] == "HARVESTED"
    assert r.json()["actual_yield"] == 1200


def test_list_all_crops_across_farms(client, farmer_headers):
    field_id_1 = _create_field(client, farmer_headers)
    r = client.post("/api/v1/farms", json={"name": "Second Farm"}, headers=farmer_headers)
    farm_2 = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_2}/fields", json={"name": "Field 2"}, headers=farmer_headers)
    field_id_2 = r.json()["id"]

    client.post(f"/api/v1/fields/{field_id_1}/crops", json={"crop_type": "Wheat"}, headers=farmer_headers)
    client.post(f"/api/v1/fields/{field_id_2}/crops", json={"crop_type": "Barley"}, headers=farmer_headers)

    r = client.get("/api/v1/crops", headers=farmer_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_log_activity_and_list(client, farmer_headers):
    field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=farmer_headers)
    crop_id = r.json()["id"]

    r = client.post(f"/api/v1/crops/{crop_id}/activities", json={
        "activity_type": "FERTILIZATION", "activity_date": "2026-08-05", "quantity": 50, "quantity_unit": "kg",
    }, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json()["activity_type"] == "FERTILIZATION"

    r = client.get(f"/api/v1/crops/{crop_id}/activities", headers=farmer_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_crop_ownership_chain_enforced(client, farmer_headers):
    """Crop -> Field -> Farm -> Farmer chain must be fully checked, not just the top level."""
    field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Sugarcane"}, headers=farmer_headers)
    crop_id = r.json()["id"]

    client.post("/api/v1/auth/register", json={
        "email": "chain.intruder@example.com", "password": "IntruderPass1", "full_name": "Chain Intruder",
    })
    r = client.post("/api/v1/auth/login", data={"username": "chain.intruder@example.com", "password": "IntruderPass1"})
    intruder_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get(f"/api/v1/crops/{crop_id}", headers=intruder_headers)
    assert r.status_code == 404
    r = client.post(f"/api/v1/crops/{crop_id}/activities", json={
        "activity_type": "OBSERVATION", "activity_date": "2026-08-05",
    }, headers=intruder_headers)
    assert r.status_code == 404


def test_delete_crop_cascades_activities(client, farmer_headers):
    field_id = _create_field(client, farmer_headers)
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=farmer_headers)
    crop_id = r.json()["id"]
    client.post(f"/api/v1/crops/{crop_id}/activities", json={
        "activity_type": "PLANTING", "activity_date": "2026-08-01",
    }, headers=farmer_headers)

    r = client.delete(f"/api/v1/crops/{crop_id}", headers=farmer_headers)
    assert r.status_code == 204
    r = client.get(f"/api/v1/crops/{crop_id}", headers=farmer_headers)
    assert r.status_code == 404
