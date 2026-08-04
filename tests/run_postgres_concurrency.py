import os
import subprocess
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from config.settings import DATABASE_URL


def main() -> int:
    database_name = f"fionobre_test_{uuid.uuid4().hex[:10]}"
    base_url = make_url(DATABASE_URL)
    admin_url = base_url.set(database="postgres")
    test_url = base_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))

        ambiente = os.environ.copy()
        ambiente["TEST_DATABASE_URL"] = test_url.render_as_string(hide_password=False)
        resultado = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_concorrencia_postgres",
                "-v",
            ],
            env=ambiente,
            check=False,
        )
        return resultado.returncode
    finally:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
