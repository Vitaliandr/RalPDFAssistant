import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ralpdfassistant import logs
from ralpdfassistant.core.reindex import ensure_vector_dim
from ralpdfassistant.database import SessionLocal
from ralpdfassistant.deps import enqueue_dep
from ralpdfassistant.errors import AppError
from ralpdfassistant.routes import chat, documents, models
from ralpdfassistant.settings import settings

logs.setup(as_json=settings.log_json)
log = logging.getLogger("ralpdfassistant")

CallNext = Callable[[Request], Awaitable[Response]]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # таблицы делает alembic
    with SessionLocal() as session:
        ensure_vector_dim(session, enqueue_dep())
    yield


#swagger в проде не нужен, DOCS=false
app = FastAPI(
    title="RalPDFAssistant",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs else None,
    redoc_url="/redoc" if settings.docs else None,
    openapi_url="/openapi.json" if settings.docs else None,
)

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(models.router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    log.info("отказ %s %s: %s", exc.status_code, request.url.path, exc.message)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # трейс только в лог
    log.exception("необработанная ошибка на %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "внутренняя ошибка, попробуйте позже"})


FIELDS = {
    "question": "Вопрос",
    "text": "Текст",
    "title": "Название",
    "file": "Файл",
    "document_ids": "Документы",
    "model": "Модель",
}


def _human_error(err: dict[str, Any]) -> str:
    last = str(err["loc"][-1]) if err["loc"] else "body"
    field = FIELDS.get(last, last)
    if err["type"] == "missing":
        return f"{field}: обязательное поле"
    if err["type"].endswith("_type") or err["type"].endswith("_parsing"):
        return f"{field}: неверный тип значения"
    return f"{field}: неверное значение"


#pydantic по-английски, переводим
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    text = "; ".join(_human_error(e) for e in exc.errors())
    return JSONResponse(status_code=422, content={"detail": text})


# иначе браузер держит старый js
@app.middleware("http")
async def no_stale_frontend(request: Request, call_next: CallNext) -> Response:
    response = await call_next(request)
    if request.method == "GET" and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-cache"
    return response


# CSP: выполняется только наш app.js
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next: CallNext) -> Response:
    response = await call_next(request)
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"  #от clickjacking
    h["Referrer-Policy"] = "no-referrer"
    # swagger с cdn, ему csp мешает
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        h["Content-Security-Policy"] = CSP
    return response


# чужой сайт не шлёт post/delete за нас
@app.middleware("http")
async def same_origin_only(request: Request, call_next: CallNext) -> Response:
    origin = request.headers.get("origin")
    if origin and request.method not in ("GET", "HEAD", "OPTIONS"):
        if urlparse(origin).netloc != request.headers.get("host", ""):
            log.info("отказ: чужой origin %s", origin[:100])
            return JSONResponse(status_code=403, content={"detail": "запрос с чужого сайта"})
    return await call_next(request)


#последний = первый на входе, id есть во всех логах
@app.middleware("http")
async def with_request_id(request: Request, call_next: CallNext) -> Response:
    rid = logs.new_request_id(request.headers.get("x-request-id"))
    token = logs.request_id.set(rid)
    try:
        response = await call_next(request)
    finally:
        logs.request_id.reset(token)
    response.headers["X-Request-ID"] = rid
    return response


# от dns rebinding
hosts = [h.strip() for h in settings.allowed_hosts.split(",") if h.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# в конце, а то перекроет api
app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")
