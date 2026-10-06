#коммитит сервис, тут нет
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ralpdfassistant.tables import Document


def get(session: Session, doc_id: int) -> Document | None:
    return session.get(Document, doc_id)


def all_docs(session: Session) -> list[Document]:
    res = session.execute(select(Document).order_by(Document.id.desc()))
    return list(res.scalars())


def add(session: Session, doc: Document) -> None:
    session.add(doc)


def delete(session: Session, doc: Document) -> None:
    session.delete(doc)


def requeue_all(session: Session) -> list[int]:
    ids = list(session.scalars(select(Document.id)))
    session.execute(update(Document).values(status="queued", chunks_count=0, error=None))
    return ids
