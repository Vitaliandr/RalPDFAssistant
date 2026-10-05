from pathlib import Path

from sqlalchemy import func, select

from ralpdfassistant.settings import settings
from ralpdfassistant.tables import Chunk, Document
from tests.conftest import add_text, blank_pdf, make_pdf


def test_upload_text_goes_to_queue(client, jobs):
    r = client.post("/api/documents/text", json={"title": "Тарифы", "text": "Обслуживание 99 рублей."})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    assert body["chunks_count"] == 0
    assert jobs == [body["id"]]


def test_text_without_title(client):
    r = client.post("/api/documents/text", json={"text": "какой-то текст про вклады"})
    assert r.json()["title"] == "Без названия"


def test_empty_text_rejected(client, jobs):
    r = client.post("/api/documents/text", json={"title": "x", "text": "   "})
    assert r.status_code == 400
    assert jobs == []


def test_document_becomes_ready(client, process):
    doc_id = add_text(client, "Вклад", "Вклад открывается на 12 месяцев под 14 процентов годовых.")
    process()

    docs = client.get("/api/documents").json()
    assert docs[0]["id"] == doc_id
    assert docs[0]["status"] == "ready"
    assert docs[0]["chunks_count"] == 1


def test_list_newest_first(client):
    first = add_text(client, "один", "первый документ")
    second = add_text(client, "два", "второй документ")
    assert [d["id"] for d in client.get("/api/documents").json()] == [second, first]


def test_upload_txt_file(client, process):
    r = client.post("/api/documents", files={"file": ("tarif.txt", "Комиссия 1.5 процента".encode(), "text/plain")})
    assert r.status_code == 200
    assert r.json()["title"] == "tarif.txt"
    process()
    assert client.get("/api/documents").json()[0]["status"] == "ready"


def test_upload_pdf_keeps_pages(client, process, session):
    pdf = make_pdf(["First page about credit card fee", "Second page about deposit rate"])
    r = client.post("/api/documents", files={"file": ("bank.pdf", pdf, "application/pdf")})
    assert r.status_code == 200
    process()

    pages = sorted(session.scalars(select(Chunk.page)))
    assert pages == [1, 2]


def test_wrong_extension(client, jobs):
    r = client.post("/api/documents", files={"file": ("virus.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]
    assert jobs == []


def test_file_too_large(client, jobs, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    big = b"a" * (1024 * 1024 + 10)
    r = client.post("/api/documents", files={"file": ("big.txt", big, "text/plain")})
    assert r.status_code == 413
    assert jobs == []


def test_no_file_in_request(client):
    r = client.post("/api/documents")
    assert r.status_code == 422
    assert "Файл" in r.json()["detail"]


def test_pdf_without_text_gets_error(client, process):
    client.post("/api/documents", files={"file": ("scan.pdf", blank_pdf(), "application/pdf")})
    process()
    doc = client.get("/api/documents").json()[0]
    assert doc["status"] == "error"
    assert "нет текста" in doc["error"]


def test_delete_removes_everything(client, process, session):
    doc_id = add_text(client, "Удалить", "текст который скоро пропадёт из базы")
    process()
    path = Path(session.get(Document, doc_id).path)
    assert path.exists()

    assert client.delete(f"/api/documents/{doc_id}").json() == {"ok": True}
    assert client.get("/api/documents").json() == []
    assert not path.exists()
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(Chunk)) == 0


def test_delete_unknown(client):
    r = client.delete("/api/documents/999")
    assert r.status_code == 404
