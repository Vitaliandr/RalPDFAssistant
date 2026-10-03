import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Document
from app.schemas import DocumentOut, TextIn
from app.tasks import process_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED = {".pdf", ".txt", ".md"}


def save_and_queue(db: Session, title: str, data: bytes, suffix: str) -> Document:
    folder = Path(settings.uploads_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)

    doc = Document(title=title[:255], path=str(path))
    db.add(doc)
    db.commit()
    #задачу кидаем после коммита, иначе воркер может не найти документ
    process_document.delay(doc.id)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return db.scalars(select(Document).order_by(Document.id.desc())).all()


@router.post("", response_model=DocumentOut)
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, "Поддерживаются только PDF, TXT и MD")

    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Файл больше {settings.max_upload_mb} МБ")

    return save_and_queue(db, file.filename, data, suffix)


@router.post("/text", response_model=DocumentOut)
def upload_text(body: TextIn, db: Session = Depends(get_db)):
    if not body.text.strip():
        raise HTTPException(400, "Текст пустой")
    title = body.title.strip() or "Без названия"
    return save_and_queue(db, title, body.text.encode("utf-8"), ".txt")


@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Документ не найден")

    Path(doc.path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    return {"ok": True}
