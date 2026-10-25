import os

import pytest

from backend.app.database import RunDatabase


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to opt into a dedicated PostgreSQL connectivity test",
)
def test_dedicated_postgres_database_connectivity() -> None:
    test_url = os.environ["TEST_DATABASE_URL"]
    production_url = os.getenv("DATABASE_URL")
    if production_url and test_url == production_url:
        pytest.fail("TEST_DATABASE_URL must not point to DATABASE_URL")

    database = RunDatabase(test_url)
    try:
        database.check_connection()
    finally:
        database.dispose()
