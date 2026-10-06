from pathlib import Path

from sqlalchemy import select

from ralpdfassistant.core import ingest
from ralpdfassistant.repositories import documents as documents_repo
from ralpdfassistant.settings import settings
from ralpdfassistant.tables import Chunk, Document
from tests.conftest import HashEmbedder


def make_doc(session, path: Path) -> int:
    doc = Document(title="t", path=str(path))
    documents_repo.add(session, doc)
    session.commit()
    return doc.id


def reload(session, doc_id: int) -> Document:
    doc = documents_repo.get(session, doc_id)
    assert doc is not None
    return doc


class RecordingEmbedder(HashEmbedder):
    def __init__(self) -> None:
        self.seen: list[str] = []

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        self.seen.extend(texts)
        return super().embed_passages(texts)


def make_titled(session, path: Path, title: str) -> int:
    doc = Document(title=title, path=str(path))
    documents_repo.add(session, doc)
    session.commit()
    return doc.id


def test_context_modes():
    assert ingest.context_line("off", "Тарифы", 2, "любой текст") == ""
    assert ingest.context_line("title", "Тарифы", 2, "любой текст") == "Тарифы, стр. 2\n"
    assert ingest.context_line("title", "Тарифы", None, "любой текст") == "Тарифы\n"


def test_context_head_takes_first_words():
    page = " ".join(f"слово{i}" for i in range(50))
    line = ingest.context_line("head", "Отчёт", 5, page)
    assert line.startswith("Отчёт, стр. 5. слово0 слово1")
    assert "слово17" in line
    assert "слово18" not in line


def test_context_only_in_vector(session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "chunk_context", "title")
    f = tmp_path / "a.txt"
    f.write_text("Ставка по вкладу 14 процентов", encoding="utf-8")
    doc_id = make_titled(session, f, "Условия вклада")

    embedder = RecordingEmbedder()
    ingest.process(session, embedder, doc_id)

    assert embedder.seen == ["Условия вклада\nСтавка по вкладу 14 процентов"]
    assert session.scalars(select(Chunk.text)).all() == ["Ставка по вкладу 14 процентов"]


def test_context_off_sends_plain_chunk(session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "chunk_context", "off")
    f = tmp_path / "a.txt"
    f.write_text("Ставка по вкладу 14 процентов", encoding="utf-8")
    doc_id = make_titled(session, f, "Условия вклада")

    embedder = RecordingEmbedder()
    ingest.process(session, embedder, doc_id)
    assert embedder.seen == ["Ставка по вкладу 14 процентов"]


def test_cp1251_file(session, tmp_path):
    f = tmp_path / "old.txt"
    f.write_bytes("Ставка по вкладу 14 процентов".encode("cp1251"))
    doc_id = make_doc(session, f)

    ingest.process(session, HashEmbedder(), doc_id)
    assert reload(session, doc_id).status == "ready"


def test_missing_file_is_error_not_crash(session, tmp_path):
    doc_id = make_doc(session, tmp_path / "нет такого.txt")

    ingest.process(session, HashEmbedder(), doc_id)
    doc = reload(session, doc_id)
    assert doc.status == "error"
    assert doc.error


def test_unknown_doc_is_ignored(session):
    ingest.process(session, HashEmbedder(), 12345)


def test_long_text_split_into_chunks(session, tmp_path):
    f = tmp_path / "long.txt"
    f.write_text(" ".join(f"Предложение номер {i} про тарифы банка." for i in range(200)), encoding="utf-8")
    doc_id = make_doc(session, f)

    ingest.process(session, HashEmbedder(), doc_id)
    assert reload(session, doc_id).chunks_count > 5
