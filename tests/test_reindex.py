from sqlalchemy import text

from ralpdfassistant.core.reindex import ensure_vector_dim
from ralpdfassistant.repositories import chunks as chunks_repo
from ralpdfassistant.settings import settings
from ralpdfassistant.tables import Document
from tests.conftest import add_text


def test_same_dim_changes_nothing(client, process, session, jobs):
    add_text(client, "док", "какой-то текст про вклады")
    process()

    assert ensure_vector_dim(session, jobs.append) is False
    assert jobs == []
    assert session.get(Document, 1).status == "ready"


def test_other_dim_rebuilds_and_requeues(client, process, session, jobs):
    first = add_text(client, "один", "текст про тарифы карты")
    second = add_text(client, "два", "текст про условия вклада")
    process()

    #как будто старая база
    chunks_repo.change_dim(session, 384)
    session.commit()
    assert chunks_repo.vector_dim(session) == 384

    assert ensure_vector_dim(session, jobs.append) is True
    assert chunks_repo.vector_dim(session) == settings.embed_dim
    assert sorted(jobs) == [first, second]

    session.expire_all()
    assert {session.get(Document, i).status for i in (first, second)} == {"queued"}

    process()
    hits = chunks_repo.search(session, [1.0] + [0.0] * (settings.embed_dim - 1), None, 5)
    assert len(hits) == 2


def test_no_table_no_problem(session):
    session.execute(text("drop table chunks"))
    session.commit()
    assert ensure_vector_dim(session, lambda i: None) is False
