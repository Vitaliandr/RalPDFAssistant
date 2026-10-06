from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

#иначе metadata пустая
from ralpdfassistant import tables  # noqa: F401
from ralpdfassistant.database import Base
from ralpdfassistant.settings import settings

config = context.config
if config.config_file_name is not None:
    # чтоб не гасить логи pytest
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
