from fastembed import TextEmbedding

from app.config import settings

_model = None


def get_model():
    #грузим лениво иначе api стартует долго
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=settings.embed_model, cache_dir=settings.models_dir)
    return _model


def embed_passages(texts: list[str]) -> list[list[float]]:
    prefixed = [settings.passage_prefix + t for t in texts]
    return [v.tolist() for v in get_model().embed(prefixed)]


def embed_query(text: str) -> list[float]:
    return [v.tolist() for v in get_model().embed([settings.query_prefix + text])][0]
