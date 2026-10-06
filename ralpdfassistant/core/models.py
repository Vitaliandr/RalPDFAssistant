from dataclasses import dataclass

from ralpdfassistant.settings import settings


@dataclass
class ModelInfo:
    id: str
    label: str
    note: str
    default: bool
    #облачная модель, ей нужен ключ
    cloud: bool
    #в .env у сервера свой ключ есть. сам ключ наружу не отдаём никогда, только факт что он есть
    server_key: bool
    #у сервера ключа нет, значит человеку надо вставить свой в интерфейсе
    needs_key: bool


def list_models() -> list[ModelInfo]:
    return [
        ModelInfo(
            p.id,
            p.label,
            p.note,
            default=p.id == settings.default_llm,
            cloud=p.cloud,
            server_key=bool(p.api_key),
            needs_key=p.cloud and not p.api_key,
        )
        for p in settings.llm_profiles().values()
    ]
