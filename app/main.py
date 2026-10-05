from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app.config import settings
from app.db import SessionLocal, engine
from app.models import Base, Document
from app.routers import chat, documents
from app.tasks import process_document


def fix_vector_dim() -> bool:
    # если сменили модель эмбеддингов то размер вектора в таблице уже не тот
    with engine.begin() as conn:
        dim = conn.execute(text(
            "select a.atttypmod from pg_attribute a join pg_class c on c.oid = a.attrelid "
            "where c.relname = 'chunks' and a.attname = 'embedding'"
        )).scalar()
        if dim is None or dim == settings.embed_dim:
            return False

        # старые векторы от другой модели всё равно бесполезны
        conn.execute(text("delete from chunks"))
        conn.execute(text("drop index if exists chunks_embedding_idx"))
        conn.execute(text(f"alter table chunks alter column embedding type vector({settings.embed_dim})"))
        conn.execute(text(
            "create index chunks_embedding_idx on chunks using hnsw (embedding vector_cosine_ops)"
        ))
    return True


def requeue_all():
    db = SessionLocal()
    for doc in db.scalars(select(Document)):
        doc.status = "queued"
        doc.chunks_count = 0
        doc.error = None
    db.commit()
    for doc in db.scalars(select(Document)):
        process_document.delay(doc.id)
    db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    changed = fix_vector_dim()
    Base.metadata.create_all(engine)
    if changed:
        requeue_all()
    yield


app = FastAPI(title="RAG по документам", lifespan=lifespan)

app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


#статику монтируем последней иначе она перекроет api
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
