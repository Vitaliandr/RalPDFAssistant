from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from ralpdfassistant.repositories import chunks as chunks_repo
from ralpdfassistant.settings import settings


def alembic_config() -> Config:
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parent.parent / "migrations"))
    return cfg


def test_upgrade_and_downgrade(engine, session):
    # база без наших таблиц, дальше всё делает alembic
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    command.upgrade(alembic_config(), "head")
    names = set(inspect(engine).get_table_names())
    assert {"documents", "chunks"} <= names
    assert chunks_repo.vector_dim(session) == settings.embed_dim

    indexes = {i["name"] for i in inspect(engine).get_indexes("chunks")}
    assert "ix_chunks_document_id" in indexes
    assert "chunks_embedding_idx" in indexes

    #индекс по выражению sqlalchemy не отражает, смотрим в каталог postgres
    fts = engine.connect().execute(text("select 1 from pg_indexes where indexname = 'chunks_fts_idx'")).scalar()
    assert fts == 1

    command.downgrade(alembic_config(), "base")
    assert "chunks" not in inspect(engine).get_table_names()
