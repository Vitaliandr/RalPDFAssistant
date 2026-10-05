from ralpdfassistant import logs


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_security_headers(client):
    h = client.get("/").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert "script-src 'self'" in h["content-security-policy"]


def test_swagger_is_not_blocked_by_csp(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "content-security-policy" not in r.headers


def test_frontend_is_served_in_russian(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "RalPDFAssistant" in r.text
    assert r.headers["cache-control"] == "no-cache"


def test_request_id_is_returned(client):
    r = client.get("/health")
    assert len(r.headers["x-request-id"]) == 12


def test_good_request_id_is_kept(client):
    r = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


def test_bad_request_id_is_replaced(client):
    r = client.get("/health", headers={"X-Request-ID": "evil\nline"})
    assert r.headers["x-request-id"] != "evil\nline"


def test_new_request_id_rules():
    assert logs.new_request_id(None) != logs.new_request_id(None)
    assert logs.new_request_id("a" * 100) != "a" * 100


def test_validation_error_in_russian(client):
    r = client.post("/api/documents/text", json={"title": "x"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Текст: обязательное поле"


def test_wrong_type_in_russian(client):
    r = client.post("/api/ask", json={"question": "q", "document_ids": "не список"})
    assert r.status_code == 422
    assert "Документы" in r.json()["detail"]


def test_json_logs_format():
    import json
    import logging

    logs.setup(as_json=True)
    try:
        record = logging.LogRecord("t", logging.INFO, "f.py", 1, "привет %s", ("мир",), None)
        handler = logging.getLogger().handlers[0]
        data = json.loads(handler.format(record))
        assert data["msg"] == "привет мир"
        assert data["level"] == "INFO"
    finally:
        logs.setup(as_json=False)
