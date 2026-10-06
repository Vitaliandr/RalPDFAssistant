from ralpdfassistant.core import ask
from ralpdfassistant.repositories.chunks import Hit
from tests.conftest import HashEmbedder, add_text


def hit(i: int, score: float = 0.5) -> Hit:
    return Hit(id=i, title="t", page=None, text=f"текст {i}", score=score)


def test_keywords_drop_stop_words():
    assert ask.keywords("Какой чистый убыток за период?") == "чистый | убыток | период"


def test_keywords_without_duplicates():
    assert ask.keywords("убыток убыток Убыток") == "убыток"


def test_keywords_only_stop_words():
    assert ask.keywords("Что это? Кто там") == "там"
    assert ask.keywords("Что это?") == ""


def test_fuse_prefers_item_found_by_both():
    #id=2 есть в обоих списках
    fused = ask.fuse([hit(1), hit(2), hit(3)], [hit(4), hit(2)], limit=5)
    assert fused[0].id == 2


def test_fuse_respects_limit_and_has_no_duplicates():
    fused = ask.fuse([hit(1), hit(2), hit(3)], [hit(3), hit(4), hit(1)], limit=3)
    assert len(fused) == 3
    assert len({h.id for h in fused}) == 3


def test_fuse_with_empty_lists():
    assert ask.fuse([], [], limit=5) == []
    assert [h.id for h in ask.fuse([hit(1), hit(2)], [], limit=5)] == [1, 2]


def test_word_search_knows_word_forms(client, process, session):
    # вкладе и вкладу, postgres склеит
    add_text(client, "Вклад", "Ставка по вкладу четырнадцать процентов")
    add_text(client, "Погода", "Сегодня солнечно и тепло на улице")
    process()

    found = ask.retrieve(session, HashEmbedder(), "что в вкладе?", None, limit=2, hybrid=True)
    assert found[0].title == "Вклад"


def test_hybrid_off_is_plain_vector_search(client, process, session):
    add_text(client, "Тарифы", "Обслуживание карты стоит 99 рублей")
    add_text(client, "Вклад", "Ставка по вкладу четырнадцать процентов")
    process()

    found = ask.retrieve(session, HashEmbedder(), "обслуживание карты", None, hybrid=False)
    assert found[0].title == "Тарифы"


def test_word_search_respects_document_filter(client, process, session):
    first = add_text(client, "Первый", "Штраф за просрочку платежа пятьсот рублей")
    second = add_text(client, "Второй", "Штраф за просрочку займа тысяча рублей")
    process()

    found = ask.retrieve(session, HashEmbedder(), "штраф за просрочку", [second], hybrid=True)
    assert {h.title for h in found} == {"Второй"}
    assert first not in [h.id for h in found]


def test_only_stop_words_falls_back_to_vectors(client, process, session):
    add_text(client, "Тарифы", "Обслуживание карты стоит 99 рублей")
    process()

    found = ask.retrieve(session, HashEmbedder(), "что это", None, hybrid=True)
    assert len(found) == 1


def test_hybrid_through_api(client, process):
    add_text(client, "Вклад", "Ставка по вкладу четырнадцать процентов")
    add_text(client, "Погода", "Сегодня солнечно и тепло на улице")
    process()

    r = client.post("/api/ask", json={"question": "что в вкладе?"})
    assert r.json()["sources"][0]["document"] == "Вклад"
