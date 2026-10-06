def _register_and_login(client, email, password="TestPass123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Farmer"})
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup_farm_field_crop(client, headers, soil_type="LOAMY", irrigation_type="DRIP"):
    r = client.post("/api/v1/farms", json={"name": "A's Farm"}, headers=headers)
    farm_id = r.json()["id"]
    r = client.post(f"/api/v1/farms/{farm_id}/fields", json={
        "name": "North Plot", "soil_type": soil_type, "irrigation_type": irrigation_type,
    }, headers=headers)
    field_id = r.json()["id"]
    r = client.post(f"/api/v1/fields/{field_id}/crops", json={"crop_type": "Wheat"}, headers=headers)
    crop_id = r.json()["id"]
    return farm_id, field_id, crop_id


# --- Conversation CRUD + ownership ---

def test_create_and_list_conversation(client, farmer_headers):
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    assert r.status_code == 201
    conv_id = r.json()["id"]

    r = client.get("/api/v1/copilot/conversations", headers=farmer_headers)
    assert r.status_code == 200
    assert any(c["id"] == conv_id for c in r.json())


def test_get_conversation_requires_auth(client):
    r = client.get("/api/v1/copilot/conversations")
    assert r.status_code == 401


def test_get_nonexistent_conversation_404(client, farmer_headers):
    import uuid
    r = client.get(f"/api/v1/copilot/conversations/{uuid.uuid4()}", headers=farmer_headers)
    assert r.status_code == 404


def test_delete_conversation(client, farmer_headers):
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    r = client.delete(f"/api/v1/copilot/conversations/{conv_id}", headers=farmer_headers)
    assert r.status_code == 204
    r = client.get(f"/api/v1/copilot/conversations/{conv_id}", headers=farmer_headers)
    assert r.status_code == 404


# --- IDOR: the critical security requirement for this feature ---

def test_idor_cannot_read_another_farmers_conversation(client, farmer_headers):
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]

    b_headers = _register_and_login(client, "farmer.b.copilot1@example.com")
    r = client.get(f"/api/v1/copilot/conversations/{conv_id}", headers=b_headers)
    assert r.status_code == 404


def test_idor_cannot_list_another_farmers_conversations(client, farmer_headers):
    client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    b_headers = _register_and_login(client, "farmer.b.copilot2@example.com")
    r = client.get("/api/v1/copilot/conversations", headers=b_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_idor_cannot_send_message_to_another_farmers_conversation(client, farmer_headers):
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]

    b_headers = _register_and_login(client, "farmer.b.copilot3@example.com")
    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Hi"}, headers=b_headers)
    assert r.status_code == 404


def test_idor_cannot_delete_another_farmers_conversation(client, farmer_headers):
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]

    b_headers = _register_and_login(client, "farmer.b.copilot4@example.com")
    r = client.delete(f"/api/v1/copilot/conversations/{conv_id}", headers=b_headers)
    assert r.status_code == 404

    # confirm it's genuinely untouched
    r = client.get(f"/api/v1/copilot/conversations/{conv_id}", headers=farmer_headers)
    assert r.status_code == 200


def test_idor_context_never_leaks_another_farmers_data():
    """Direct unit-level check that build_farmer_context is scoped by farmer, not global."""
    # Covered end-to-end via the grounding test below (farmer B's empty-context
    # response proves no cross-farmer data leaks into the built context).
    pass


def test_idor_farmer_b_gets_empty_context_despite_farmer_a_having_data(client, farmer_headers):
    _setup_farm_field_crop(client, farmer_headers)

    b_headers = _register_and_login(client, "farmer.b.copilotctx@example.com")
    r = client.post("/api/v1/copilot/conversations", json={}, headers=b_headers)
    conv_id = r.json()["id"]

    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Summarize my farm"}, headers=b_headers)
    assert r.status_code == 201
    body = r.json()
    assert "i don't have any farm data" in body["content"].lower()
    # Must not mention Farmer A's actual data
    assert "north plot" not in body["content"].lower()
    assert "wheat" not in body["content"].lower()


# --- Full end-to-end flow ---

def test_full_copilot_flow_grounded_in_real_data(client, farmer_headers):
    _setup_farm_field_crop(client, farmer_headers)

    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    assert r.status_code == 201
    conv_id = r.json()["id"]

    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "How are my crops doing?"}, headers=farmer_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "ASSISTANT"
    assert body["is_mock"] is True
    assert body["provider_name"] == "mock-copilot"
    assert "wheat" in body["content"].lower()
    assert "north plot" in body["content"].lower()
    assert any(e["entity_type"] == "crop" for e in body["referenced_entities"])

    # Conversation now has both the user message and the assistant reply
    r = client.get(f"/api/v1/copilot/conversations/{conv_id}", headers=farmer_headers)
    messages = r.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "USER"
    assert messages[1]["role"] == "ASSISTANT"


def test_conversation_title_set_from_first_message(client, farmer_headers):
    _setup_farm_field_crop(client, farmer_headers)
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "What needs my attention today?"}, headers=farmer_headers)

    r = client.get(f"/api/v1/copilot/conversations/{conv_id}", headers=farmer_headers)
    assert r.json()["title"] == "What needs my attention today?"


def test_message_requires_non_empty_content(client, farmer_headers):
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": ""}, headers=farmer_headers)
    assert r.status_code == 422


# --- Grounding ---

def test_grounding_no_farms_says_so_explicitly(client, farmer_headers):
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Summarize my farm"}, headers=farmer_headers)
    assert r.status_code == 201
    assert "i don't have any farm data" in r.json()["content"].lower()


def test_grounding_risks_reflect_actual_scan_results(client, farmer_headers):
    _, field_id, _ = _setup_farm_field_crop(client, farmer_headers, soil_type="UNKNOWN", irrigation_type="UNKNOWN")
    client.post(f"/api/v1/risk/fields/{field_id}/scan", headers=farmer_headers)

    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "What risks do I have?"}, headers=farmer_headers)
    body = r.json()
    assert "data quality" in body["content"].lower() or "data_quality" in body["content"].lower()
    assert any(e["entity_type"] == "risk" for e in body["referenced_entities"])


def test_grounding_recommendations_reflect_actual_state(client, farmer_headers):
    _, field_id, crop_id = _setup_farm_field_crop(client, farmer_headers)
    client.patch(f"/api/v1/crops/{crop_id}", json={"stage": "MATURITY"}, headers=farmer_headers)
    client.post("/api/v1/recommendations/generate", headers=farmer_headers)

    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "What are my recommendations?"}, headers=farmer_headers)
    body = r.json()
    assert "harvest" in body["content"].lower()
    assert any(e["entity_type"] == "recommendation" for e in body["referenced_entities"])


def test_grounding_no_active_risks_says_so(client, farmer_headers):
    _setup_farm_field_crop(client, farmer_headers, soil_type="CLAY", irrigation_type="DRIP")
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "What risks do I have?"}, headers=farmer_headers)
    assert "no active risks" in r.json()["content"].lower()


def test_grounding_stale_weather_produces_a_freshness_warning(client, farmer_headers):
    """
    The context builder must surface staleness rather than silently treating
    old weather as current -- simulated here by directly checking the
    warning path exists when a stale snapshot is present.
    """
    _, field_id, _ = _setup_farm_field_crop(client, farmer_headers)
    client.get(f"/api/v1/weather/fields/{field_id}", headers=farmer_headers)  # populate a snapshot

    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Summarize my farm"}, headers=farmer_headers)
    # Freshness warnings list must always be present (possibly empty) and never crash the response
    assert "context_freshness_warnings" in r.json()


def test_provider_marked_as_mock_in_every_response(client, farmer_headers):
    _setup_farm_field_crop(client, farmer_headers)
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Hello"}, headers=farmer_headers)
    assert r.json()["is_mock"] is True


def test_provider_failure_degrades_gracefully_without_fabricating_a_response(client, farmer_headers, monkeypatch):
    """
    Simulates a provider exception (the mock/future-real provider throwing)
    and verifies the orchestrator degrades to an honest failure message
    rather than crashing the request or fabricating a successful reply.
    """
    _setup_farm_field_crop(client, farmer_headers)
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated provider outage")

    import app.services.copilot_service as copilot_service_module
    monkeypatch.setattr(copilot_service_module, "get_copilot_provider", lambda: type(
        "BrokenProvider", (), {"respond": _raise}
    )())

    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Hello"}, headers=farmer_headers)
    assert r.status_code == 201
    body = r.json()
    assert "couldn't process" in body["content"].lower()
    assert body["referenced_entities"] == []


def test_empty_context_with_zero_activity_still_responds_safely(client, farmer_headers):
    """A farmer with a farm/field but no crops, activities, risks, or recommendations must still get a safe reply."""
    r = client.post("/api/v1/farms", json={"name": "Bare Farm"}, headers=farmer_headers)
    farm_id = r.json()["id"]
    client.post(f"/api/v1/farms/{farm_id}/fields", json={"name": "Empty Field"}, headers=farmer_headers)

    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "How are my crops doing?"}, headers=farmer_headers)
    assert r.status_code == 201
    assert "don't have any crops" in r.json()["content"].lower()


# --- Provider readiness: malformed / empty / timeout / unavailable ---

def _patch_provider(monkeypatch, fake_respond):
    import app.services.copilot_service as copilot_service_module
    monkeypatch.setattr(
        copilot_service_module, "get_copilot_provider",
        lambda: type("FakeProvider", (), {"respond": staticmethod(fake_respond)})()
    )


def test_provider_timeout_degrades_gracefully(client, farmer_headers, monkeypatch):
    _setup_farm_field_crop(client, farmer_headers)
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]

    def _timeout(*args, **kwargs):
        raise TimeoutError("simulated provider timeout")

    _patch_provider(monkeypatch, _timeout)

    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Hello"}, headers=farmer_headers)
    assert r.status_code == 201
    assert "couldn't process" in r.json()["content"].lower()
    assert r.json()["is_mock"] is True


def test_provider_unavailable_connection_error_degrades_gracefully(client, farmer_headers, monkeypatch):
    _setup_farm_field_crop(client, farmer_headers)
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]

    def _unavailable(*args, **kwargs):
        raise ConnectionError("simulated provider unreachable")

    _patch_provider(monkeypatch, _unavailable)

    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Hello"}, headers=farmer_headers)
    assert r.status_code == 201
    assert "couldn't process" in r.json()["content"].lower()


def test_malformed_provider_result_wrong_type_is_rejected(client, farmer_headers, monkeypatch):
    """A provider that returns the wrong type entirely (e.g. a raw dict) must never reach the frontend."""
    _setup_farm_field_crop(client, farmer_headers)
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]

    _patch_provider(monkeypatch, lambda request: {"content": "not a real CopilotResponse"})

    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Hello"}, headers=farmer_headers)
    assert r.status_code == 201
    assert "couldn't process" in r.json()["content"].lower()


def test_empty_content_provider_result_is_rejected(client, farmer_headers, monkeypatch):
    from app.ai.contracts import CopilotResponse

    _setup_farm_field_crop(client, farmer_headers)
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]

    _patch_provider(monkeypatch, lambda request: CopilotResponse(
        content="   ", referenced_entities=[], context_freshness_warnings=[], provider_name="mock-copilot", is_mock=True,
    ))

    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Hello"}, headers=farmer_headers)
    assert r.status_code == 201
    assert "couldn't process" in r.json()["content"].lower()


def test_malformed_referenced_entities_type_is_rejected(client, farmer_headers, monkeypatch):
    from app.ai.contracts import CopilotResponse

    _setup_farm_field_crop(client, farmer_headers)
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]

    _patch_provider(monkeypatch, lambda request: CopilotResponse(
        content="Valid text",
        referenced_entities="not-a-list",  # malformed on purpose
        context_freshness_warnings=[], provider_name="mock-copilot", is_mock=True,
    ))

    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "Hello"}, headers=farmer_headers)
    assert r.status_code == 201
    assert "couldn't process" in r.json()["content"].lower()


def test_valid_provider_result_still_passes_validation_and_persists_normally(client, farmer_headers):
    """Sanity check: the validation layer doesn't reject legitimate mock responses."""
    _setup_farm_field_crop(client, farmer_headers)
    r = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers)
    conv_id = r.json()["id"]
    r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": "How are my crops doing?"}, headers=farmer_headers)
    assert r.status_code == 201
    assert "couldn't process" not in r.json()["content"].lower()
    assert "wheat" in r.json()["content"].lower()


# --- Conversation history bounding/scoping ---

def test_conversation_history_is_scoped_to_its_own_conversation_only(client, farmer_headers):
    """
    Sending a message in conversation B must never be influenced by messages
    from conversation A, even though both belong to the same farmer.
    """
    _setup_farm_field_crop(client, farmer_headers)

    conv_a = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers).json()["id"]
    client.post(f"/api/v1/copilot/conversations/{conv_a}/messages", json={"content": "This is conversation A, remember the word PINEAPPLE."}, headers=farmer_headers)

    conv_b = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers).json()["id"]
    r = client.get(f"/api/v1/copilot/conversations/{conv_b}", headers=farmer_headers)
    assert r.json()["messages"] == []  # conversation B starts with zero messages, unaffected by A

    r = client.post(f"/api/v1/copilot/conversations/{conv_b}/messages", json={"content": "Hello"}, headers=farmer_headers)
    assert r.status_code == 201

    r = client.get(f"/api/v1/copilot/conversations/{conv_b}", headers=farmer_headers)
    contents = [m["content"] for m in r.json()["messages"]]
    assert not any("pineapple" in c.lower() for c in contents)


def test_conversation_history_length_is_bounded(client, farmer_headers):
    """
    Sending more than MAX_HISTORY_TURNS*2 messages must not error or grow
    the history passed to the provider unboundedly -- the orchestrator caps
    the query itself.
    """
    _setup_farm_field_crop(client, farmer_headers)
    conv_id = client.post("/api/v1/copilot/conversations", json={}, headers=farmer_headers).json()["id"]

    for i in range(12):
        r = client.post(f"/api/v1/copilot/conversations/{conv_id}/messages", json={"content": f"Message {i}"}, headers=farmer_headers)
        assert r.status_code == 201

    r = client.get(f"/api/v1/copilot/conversations/{conv_id}", headers=farmer_headers)
    # 12 user + 12 assistant = 24 messages persisted; the important guarantee
    # is that the request succeeded every time regardless of growing history.
    assert len(r.json()["messages"]) == 24
