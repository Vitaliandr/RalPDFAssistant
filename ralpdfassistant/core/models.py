from dataclasses import dataclass

from ralpdfassistant.settings import DEFAULT_MODEL, settings


@dataclass
class ModelInfo:
    id: str
    label: str
    note: str
    default: bool
    cloud: bool


def list_models() -> list[ModelInfo]:
    return [
        ModelInfo(p.id, p.label, p.note, default=p.id == DEFAULT_MODEL, cloud=p.cloud)
        for p in settings.llm_profiles().values()
    ]
