import pytest

from ralpdfassistant.background import tasks
from ralpdfassistant.repositories import documents as documents_repo
from ralpdfassistant.tables import Document
from tests.conftest import HashEmbedder


def test_celery_task_processes_document(engine, session, tmp_path, monkeypatch):
    f = tmp_path / "t.txt"
    f.write_text("Штраф за просрочку 590 рублей", encoding="utf-8")
    doc = Document(title="t", path=str(f))
    documents_repo.add(session, doc)
    session.commit()

    monkeypatch.setattr(tasks, "get_embedder", lambda: HashEmbedder())
    tasks.process_document(doc.id)

    session.expire_all()
    assert session.get(Document, doc.id).status == "ready"


def test_model_load_failure_is_visible(engine, session, tmp_path, monkeypatch):
    f = tmp_path / "t.txt"
    f.write_text("Штраф за просрочку 590 рублей", encoding="utf-8")
    doc = Document(title="t", path=str(f))
    documents_repo.add(session, doc)
    session.commit()

    def broken():
        raise RuntimeError("нет файла модели")

    monkeypatch.setattr(tasks, "get_embedder", broken)
    with pytest.raises(RuntimeError):
        tasks.process_document(doc.id)

    # не должен висеть в очереди
    session.expire_all()
    saved = session.get(Document, doc.id)
    assert saved.status == "error"
    assert "модель" in saved.error
    assert "нет файла модели" in saved.error
