# то что роуты получают через Depends. тут всё что ходит наружу (очередь, модели),
# в тестах эти функции подменяются через dependency_overrides
from ralpdfassistant.clients.embeddings import Embedder, get_embedder
from ralpdfassistant.clients.llm import Llm, ask_llm
from ralpdfassistant.core.documents import Enqueue


def enqueue_dep() -> Enqueue:
    #импорт внутри, чтобы api не поднимал celery пока никто не загрузил файл
    from ralpdfassistant.background.tasks import process_document

    return process_document.delay


def embedder_dep() -> Embedder:
    return get_embedder()


def llm_dep() -> Llm:
    return ask_llm
