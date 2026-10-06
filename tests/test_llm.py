import json
from typing import Any

import httpx
import pytest

from ralpdfassistant.clients.llm import ask_llm
from ralpdfassistant.errors import AppError, LlmUnavailable
from ralpdfassistant.settings import settings

OK = {"choices": [{"message": {"content": "ок"}}]}


def client_with(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_normal_answer():
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.read())
        return httpx.Response(200, json={"choices": [{"message": {"content": "  99 рублей \n"}}]})

    answer = ask_llm("сколько?", "контекст про карту", client=client_with(handler))
    assert answer == "99 рублей"
    assert seen["url"].endswith("/chat/completions")
    user_message = seen["body"]["messages"][1]["content"]
    assert "контекст про карту" in user_message
    assert "сколько?" in user_message


def test_local_model_gets_no_auth_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        seen["model"] = json.loads(request.read())["model"]
        return httpx.Response(200, json=OK)

    ask_llm("q", "c", "ollama", client=client_with(handler))
    assert seen["auth"] is None
    assert "11434" in seen["url"]
    assert seen["model"] == settings.ollama_model


def test_groq_goes_to_groq_with_key(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "secret-key")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        seen["model"] = json.loads(request.read())["model"]
        return httpx.Response(200, json=OK)

    ask_llm("q", "c", "groq", client=client_with(handler))
    assert seen["auth"] == "Bearer secret-key"
    assert seen["url"].startswith("https://api.groq.com/")
    assert seen["model"] == settings.groq_model


def test_users_own_key_works_without_key_in_env():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=OK)

    ask_llm("q", "c", "groq", "gsk_userkey", client_with(handler))
    assert seen["auth"] == "Bearer gsk_userkey"


def test_users_key_beats_key_from_env(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "from-env")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=OK)

    ask_llm("q", "c", "groq", "gsk_userkey", client_with(handler))
    assert seen["auth"] == "Bearer gsk_userkey"


def test_users_key_is_not_sent_to_local_model():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=OK)

    ask_llm("q", "c", "ollama", "gsk_userkey", client_with(handler))
    assert seen["auth"] is None


@pytest.mark.parametrize("bad", ["gsk abc", "gsk_\nabc", "a" * 300, "   ", "gsk_\tabc"])
def test_weird_keys_are_refused(bad):
    #все эти ключи отсекаются проверкой формата, до запроса к провайдеру дело не доходит
    with pytest.raises(AppError):
        ask_llm("q", "c", "groq", bad, client_with(lambda r: httpx.Response(200, json=OK)))


def test_key_with_spaces_around_is_trimmed():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=OK)

    ask_llm("q", "c", "groq", "  gsk_userkey \n", client_with(handler))
    assert seen["auth"] == "Bearer gsk_userkey"


def test_rejected_users_key_says_check_your_key():
    with pytest.raises(LlmUnavailable) as e:
        ask_llm("q", "c", "groq", "gsk_bad", client_with(lambda r: httpx.Response(401, json={})))
    assert e.value.message == "Провайдер не принял ключ, проверь его"
    assert "gsk_bad" not in e.value.message


def test_default_model_is_used_when_not_asked(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "k")
    monkeypatch.setattr(settings, "default_llm", "groq")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=OK)

    ask_llm("q", "c", None, client=client_with(handler))
    assert "groq.com" in seen["url"]


def test_cloud_model_without_key_is_refused():
    with pytest.raises(AppError) as e:
        ask_llm("q", "c", "groq", client=client_with(lambda r: httpx.Response(200, json=OK)))
    assert "нужен ключ" in e.value.message


def test_unknown_model_is_refused():
    with pytest.raises(AppError):
        ask_llm("q", "c", "gpt-17", client=client_with(lambda r: httpx.Response(200, json=OK)))


@pytest.mark.parametrize(
    ("code", "part"),
    [(401, "ключ"), (403, "ключ"), (429, "лимит"), (500, "ошибку 500")],
)
def test_provider_errors_become_readable(code, part):
    with pytest.raises(LlmUnavailable) as e:
        ask_llm("q", "c", client=client_with(lambda r: httpx.Response(code, json={})))
    assert part in e.value.message


def test_local_model_unreachable_tells_what_to_do():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("нет связи")

    with pytest.raises(LlmUnavailable) as e:
        ask_llm("q", "c", "ollama", client=client_with(handler))
    #новый человек должен узнать два выхода: поставить ollama или взять облако со своим ключом
    assert "Запусти Ollama" in e.value.message
    assert f"ollama pull {settings.ollama_model}" in e.value.message
    assert "Groq" in e.value.message


def test_cloud_unreachable_mentions_internet(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("нет связи")

    with pytest.raises(LlmUnavailable) as e:
        ask_llm("q", "c", "groq", "gsk_userkey", client=client_with(handler))
    assert "интернет" in e.value.message


def test_cloud_does_not_know_model():
    with pytest.raises(LlmUnavailable) as e:
        ask_llm("q", "c", "groq", "gsk_userkey", client=client_with(lambda r: httpx.Response(404, json={})))
    assert "название модели" in e.value.message


def test_model_not_pulled_in_ollama():
    with pytest.raises(LlmUnavailable) as e:
        ask_llm("q", "c", "ollama", client=client_with(lambda r: httpx.Response(404, json={})))
    assert f"ollama pull {settings.ollama_model}" in e.value.message


def test_weird_answer_format():
    with pytest.raises(LlmUnavailable):
        ask_llm("q", "c", client=client_with(lambda r: httpx.Response(200, json={"oops": 1})))


def test_not_json():
    with pytest.raises(LlmUnavailable):
        ask_llm("q", "c", client=client_with(lambda r: httpx.Response(200, text="не json")))


def test_own_client_is_created_and_closed(monkeypatch):
    closed = []

    class FakeClient:
        def post(self, url, json, headers):
            return httpx.Response(200, json=OK, request=httpx.Request("POST", url))

        def close(self):
            closed.append(True)

    monkeypatch.setattr(httpx, "Client", lambda timeout: FakeClient())
    assert ask_llm("q", "c") == "ок"
    assert closed == [True]
