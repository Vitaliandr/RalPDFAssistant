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
        #pdfplumber собирает слова в строки по координатам, поэтому строки таблиц тарифов остаются целыми.
        # pypdf отдавал сначала все названия строк, потом все значения, и модель путала что к чему
        with pdfplumber.open(path) as pdf:
            return [(i + 1, page.extract_text() or "") for i, page in enumerate(pdf.pages)]

    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # старые txt часто в cp1251
        text = raw.decode("cp1251", errors="replace")
    return [(None, text)]


def process(session: Session, embedder: Embedder, doc_id: int) -> None:
    doc = documents_repo.get(session, doc_id)
    if doc is None:
        return

    try:
        doc.status = "processing"
        session.commit()

        pieces: list[tuple[int | None, str]] = []
        for page, text in read_pages(Path(doc.path)):
            for chunk in split_text(text, settings.chunk_size, settings.chunk_overlap):
                pieces.append((page, chunk))
        if not pieces:
            raise ValueError("В файле нет текста, возможно это скан")

        vectors: list[list[float]] = []
        #пачками чтобы не упереться в память на больших pdf
        for i in range(0, len(pieces), BATCH):
            vectors.extend(embedder.embed_passages([t for _, t in pieces[i : i + BATCH]]))

        chunks_repo.add_many(session, doc.id, pieces, vectors)
        doc.chunks_count = len(pieces)
        doc.status = "ready"
        session.commit()
        log.info("документ %s готов, чанков %s", doc.id, len(pieces))
    except Exception as e:
        session.rollback()
        # после rollback объект протух, берём заново
        doc = documents_repo.get(session, doc_id)
        if doc is not None:
            doc.status = "error"
            doc.error = str(e)[:500]
            session.commit()
        log.warning("документ %s не обработан: %s", doc_id, e)
