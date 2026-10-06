def _create_farm(client, headers, name="Farm"):
    r = client.post("/api/v1/farms", json={"name": name}, headers=headers)
    return r.json()["id"]


def test_create_field_under_farm(client, farmer_headers):
    farm_id = _create_farm(client, farmer_headers)
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field A", "area_acres": 2.5, "soil_type": "CLAY", "irrigation_type": "FLOOD",
    }, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json()["soil_type"] == "CLAY"
    assert r.json()["crop_count"] == 0


def test_create_field_under_nonexistent_farm_404(client, farmer_headers):
    import uuid
    r = client.post(f"/api/v1/farms/{uuid.uuid4()}/fields", json={"name": "Orphan"}, headers=farmer_headers)
    assert r.status_code == 404


def test_field_visible_via_farm_field_count(client, farmer_headers):
    farm_id = _create_farm(client, farmer_headers)
    client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "F1"}, headers=farmer_headers)
    client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "F2"}, headers=farmer_headers)
    r = client.get(f"/api/v1/farms/{farm_id}", headers=farmer_headers)
    assert r.json()["field_count"] == 2


def test_create_field_with_canal_irrigation(client, farmer_headers):
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Canal Field", "soil_type": "CLAY", "irrigation_type": "CANAL",
    }, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json()["irrigation_type"] == "CANAL"


def test_create_field_with_tubewell_irrigation(client, farmer_headers):
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Tubewell Field", "soil_type": "LOAMY", "irrigation_type": "TUBEWELL",
    }, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json()["irrigation_type"] == "TUBEWELL"


def test_invalid_irrigation_type_rejected(client, farmer_headers):
    r = client.post("/api/v1/farms", json={"name": "Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Bad Field", "irrigation_type": "SOLAR_PUMP",
    }, headers=farmer_headers)
    assert r.status_code == 422


def test_field_ownership_enforced_across_farmers(client, farmer_headers):
    farm_id = _create_farm(client, farmer_headers)
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "Private Field"}, headers=farmer_headers)
    field_id = r.json()["id"]

    client.post("/api/v1/auth/register", json={
        "email": "intruder@example.com", "password": "IntruderPass1", "full_name": "Intruder",
    })
    r = client.post("/api/v1/auth/login", data={"username": "intruder@example.com", "password": "IntruderPass1"})
    intruder_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get(f"/api/v1/fields/{field_id}", headers=intruder_headers)
    assert r.status_code == 404


# --- Field creation with initial crops ---

def test_create_field_with_initial_crops_persists_them(client, farmer_headers):
    farm_id = _create_farm(client, farmer_headers)
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "North Field", "soil_type": "LOAMY", "irrigation_type": "CANAL",
        "initial_crop_types": ["Wheat", "Rice"],
    }, headers=farmer_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["crop_count"] == 2
    crop_types = sorted(c["crop_type"] for c in body["crops"])
    assert crop_types == ["Rice", "Wheat"]


def test_field_crops_survive_fresh_get_request(client, farmer_headers):
    farm_id = _create_farm(client, farmer_headers)
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field", "initial_crop_types": ["Wheat", "Rice", "Cotton"],
    }, headers=farmer_headers)
    field_id = r.json()["id"]

    r = client.get(f"/api/v1/fields/{field_id}", headers=farmer_headers)
    assert r.status_code == 200
    assert r.json()["crop_count"] == 3
    assert sorted(c["crop_type"] for c in r.json()["crops"]) == ["Cotton", "Rice", "Wheat"]

    r = client.get(f"/api/v1/fields/{field_id}/crops", headers=farmer_headers)
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_create_field_without_crops_still_works(client, farmer_headers):
    farm_id = _create_farm(client, farmer_headers)
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "Empty Field"}, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json()["crop_count"] == 0
    assert r.json()["crops"] == []


def test_create_field_rejects_blank_crop_type(client, farmer_headers):
    farm_id = _create_farm(client, farmer_headers)
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field", "initial_crop_types": ["Wheat", "   "],
    }, headers=farmer_headers)
    assert r.status_code == 422


def test_create_field_dedupes_repeated_crop_types(client, farmer_headers):
    farm_id = _create_farm(client, farmer_headers)
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field", "initial_crop_types": ["Wheat", "wheat", "WHEAT"],
    }, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json()["crop_count"] == 1


def test_new_field_crops_are_not_visible_to_another_farmer(client, farmer_headers):
    farm_id = _create_farm(client, farmer_headers)
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "Field", "initial_crop_types": ["Wheat"],
    }, headers=farmer_headers)
    field_id = r.json()["id"]

    client.post("/api/v1/auth/register", json={
        "email": "field.crops.intruder@example.com", "password": "IntruderPass1", "full_name": "Intruder",
    })
    r = client.post("/api/v1/auth/login", data={"username": "field.crops.intruder@example.com", "password": "IntruderPass1"})
    intruder_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get(f"/api/v1/fields/{field_id}", headers=intruder_headers)
    assert r.status_code == 404
    r = client.get(f"/api/v1/fields/{field_id}/crops", headers=intruder_headers)
    assert r.status_code == 404
