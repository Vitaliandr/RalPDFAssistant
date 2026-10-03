from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import embed_query
from app.models import Chunk, Document


def find_chunks(db: Session, question: str, doc_ids: list[int] | None, limit: int):
    vec = embed_query(question)
    dist = Chunk.embedding.cosine_distance(vec)

    query = (
        select(Chunk, Document.title, dist.label("dist"))
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.status == "ready")
    )
    if doc_ids:
        query = query.where(Chunk.document_id.in_(doc_ids))

    return db.execute(query.order_by(dist).limit(limit)).all()
