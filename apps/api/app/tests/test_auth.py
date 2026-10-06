def test_register_creates_farmer(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "alice@example.com", "password": "StrongPass1", "full_name": "Alice",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["full_name"] == "Alice"
    assert body["user"]["role"] == "FARMER"
    assert body["user"]["is_active"] is True


def test_register_duplicate_email_rejected(client):
    payload = {"email": "dup@example.com", "password": "StrongPass1", "full_name": "Dup"}
    r1 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


def test_register_short_password_rejected(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "short@example.com", "password": "short", "full_name": "Short Pass",
    })
    assert r.status_code == 422


def test_login_success_returns_token(client):
    client.post("/api/v1/auth/register", json={
        "email": "bob@example.com", "password": "StrongPass1", "full_name": "Bob",
    })
    r = client.post("/api/v1/auth/login", data={"username": "bob@example.com", "password": "StrongPass1"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password_rejected(client):
    client.post("/api/v1/auth/register", json={
        "email": "carol@example.com", "password": "StrongPass1", "full_name": "Carol",
    })
    r = client.post("/api/v1/auth/login", data={"username": "carol@example.com", "password": "WrongPass1"})
    assert r.status_code == 401


def test_login_nonexistent_user_rejected(client):
    r = client.post("/api/v1/auth/login", data={"username": "ghost@example.com", "password": "whatever123"})
    assert r.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_returns_current_user(client, farmer_headers):
    r = client.get("/api/v1/auth/me", headers=farmer_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "test.farmer@example.com"


def test_invalid_token_rejected(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
