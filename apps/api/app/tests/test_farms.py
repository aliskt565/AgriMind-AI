def test_create_and_list_farm(client, farmer_headers):
    r = client.post("/api/v1/farms", json={"name": "Test Farm", "total_area_acres": 10}, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json()["field_count"] == 0

    r = client.get("/api/v1/farms", headers=farmer_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_create_farm_requires_auth(client):
    r = client.post("/api/v1/farms", json={"name": "No Auth Farm"})
    assert r.status_code == 401


def test_create_farm_validates_name(client, farmer_headers):
    r = client.post("/api/v1/farms", json={"name": ""}, headers=farmer_headers)
    assert r.status_code == 422


def test_update_farm(client, farmer_headers):
    r = client.post("/api/v1/farms", json={"name": "Original"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.patch(f"/api/v1/farms/{farm_id}", json={"name": "Renamed"}, headers=farmer_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"


def test_update_farm_persists_all_editable_fields(client, farmer_headers):
    r = client.post("/api/v1/farms", json={"name": "Original", "total_area_acres": 5, "location": "Old Location"}, headers=farmer_headers)
    farm_id = r.json()["id"]

    r = client.patch(f"/api/v1/farms/{farm_id}", json={
        "name": "Updated Name", "total_area_acres": 20, "location": "New Location",
    }, headers=farmer_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Name"
    assert r.json()["total_area_acres"] == 20
    assert r.json()["location"] == "New Location"

    r = client.get(f"/api/v1/farms/{farm_id}", headers=farmer_headers)
    assert r.json()["name"] == "Updated Name"
    assert r.json()["total_area_acres"] == 20
    assert r.json()["location"] == "New Location"


def test_update_farm_does_not_create_a_duplicate(client, farmer_headers):
    client.post("/api/v1/farms", json={"name": "Original"}, headers=farmer_headers)
    r = client.get("/api/v1/farms", headers=farmer_headers)
    farm_id = r.json()[0]["id"]
    assert len(r.json()) == 1

    client.patch(f"/api/v1/farms/{farm_id}", json={"name": "Renamed"}, headers=farmer_headers)

    r = client.get("/api/v1/farms", headers=farmer_headers)
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == farm_id
    assert r.json()[0]["name"] == "Renamed"


def test_farmer_cannot_update_another_farmers_farm(client, farmer_headers):
    r = client.post("/api/v1/farms", json={"name": "A's Farm", "location": "A's Location"}, headers=farmer_headers)
    farm_id = r.json()["id"]

    client.post("/api/v1/auth/register", json={
        "email": "farm.edit.intruder@example.com", "password": "IntruderPass1", "full_name": "Intruder",
    })
    r = client.post("/api/v1/auth/login", data={"username": "farm.edit.intruder@example.com", "password": "IntruderPass1"})
    intruder_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.patch(f"/api/v1/farms/{farm_id}", json={"name": "Hijacked"}, headers=intruder_headers)
    assert r.status_code == 404

    r = client.get(f"/api/v1/farms/{farm_id}", headers=farmer_headers)
    assert r.json()["name"] == "A's Farm"
    assert r.json()["location"] == "A's Location"


def test_delete_farm(client, farmer_headers):
    r = client.post("/api/v1/farms", json={"name": "To Delete"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    r = client.delete(f"/api/v1/farms/{farm_id}", headers=farmer_headers)
    assert r.status_code == 204
    r = client.get(f"/api/v1/farms/{farm_id}", headers=farmer_headers)
    assert r.status_code == 404


def test_farmer_cannot_access_another_farmers_farm(client, farmer_headers):
    """Core authorization boundary: ownership is enforced server-side."""
    r = client.post("/api/v1/farms", json={"name": "Farmer A's Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]

    client.post("/api/v1/auth/register", json={
        "email": "other.farmer@example.com", "password": "OtherPass1", "full_name": "Other Farmer",
    })
    r = client.post("/api/v1/auth/login", data={"username": "other.farmer@example.com", "password": "OtherPass1"})
    other_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get(f"/api/v1/farms/{farm_id}", headers=other_headers)
    assert r.status_code == 404  # not 403 -- existence is not leaked either

    r = client.get("/api/v1/farms", headers=other_headers)
    assert r.status_code == 200
    assert len(r.json()) == 0
