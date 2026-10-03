import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.llm import ask_llm, build_context
from app.schemas import AskIn, AskOut, SourceOut
from app.search import find_chunks

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/ask", response_model=AskOut)
def ask(body: AskIn, db: Session = Depends(get_db)):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Задай вопрос")

    found = find_chunks(db, question, body.document_ids, settings.top_k)
    if not found:
        return AskOut(answer="Пока нет готовых документов, загрузи хотя бы один.", sources=[])

    try:
        answer = ask_llm(question, build_context(found))
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code in (401, 403):
            msg = "Провайдер не принял ключ, проверь LLM_API_KEY"
        elif code == 429:
            msg = "Упёрлись в лимит бесплатного тарифа, подожди минуту"
        elif code == 404:
            msg = "Провайдер не знает такую модель, проверь LLM_MODEL"
        else:
            msg = f"Модель вернула ошибку {code}"
        raise HTTPException(502, msg)
    except httpx.HTTPError:
        raise HTTPException(502, "Не достучались до модели, проверь адрес и что ollama запущена")

    sources = [
        SourceOut(document=title, page=chunk.page, text=chunk.text, score=round(1 - dist, 3))
        for chunk, title, dist in found
    ]
    return AskOut(answer=answer, sources=sources)
