from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, literal_column, select, text
from sqlalchemy.orm import Session

from ralpdfassistant.tables import Chunk, Document


@dataclass
class Hit:
    id: int
    title: str
    page: int | None
    text: str
    score: float


def add_many(session: Session, doc_id: int, pieces: list[tuple[int | None, str]], vectors: list[list[float]]) -> None:
    for pos, ((page, body), vec) in enumerate(zip(pieces, vectors, strict=True)):
        session.add(Chunk(document_id=doc_id, position=pos, page=page, text=body, embedding=vec))


def _base_query(vec: list[float], doc_ids: list[int] | None) -> tuple[Select[Any], Any]:
    dist = Chunk.embedding.cosine_distance(vec)
    query = (
        select(Chunk.id, Chunk.text, Chunk.page, Document.title, dist.label("dist"))
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.status == "ready")
    )
    if doc_ids:
        query = query.where(Chunk.document_id.in_(doc_ids))
    return query, dist


def _hits(rows: Sequence[Any]) -> list[Hit]:
    return [Hit(id=r.id, title=r.title, page=r.page, text=r.text, score=round(1 - r.dist, 3)) for r in rows]


def search(session: Session, vec: list[float], doc_ids: list[int] | None, limit: int) -> list[Hit]:
    query, dist = _base_query(vec, doc_ids)
    return _hits(session.execute(query.order_by(dist).limit(limit)).all())


#выражение должно совпадать с тем что в индексе chunks_fts_idx (миграция 0002), иначе индекс не подхватится
FTS_VECTOR = func.to_tsvector(literal_column("'russian'"), Chunk.text)


def keyword_search(
    session: Session, vec: list[float], tsquery: str, doc_ids: list[int] | None, limit: int
) -> list[Hit]:
    #score у таких кусков всё равно косинус, чтобы в интерфейсе везде была одна шкала
    query, _ = _base_query(vec, doc_ids)
    ts = func.to_tsquery(literal_column("'russian'"), tsquery)
    query = query.where(FTS_VECTOR.op("@@")(ts)).order_by(func.ts_rank_cd(FTS_VECTOR, ts).desc())
    return _hits(session.execute(query.limit(limit)).all())


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
