import atexit
import os
import re
import tempfile
import zlib


def _test_database_url() -> str:
    # своя база (CI, или чтобы быстрее локально) через TEST_DATABASE_URL,
    #иначе поднимаем чистый postgres с pgvector в докере на время тестов
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    from testcontainers.postgres import PostgresContainer

    pg = PostgresContainer("pgvector/pgvector:pg16", driver="psycopg")
    pg.start()
    atexit.register(pg.stop)
    return pg.get_connection_url()


# до импорта приложения, settings читаются один раз при импорте
os.environ["DATABASE_URL"] = _test_database_url()
os.environ["UPLOADS_DIR"] = tempfile.mkdtemp(prefix="ralpdfassistant_")
#настоящий .env тестам не нужен, ключи и модель по умолчанию задаём сами
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["DEFAULT_LLM"] = ""
os.environ["EMBED_MODEL"] = "intfloat/multilingual-e5-large"

import io
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ralpdfassistant import tables  # noqa: F401
from ralpdfassistant.core import ingest
from ralpdfassistant.database import Base, get_session
from ralpdfassistant.deps import embedder_dep, enqueue_dep, llm_dep
from ralpdfassistant.main import app
from ralpdfassistant.settings import settings


class HashEmbedder:
    # вместо настоящей модели: слова раскладываются по осям вектора, так что похожие тексты
    # действительно оказываются рядом и поиск в тестах что-то ранжирует
    def _vec(self, text_: str) -> list[float]:
        vec = [0.0] * settings.embed_dim
        for word in re.findall(r"[а-яёa-z0-9]+", text_.lower()):
            if len(word) > 2:
                vec[zlib.crc32(word.encode()) % settings.embed_dim] += 1.0
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class FakeLlm:
    def __init__(self) -> None:
        self.answer = "тестовый ответ"
        self.error: Exception | None = None
        self.calls: list[tuple[str, str]] = []
        #какую модель просили в каждом вызове
        self.models: list[str | None] = []
        #свой ключ пользователя, который пришёл с вопросом
        self.keys: list[str | None] = []

    def __call__(self, question: str, context: str, model: str | None = None, api_key: str | None = None) -> str:
        self.calls.append((question, context))
        self.models.append(model)
        self.keys.append(api_key)
        if self.error:
            raise self.error
        return self.answer


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        #drop_all спотыкается если в базе схема от старой версии, проще снести всё
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture
def jobs() -> list[int]:
    return []


@pytest.fixture
def llm() -> FakeLlm:
    return FakeLlm()


@pytest.fixture
def client(engine: Engine, jobs: list[int], llm: FakeLlm) -> Iterator[TestClient]:
    make_session = sessionmaker(engine, expire_on_commit=False)

    def _session() -> Iterator[Session]:
        with make_session() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[enqueue_dep] = lambda: jobs.append
    app.dependency_overrides[embedder_dep] = lambda: HashEmbedder()
    app.dependency_overrides[llm_dep] = lambda: llm

    # raise_server_exceptions=False чтобы 500 можно было проверить как ответ а не как падение теста
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def process(engine: Engine, jobs: list[int]) -> Any:
    #то что в проде делает воркер: забирает из очереди и обрабатывает
    def run() -> None:
        while jobs:
            with Session(engine, expire_on_commit=False) as s:
                ingest.process(s, HashEmbedder(), jobs.pop(0))

    return run


def add_text(client: TestClient, title: str, body: str) -> int:
    r = client.post("/api/documents/text", json={"title": title, "text": body})
    assert r.status_code == 200, r.text
    return int(r.json()["id"])


def make_pdf(pages: list[str]) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for line in pages:
        c.drawString(60, 780, line)
        c.showPage()
    c.save()
    return buf.getvalue()


def blank_pdf() -> bytes:
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()
