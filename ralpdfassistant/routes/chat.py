from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ralpdfassistant.api_models import AskIn, AskOut, SourceOut
from ralpdfassistant.clients.embeddings import Embedder
from ralpdfassistant.clients.llm import Llm
from ralpdfassistant.core import ask as service
from ralpdfassistant.database import get_session
from ralpdfassistant.deps import embedder_dep, llm_dep

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/ask", response_model=AskOut)
def ask(
    body: AskIn,
    session: Session = Depends(get_session),
    embedder: Embedder = Depends(embedder_dep),
    llm: Llm = Depends(llm_dep),
) -> AskOut:
    text, hits = service.answer(session, embedder, llm, body.question, body.document_ids)
    sources = [SourceOut(document=h.title, page=h.page, text=h.text, score=h.score) for h in hits]
    return AskOut(answer=text, sources=sources)
