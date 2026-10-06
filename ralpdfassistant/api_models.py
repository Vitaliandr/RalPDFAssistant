from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    title: str
    status: str
    error: str | None
    chunks_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TextIn(BaseModel):
    title: str = ""
    text: str


class AskIn(BaseModel):
    question: str
    document_ids: list[int] | None = None
    #id модели из /api/models, без него берётся та что по умолчанию
    model: str | None = None


class SourceOut(BaseModel):
    document: str
    page: int | None
    text: str
    score: float


class AskOut(BaseModel):
    answer: str
    sources: list[SourceOut]
    #какая модель реально отвечала
    model: str


class ModelOut(BaseModel):
    id: str
    label: str
    note: str
    default: bool
    cloud: bool
    server_key: bool
    needs_key: bool
