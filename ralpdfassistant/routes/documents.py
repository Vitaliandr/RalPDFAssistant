from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from ralpdfassistant.api_models import DocumentOut, TextIn
from ralpdfassistant.core import documents as service
from ralpdfassistant.core.documents import Enqueue
from ralpdfassistant.database import get_session
from ralpdfassistant.deps import enqueue_dep
from ralpdfassistant.settings import settings

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(session: Session = Depends(get_session)) -> list[DocumentOut]:
    return [DocumentOut.model_validate(d) for d in service.list_documents(session)]


@router.post("", response_model=DocumentOut)
def upload(
    file: UploadFile = File(...), session: Session = Depends(get_session), enqueue: Enqueue = Depends(enqueue_dep)
) -> DocumentOut:
    # читаем с запасом в один байт, так видно что файл больше лимита и не грузим в память гигабайты
    data = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    doc = service.upload_file(session, enqueue, file.filename or "", data)
    return DocumentOut.model_validate(doc)


@router.post("/text", response_model=DocumentOut)
def upload_text(
    body: TextIn, session: Session = Depends(get_session), enqueue: Enqueue = Depends(enqueue_dep)
) -> DocumentOut:
    doc = service.upload_text(session, enqueue, body.title, body.text)
    return DocumentOut.model_validate(doc)


@router.delete("/{doc_id}")
def delete_document(doc_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    service.delete_document(session, doc_id)
    return {"ok": True}
