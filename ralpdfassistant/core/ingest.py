import logging
from pathlib import Path

import pdfplumber
from sqlalchemy.orm import Session

from ralpdfassistant.clients.embeddings import Embedder
from ralpdfassistant.core.chunker import split_text
from ralpdfassistant.repositories import chunks as chunks_repo
from ralpdfassistant.repositories import documents as documents_repo
from ralpdfassistant.settings import settings

log = logging.getLogger(__name__)

BATCH = 32


def read_pages(path: Path) -> list[tuple[int | None, str]]:
    if path.suffix.lower() == ".pdf":
        #pdfplumber держит строки таблиц целыми
        with pdfplumber.open(path) as pdf:
            return [(i + 1, page.extract_text() or "") for i, page in enumerate(pdf.pages)]

    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # старые txt в cp1251
        text = raw.decode("cp1251", errors="replace")
    return [(None, text)]


def context_line(mode: str, title: str, page: int | None, page_text: str) -> str:
    #контекст перед куском, влияет только на вектр
    if mode == "off":
        return ""
    where = f"{title}, стр. {page}" if page else title
    if mode == "head":
        words = page_text.split()
        head = " ".join(words[:18])
        return f"{where}. {head}\n"
    return f"{where}\n"


def process(session: Session, embedder: Embedder, doc_id: int) -> None:
    doc = documents_repo.get(session, doc_id)
    if doc is None:
        return

    try:
        doc.status = "processing"
        session.commit()

        pieces: list[tuple[int | None, str]] = []
        to_embed: list[str] = []
        for page, text in read_pages(Path(doc.path)):
            context = context_line(settings.chunk_context, doc.title, page, text)
            for chunk in split_text(text, settings.chunk_size, settings.chunk_overlap):
                pieces.append((page, chunk))
                to_embed.append(context + chunk)
        if not pieces:
            raise ValueError("В файле нет текста, возможно это скан")

        vectors: list[list[float]] = []
        # пачками, а то память
        for i in range(0, len(to_embed), BATCH):
            vectors.extend(embedder.embed_passages(to_embed[i : i + BATCH]))

        chunks_repo.add_many(session, doc.id, pieces, vectors)
        doc.chunks_count = len(pieces)
        doc.status = "ready"
        session.commit()
        log.info("документ %s готов, чанков %s", doc.id, len(pieces))
    except Exception as e:
        session.rollback()
        #после rollback берём заново
        doc = documents_repo.get(session, doc_id)
        if doc is not None:
            doc.status = "error"
            doc.error = str(e)[:500]
            session.commit()
        log.warning("документ %s не обработан: %s", doc_id, e)
