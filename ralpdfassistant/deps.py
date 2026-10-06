# тут то что в тестах подменяем
from ralpdfassistant.clients.embeddings import Embedder, get_embedder
from ralpdfassistant.clients.llm import Llm, ask_llm
from ralpdfassistant.core.documents import Enqueue


def enqueue_dep() -> Enqueue:
    #celery только когда надо
    from ralpdfassistant.background.tasks import process_document

    return process_document.delay


def embedder_dep() -> Embedder:
    return get_embedder()


def llm_dep() -> Llm:
    return ask_llm
