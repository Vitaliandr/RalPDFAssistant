import logging

from sqlalchemy.orm import Session

from ralpdfassistant.core.documents import Enqueue
from ralpdfassistant.repositories import chunks as chunks_repo
from ralpdfassistant.repositories import documents as documents_repo
from ralpdfassistant.settings import settings

log = logging.getLogger(__name__)


def ensure_vector_dim(session: Session, enqueue: Enqueue) -> bool:
    #если сменили модель эмбеддингов то размер вектора в таблице уже не тот
    dim = chunks_repo.vector_dim(session)
    if dim is None or dim == settings.embed_dim:
        return False

    chunks_repo.change_dim(session, settings.embed_dim)
    ids = documents_repo.requeue_all(session)
    session.commit()
    for doc_id in ids:
        enqueue(doc_id)
    log.info("размер вектора %s -> %s, на переиндексацию ушло документов: %s", dim, settings.embed_dim, len(ids))
    return True
