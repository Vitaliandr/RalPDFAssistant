from ralpdfassistant.errors import LlmUnavailable
from tests.conftest import add_text


def test_llm_error_is_502_with_text(client, process, llm):
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()
    llm.error = LlmUnavailable("Упёрлись в лимит бесплатного тарифа, подожди минуту")

    r = client.post("/api/ask", json={"question": "обслуживание карты"})
    assert r.status_code == 502
    assert "лимит" in r.json()["detail"]


def test_500_hides_details(client, process, llm):
    add_text(client, "Тарифы", "обслуживание карты стоит 99 рублей")
    process()
    llm.error = RuntimeError("секретная деталь устройства сервера")

    r = client.post("/api/ask", json={"question": "обслуживание карты"})
    assert r.status_code == 500
    assert "секретная" not in r.text
    assert "внутренняя ошибка" in r.json()["detail"]
