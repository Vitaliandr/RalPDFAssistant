import json
from typing import Any

import httpx
import pytest

from ralpdfassistant.clients.llm import ask_llm
from ralpdfassistant.errors import LlmUnavailable
from ralpdfassistant.settings import settings


def client_with(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_normal_answer():
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.read())
        return httpx.Response(200, json={"choices": [{"message": {"content": "  99 рублей \n"}}]})

    answer = ask_llm("сколько?", "контекст про карту", client_with(handler))
    assert answer == "99 рублей"
    assert seen["url"].endswith("/chat/completions")
    user_message = seen["body"]["messages"][1]["content"]
    assert "контекст про карту" in user_message
    assert "сколько?" in user_message


def test_key_goes_to_header(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "secret-key")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ок"}}]})

    ask_llm("q", "c", client_with(handler))
    assert seen["auth"] == "Bearer secret-key"


@pytest.mark.parametrize(
    ("code", "part"),
    [(401, "ключ"), (403, "ключ"), (429, "лимит"), (404, "модель"), (500, "ошибку 500")],
)
def test_provider_errors_become_readable(code, part):
    with pytest.raises(LlmUnavailable) as e:
        ask_llm("q", "c", client_with(lambda r: httpx.Response(code, json={})))
    assert part in e.value.message


def test_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("нет связи")

    with pytest.raises(LlmUnavailable) as e:
        ask_llm("q", "c", client_with(handler))
    assert "ollama" in e.value.message


def test_weird_answer_format():
    with pytest.raises(LlmUnavailable):
        ask_llm("q", "c", client_with(lambda r: httpx.Response(200, json={"oops": 1})))


def test_not_json():
    with pytest.raises(LlmUnavailable):
        ask_llm("q", "c", client_with(lambda r: httpx.Response(200, text="не json")))


def test_own_client_is_created_and_closed(monkeypatch):
    closed = []

    class FakeClient:
        def post(self, url, json, headers):
            body = {"choices": [{"message": {"content": "ок"}}]}
            return httpx.Response(200, json=body, request=httpx.Request("POST", url))

        def close(self):
            closed.append(True)

    monkeypatch.setattr(httpx, "Client", lambda timeout: FakeClient())
    assert ask_llm("q", "c") == "ок"
    assert closed == [True]
