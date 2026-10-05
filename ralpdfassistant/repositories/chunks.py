from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ralpdfassistant.tables import Chunk, Document


@dataclass
class Hit:
    title: str
    page: int | None
    text: str
    score: float


def add_many(session: Session, doc_id: int, pieces: list[tuple[int | None, str]], vectors: list[list[float]]) -> None:
    for pos, ((page, body), vec) in enumerate(zip(pieces, vectors, strict=True)):
        session.add(Chunk(document_id=doc_id, position=pos, page=page, text=body, embedding=vec))


def search(session: Session, vec: list[float], doc_ids: list[int] | None, limit: int) -> list[Hit]:
    dist = Chunk.embedding.cosine_distance(vec)
    query = (
        select(Chunk.text, Chunk.page, Document.title, dist.label("dist"))
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.status == "ready")
    )
    if doc_ids:
        query = query.where(Chunk.document_id.in_(doc_ids))

    rows = session.execute(query.order_by(dist).limit(limit)).all()
    return [Hit(title=r.title, page=r.page, text=r.text, score=round(1 - r.dist, 3)) for r in rows]


def vector_dim(session: Session) -> int | None:
    # у pgvector размер лежит прямо в atttypmod
    return session.execute(
        text(
            "select a.atttypmod from pg_attribute a join pg_class c on c.oid = a.attrelid "
            "where c.relname = 'chunks' and a.attname = 'embedding'"
        )
    ).scalar()


def change_dim(session: Session, dim: int) -> None:
    # старые векторы от другой модели всё равно бесполезны
    session.execute(text("delete from chunks"))
    session.execute(text("drop index if exists chunks_embedding_idx"))
    session.execute(text(f"alter table chunks alter column embedding type vector({int(dim)})"))
    session.execute(text("create index chunks_embedding_idx on chunks using hnsw (embedding vector_cosine_ops)"))
