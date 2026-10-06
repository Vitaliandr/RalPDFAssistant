import logging

from ralpdfassistant.clients.llm import ask_llm
from ralpdfassistant.deps import llm_dep
from ralpdfassistant.errors import LlmUnavailable
from ralpdfassistant.main import app
from ralpdfassistant.settings import settings
from tests.conftest import add_text


def test_local_and_groq_listed_without_keys(client):
    r = client.get("/api/models")
    assert r.status_code == 200
    models = {m["id"]: m for m in r.json()}
    assert list(models) == ["ollama", "groq"]
    assert models["ollama"]["default"] is True
    assert models["ollama"]["label"] == "Локально (Ollama)"
    #ключа в .env нет, интерфейс должен показать поле для своего
    assert models["ollama"]["needs_key"] is False
    assert models["groq"]["needs_key"] is True
    assert models["groq"]["cloud"] is True and models["groq"]["server_key"] is False
    assert models["ollama"]["cloud"] is False


def test_groq_with_key_in_env_needs_nothing(client, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "k")
    monkeypatch.setattr(settings, "default_llm", "groq")

    models = {m["id"]: m for m in client.get("/api/models").json()}
    assert models["groq"]["default"] is True
    assert models["groq"]["needs_key"] is False
    assert models["groq"]["server_key"] is True
    assert models["ollama"]["default"] is False
    assert "файлы целиком не уходят" in models["groq"]["note"]


def test_server_key_value_is_never_exposed(client, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "gsk_server_secret_value")
    monkeypatch.setattr(settings, "default_llm", "groq")

    r = client.get("/api/models")
    assert "gsk_server_secret_value" not in r.text


def test_chosen_model_reaches_llm_and_is_reported(client, process, llm):
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()

    r = client.post("/api/ask", json={"question": "обслуживание карты", "model": "ollama"})
    assert r.status_code == 200
    assert r.json()["model"] == "ollama"
    assert llm.models == ["ollama"]


def test_default_model_reported_when_not_chosen(client, process, llm):
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()

    r = client.post("/api/ask", json={"question": "обслуживание карты"})
    assert r.json()["model"] == settings.default_llm
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


def test_cloud_model_without_any_key_gives_readable_error(client, process):
    #тут нужен настоящий ask_llm, чтобы проверить отказ для облачной модели без ключа
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
