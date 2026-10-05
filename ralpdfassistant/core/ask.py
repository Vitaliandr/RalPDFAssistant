import logging

from sqlalchemy.orm import Session

from ralpdfassistant.clients.embeddings import Embedder
from ralpdfassistant.clients.llm import Llm
from ralpdfassistant.errors import AppError
from ralpdfassistant.repositories import chunks as chunks_repo
from ralpdfassistant.repositories.chunks import Hit
from ralpdfassistant.settings import settings

log = logging.getLogger(__name__)

NO_DOCS = "Пока нет готовых документов, загрузи хотя бы один."


def build_context(hits: list[Hit]) -> str:
    lines = []
    for n, h in enumerate(hits, start=1):
        where = f"{h.title}, стр. {h.page}" if h.page else h.title
        lines.append(f"[{n}] ({where})\n{h.text}")
    return "\n\n".join(lines)


def answer(
    session: Session, embedder: Embedder, llm: Llm, question: str, doc_ids: list[int] | None
) -> tuple[str, list[Hit]]:
    question = question.strip()
    if not question:
        raise AppError("Задай вопрос")

    hits = chunks_repo.search(session, embedder.embed_query(question), doc_ids, settings.top_k)
    if not hits:
        return NO_DOCS, []

    log.info("вопрос по %s фрагментам, лучший score %s", len(hits), hits[0].score)
    return llm(question, build_context(hits)), hits
