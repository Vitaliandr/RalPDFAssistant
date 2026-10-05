from ralpdfassistant.core.chunker import split_text


def test_empty_text():
    assert split_text("   \n\n  ") == []


def test_short_text_is_one_chunk():
    chunks = split_text("Комиссия за обслуживание 100 рублей. Снятие бесплатно.")
    assert len(chunks) == 1


def test_chunks_not_longer_than_size():
    text = " ".join(f"Предложение номер {i} про тарифы." for i in range(200))
    chunks = split_text(text, size=300, overlap=60)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)


def test_very_long_sentence_is_cut():
    chunks = split_text("а" * 2500, size=800, overlap=100)
    assert len(chunks) >= 3
