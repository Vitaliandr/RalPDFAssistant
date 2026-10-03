from fastembed import TextEmbedding

from app.config import settings

_model = None


def get_model():
    #грузим лениво иначе api стартует долго
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=settings.embed_model, cache_dir=settings.models_dir)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in get_model().embed(texts)]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
