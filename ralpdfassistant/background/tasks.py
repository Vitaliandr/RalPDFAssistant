from ralpdfassistant.background.celery_app import celery
from ralpdfassistant.clients.embeddings import get_embedder
from ralpdfassistant.core import ingest
from ralpdfassistant.database import SessionLocal


@celery.task(name="process_document")
def process_document(doc_id: int) -> None:
    with SessionLocal() as session:
        try:
            embedder = get_embedder()
        except Exception as e:
            # без этого документ висит в очереди вечно
            ingest.mark_error(session, doc_id, f"Не загрузилась модель эмбеддингов: {e}")
            raise
        ingest.process(session, embedder, doc_id)
