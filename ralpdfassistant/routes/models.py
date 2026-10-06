from fastapi import APIRouter

from ralpdfassistant.api_models import ModelOut
from ralpdfassistant.core import models as service

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=list[ModelOut])
def list_models() -> list[ModelOut]:
    return [
        ModelOut(id=m.id, label=m.label, note=m.note, default=m.default, cloud=m.cloud) for m in service.list_models()
    ]
