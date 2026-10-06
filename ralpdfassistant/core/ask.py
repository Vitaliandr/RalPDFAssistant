import logging
import re

from sqlalchemy.orm import Session

from ralpdfassistant.clients.embeddings import Embedder
from ralpdfassistant.clients.llm import Llm
from ralpdfassistant.errors import AppError
from ralpdfassistant.repositories import chunks as chunks_repo
from ralpdfassistant.repositories.chunks import Hit
from ralpdfassistant.settings import settings

log = logging.getLogger(__name__)

NO_DOCS = "Пока нет готовых документов, загрузи хотя бы один."

STOP_WORDS = {
    "какой", "какая", "какие", "какое", "каков", "кто", "что", "сколько", "когда", "где", "как",
    "для", "при", "про", "это", "был", "была", "были", "есть", "или", "его", "ещё", "еще",
}  # fmt: skip

#стандартное для rrf
RRF_K = 60


def keywords(question: str) -> str:
    words = [w for w in re.findall(r"[а-яёa-z0-9]+", question.lower()) if len(w) > 2 and w not in STOP_WORDS]
    # любое слово, не все сразу
    return " | ".join(dict.fromkeys(words))


def fuse(by_vector: list[Hit], by_words: list[Hit], limit: int) -> list[Hit]:
    #rrf: 1/(k+место) из обоих списков, score не сравниваем
    points: dict[int, float] = {}
    hits: dict[int, Hit] = {}
    for found in (by_vector, by_words):
        for rank, hit in enumerate(found):
            points[hit.id] = points.get(hit.id, 0.0) + 1 / (RRF_K + rank + 1)
            hits[hit.id] = hit
    best = sorted(points, key=lambda i: points[i], reverse=True)[:limit]
    return [hits[i] for i in best]


def retrieve(
    session: Session,
    embedder: Embedder,
    question: str,
    doc_ids: list[int] | None,
    limit: int | None = None,
    hybrid: bool | None = None,
) -> list[Hit]:
    limit = limit or settings.top_k
    vec = embedder.embed_query(question)
    if not (settings.hybrid if hybrid is None else hybrid):
        return chunks_repo.search(session, vec, doc_ids, limit)

    by_vector = chunks_repo.search(session, vec, doc_ids, settings.candidates)
    tsquery = keywords(question)
    by_words = chunks_repo.keyword_search(session, vec, tsquery, doc_ids, settings.candidates) if tsquery else []
    return fuse(by_vector, by_words, limit)


def build_context(hits: list[Hit]) -> str:
    lines = []
    for n, h in enumerate(hits, start=1):
        where = f"{h.title}, стр. {h.page}" if h.page else h.title
        lines.append(f"[{n}] ({where})\n{h.text}")
    return "\n\n".join(lines)


def answer(
    session: Session,
    embedder: Embedder,
    llm: Llm,
    question: str,
    doc_ids: list[int] | None,
    model: str | None = None,
    api_key: str | None = None,
) -> tuple[str, list[Hit]]:
    question = question.strip()
    if not question:
        raise AppError("Задай вопрос")

    hits = retrieve(session, embedder, question, doc_ids)
    if not hits:
        return NO_DOCS, []

    log.info("вопрос по %s фрагментам, лучший score %s", len(hits), hits[0].score)
    return llm(question, build_context(hits), model, api_key), hits
