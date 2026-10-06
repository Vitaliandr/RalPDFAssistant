import logging

from ralpdfassistant.clients.llm import ask_llm
from ralpdfassistant.deps import llm_dep
from ralpdfassistant.errors import LlmUnavailable
from ralpdfassistant.main import app
from tests.conftest import add_text


def test_two_models_local_is_default(client):
    r = client.get("/api/models")
    assert r.status_code == 200
    models = {m["id"]: m for m in r.json()}
    assert list(models) == ["ollama", "groq"]
    assert models["ollama"]["default"] is True
    assert models["ollama"]["label"] == "Локально (Ollama)"
    assert models["ollama"]["cloud"] is False
    assert models["groq"]["default"] is False
    assert models["groq"]["cloud"] is True
    assert "файлы целиком не уходят" in models["groq"]["note"]


def test_models_list_has_no_server_key_fields(client):
    for model in client.get("/api/models").json():
        assert set(model) == {"id", "label", "note", "default", "cloud"}


def test_chosen_model_reaches_llm_and_is_reported(client, process, llm):
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()

    r = client.post("/api/ask", json={"question": "обслуживание карты", "model": "ollama"})
    assert r.status_code == 200
    assert r.json()["model"] == "ollama"
    assert llm.models == ["ollama"]


def test_local_model_reported_when_not_chosen(client, process, llm):
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()

    r = client.post("/api/ask", json={"question": "обслуживание карты"})
    assert r.json()["model"] == "ollama"
    assert llm.models == [None]


def test_key_from_header_reaches_llm(client, process, llm):
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()

    r = client.post(
        "/api/ask", json={"question": "обслуживание карты", "model": "groq"}, headers={"X-LLM-Key": "gsk_secret"}
    )
    assert r.status_code == 200
    assert llm.keys == ["gsk_secret"]
    assert "gsk_secret" not in r.text


def test_no_header_means_no_key(client, process, llm):
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()

    client.post("/api/ask", json={"question": "обслуживание карты"})
    assert llm.keys == [None]


def test_key_never_appears_in_logs(client, process, llm, caplog):
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()
    llm.error = LlmUnavailable("Провайдер не принял ключ, проверь его")

    with caplog.at_level(logging.DEBUG):
        r = client.post(
            "/api/ask", json={"question": "обслуживание карты", "model": "groq"}, headers={"X-LLM-Key": "gsk_secret"}
        )
    assert r.status_code == 502
    assert "gsk_secret" not in caplog.text
    assert "gsk_secret" not in r.text


def test_cloud_model_without_key_gives_readable_error(client, process):
    #нужен настоящий ask_llm
    app.dependency_overrides[llm_dep] = lambda: ask_llm
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()

    r = client.post("/api/ask", json={"question": "обслуживание карты", "model": "groq"})
    assert r.status_code == 400
    assert "нужен ключ" in r.json()["detail"]


def test_unknown_model_gives_readable_error(client, process):
    app.dependency_overrides[llm_dep] = lambda: ask_llm
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()

    r = client.post("/api/ask", json={"question": "обслуживание карты", "model": "gpt-17"})
    assert r.status_code == 400
    assert "недоступна" in r.json()["detail"]
