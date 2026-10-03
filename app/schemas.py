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
    title: str
    text: str


class AskIn(BaseModel):
    question: str
    document_ids: list[int] | None = None


class SourceOut(BaseModel):
    document: str
    page: int | None
    text: str
    score: float


class AskOut(BaseModel):
    answer: str
    sources: list[SourceOut]
