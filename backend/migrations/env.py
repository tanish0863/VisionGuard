from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy.exc import SQLAlchemyError

repository_root = Path(__file__).resolve().parents[2]
if str(repository_root) not in sys.path:
    sys.path.insert(0, str(repository_root))

from backend.app.database import DatabaseConfigurationError, RunDatabase, metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def run_migrations_offline() -> None:
    raise RuntimeError(
        "Offline migrations are disabled because DATABASE_URL is required."
    )


def run_migrations_online() -> None:
    try:
        database = RunDatabase.from_environment()
    except DatabaseConfigurationError as error:
        raise SystemExit(str(error)) from None
    try:
        try:
            connection = database.engine.connect()
        except SQLAlchemyError:
            raise SystemExit(
                "Could not connect to the configured database for migration; "
                "verify DATABASE_URL and Neon connectivity."
            ) from None
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                transactional_ddl=True,
            )
            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.close()
    finally:
        database.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
