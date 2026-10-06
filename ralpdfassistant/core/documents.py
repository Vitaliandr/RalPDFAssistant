import logging
import uuid
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from ralpdfassistant.errors import AppError, NotFound, TooLarge
from ralpdfassistant.repositories import documents as documents_repo
from ralpdfassistant.settings import settings
from ralpdfassistant.tables import Document

Enqueue = Callable[[int], object]

ALLOWED = {".pdf", ".txt", ".md"}

log = logging.getLogger(__name__)


def _save_and_queue(session: Session, enqueue: Enqueue, title: str, data: bytes, suffix: str) -> Document:
    folder = Path(settings.uploads_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)

    doc = Document(title=title[:255], path=str(path))
    documents_repo.add(session, doc)
    session.commit()
    #после комита, а то воркер не найдёт
    enqueue(doc.id)
    log.info("документ %s принят (%s, %s байт)", doc.id, suffix, len(data))
    return doc


def upload_file(session: Session, enqueue: Enqueue, filename: str, data: bytes) -> Document:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise AppError("Поддерживаются только PDF, TXT и MD")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise TooLarge(f"Файл больше {settings.max_upload_mb} МБ")
    return _save_and_queue(session, enqueue, filename, data, suffix)


def upload_text(session: Session, enqueue: Enqueue, title: str, text: str) -> Document:
    if not text.strip():
        raise AppError("Текст пустой")
    return _save_and_queue(session, enqueue, title.strip() or "Без названия", text.encode("utf-8"), ".txt")


def list_documents(session: Session) -> list[Document]:
    return documents_repo.all_docs(session)


def delete_document(session: Session, doc_id: int) -> None:
    doc = documents_repo.get(session, doc_id)
    if doc is None:
        raise NotFound("Документ не найден")

    Path(doc.path).unlink(missing_ok=True)
    documents_repo.delete(session, doc)
    session.commit()
    log.info("документ %s удалён", doc_id)
