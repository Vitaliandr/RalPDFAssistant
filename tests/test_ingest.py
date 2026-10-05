from pathlib import Path

from ralpdfassistant.core import ingest
from ralpdfassistant.repositories import documents as documents_repo
from ralpdfassistant.tables import Document
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
