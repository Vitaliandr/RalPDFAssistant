import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from ralpdfassistant import logs
from ralpdfassistant.core.reindex import ensure_vector_dim
from ralpdfassistant.database import SessionLocal
from ralpdfassistant.deps import enqueue_dep
from ralpdfassistant.errors import AppError
from ralpdfassistant.routes import chat, documents
from ralpdfassistant.settings import settings

logs.setup(as_json=settings.log_json)
log = logging.getLogger("ralpdfassistant")

CallNext = Callable[[Request], Awaitable[Response]]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # таблицы создаёт alembic, тут только проверка что размер вектора совпадает с моделью
    with SessionLocal() as session:
        ensure_vector_dim(session, enqueue_dep())
    yield


#swagger можно выключить (DOCS=false), в проде карта всех ручек ни к чему
app = FastAPI(
    title="RalPDFAssistant",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs else None,
    redoc_url="/redoc" if settings.docs else None,
    openapi_url="/openapi.json" if settings.docs else None,
)

app.include_router(documents.router)
app.include_router(chat.router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    log.info("отказ %s %s: %s", exc.status_code, request.url.path, exc.message)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # трейс только в лог, клиенту детали знать незачем
    log.exception("необработанная ошибка на %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "внутренняя ошибка, попробуйте позже"})


FIELDS = {
    "question": "Вопрос",
    "text": "Текст",
    "title": "Название",
    "file": "Файл",
    "document_ids": "Документы",
}


def _human_error(err: dict[str, Any]) -> str:
    last = str(err["loc"][-1]) if err["loc"] else "body"
    field = FIELDS.get(last, last)
    if err["type"] == "missing":
        return f"{field}: обязательное поле"
    if err["type"].endswith("_type") or err["type"].endswith("_parsing"):
        return f"{field}: неверный тип значения"
    return f"{field}: неверное значение"


#ошибки pydantic по умолчанию на английском и списком, а интерфейсу нужна одна строка
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    text = "; ".join(_human_error(e) for e in exc.errors())
    return JSONResponse(status_code=422, content={"detail": text})


# без этого браузер берёт html js css из кэша и показывает старый интерфейс.
# no-cache не запрещает кэш а заставляет спросить сервер
@app.middleware("http")
async def no_stale_frontend(request: Request, call_next: CallNext) -> Response:
    response = await call_next(request)
    if request.method == "GET" and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-cache"
    return response


#браузер выполнит только наш app.js, чужой скрипт из загруженного документа не запустится
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next: CallNext) -> Response:
    response = await call_next(request)
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"  #нельзя встроить в чужой сайт
    h["Referrer-Policy"] = "no-referrer"
    # swagger грузит скрипты с cdn, ему строгий CSP ломает страницу
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        h["Content-Security-Policy"] = CSP
    return response


# объявлен последним значит выполняется первым, id есть уже во всех логах запроса
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


#интерфейс, монтируем последним иначе он перекроет api
app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")
