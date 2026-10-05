from typing import Protocol

from ralpdfassistant.settings import settings


class Embedder(Protocol):
    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedder:
    def __init__(self) -> None:
        # импорт тут, иначе api и тесты тянут onnx ещё до того как модель понадобилась
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=settings.embed_model, cache_dir=settings.models_dir)

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        prefixed = [settings.passage_prefix + t for t in texts]
        return [v.tolist() for v in self.model.embed(prefixed)]

    def embed_query(self, text: str) -> list[float]:
        return [v.tolist() for v in self.model.embed([settings.query_prefix + text])][0]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    #грузим один раз на процесс, модель весит больше 2 ГБ
    global _embedder
    if _embedder is None:
        _embedder = FastEmbedder()
    return _embedder
