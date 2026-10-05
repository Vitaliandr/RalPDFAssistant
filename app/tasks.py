from pathlib import Path

from pypdf import PdfReader

from app.celery_app import celery
from app.chunker import split_text
from app.config import settings
from app.db import SessionLocal
from app.embeddings import embed_passages
from app.models import Chunk, Document


def read_pages(path: Path) -> list[tuple[int | None, str]]:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]

    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        #старые txt часто в cp1251
        text = raw.decode("cp1251", errors="replace")
    return [(None, text)]


@celery.task(name="process_document")
def process_document(doc_id: int):
    db = SessionLocal()
    doc = db.get(Document, doc_id)
    if doc is None:
        db.close()
        return

    try:
        doc.status = "processing"
        db.commit()

        pieces = []  # (страница, текст чанка)
        for page, text in read_pages(Path(doc.path)):
            for chunk in split_text(text, settings.chunk_size, settings.chunk_overlap):
                pieces.append((page, chunk))

        if not pieces:
            raise ValueError("В файле нет текста, возможно это скан")

        vectors = []
        #пачками чтоб не упереться в память на больших pdf
        for i in range(0, len(pieces), 32):
            batch = [t for _, t in pieces[i:i + 32]]
            vectors.extend(embed_passages(batch))

        for pos, ((page, text), vec) in enumerate(zip(pieces, vectors)):
            db.add(Chunk(document_id=doc.id, position=pos, page=page, text=text, embedding=vec))

        doc.chunks_count = len(pieces)
        doc.status = "ready"
        db.commit()
    except Exception as e:
        db.rollback()
        doc = db.get(Document, doc_id)
        doc.status = "error"
        doc.error = str(e)[:500]
        db.commit()
    finally:
        db.close()
