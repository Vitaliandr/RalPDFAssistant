from ralpdfassistant.background.celery_app import celery
from ralpdfassistant.clients.embeddings import get_embedder
from ralpdfassistant.core import ingest
from ralpdfassistant.database import SessionLocal


@celery.task(name="process_document")
def process_document(doc_id: int) -> None:
    with SessionLocal() as session:
        ingest.process(session, get_embedder(), doc_id)
