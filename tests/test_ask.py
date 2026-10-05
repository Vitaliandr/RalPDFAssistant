from tests.conftest import add_text


def ask(client, question, ids=None):
    return client.post("/api/ask", json={"question": question, "document_ids": ids})


def fill(client, process):
    card = add_text(client, "Тарифы карты", "Обслуживание карты стоит 99 рублей в месяц. Снятие наличных бесплатно.")
    deposit = add_text(client, "Условия вклада", "Вклад Надёжный открывается на 12 месяцев под 14 процентов годовых.")
    process()
    return card, deposit


def test_answer_comes_from_llm(client, process, llm):
    fill(client, process)
    llm.answer = "99 рублей в месяц"

    r = ask(client, "сколько стоит обслуживание карты?")
    assert r.status_code == 200
    assert r.json()["answer"] == "99 рублей в месяц"


def test_best_source_is_first(client, process):
    fill(client, process)
    sources = ask(client, "сколько стоит обслуживание карты?").json()["sources"]
    assert sources[0]["document"] == "Тарифы карты"
    assert sources[0]["score"] > sources[-1]["score"]


def test_context_for_llm_has_numbers_and_titles(client, process, llm):
    fill(client, process)
    ask(client, "под какой процент вклад?")

    question, context = llm.calls[0]
    assert question == "под какой процент вклад?"
    assert "[1] (Условия вклада)" in context
    assert "14 процентов" in context


def test_filter_by_document(client, process):
    card, deposit = fill(client, process)
    sources = ask(client, "сколько стоит обслуживание карты?", [deposit]).json()["sources"]
    assert {s["document"] for s in sources} == {"Условия вклада"}


def test_pdf_page_in_source(client, process):
    from tests.conftest import make_pdf

    pdf = make_pdf(["Overview of the product", "Penalty for late payment is 590 rubles"])
    client.post("/api/documents", files={"file": ("cards.pdf", pdf, "application/pdf")})
    process()

    hit = ask(client, "penalty for late payment").json()["sources"][0]
    assert hit["page"] == 2
    assert hit["document"] == "cards.pdf"


def test_no_documents(client, llm):
    r = ask(client, "что угодно")
    assert r.status_code == 200
    assert "нет готовых документов" in r.json()["answer"]
    assert r.json()["sources"] == []
    assert llm.calls == []


def test_unready_documents_are_not_searched(client, llm):
    add_text(client, "ещё в очереди", "обслуживание карты стоит 99 рублей")
    r = ask(client, "обслуживание карты")
    assert r.json()["sources"] == []
    assert llm.calls == []


def test_empty_question(client):
    assert ask(client, "   ").status_code == 400


def test_question_is_required(client):
    r = client.post("/api/ask", json={})
    assert r.status_code == 422
    assert r.json()["detail"] == "Вопрос: обязательное поле"


def test_top_k_limits_sources(client, process, monkeypatch):
    from ralpdfassistant.settings import settings

    monkeypatch.setattr(settings, "top_k", 2)
    for i in range(4):
        add_text(client, f"док {i}", f"документ номер {i} про обслуживание карты")
    process()
    assert len(ask(client, "обслуживание карты").json()["sources"]) == 2
