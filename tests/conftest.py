import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import SCHEMA_PATH, app


# Fresh SQLite file per test, so tests never share state or touch foi.db.
# get_db() reads FOI_DB_PATH on every request, so setting the env var is enough to redirect it.
@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("FOI_DB_PATH", str(path))
    conn = db.get_connection(str(path))
    db.init_db(conn, SCHEMA_PATH)
    conn.close()
    return path


# "with" runs the app's lifespan (start-up), exactly as uvicorn would.
@pytest.fixture
def client(db_path):
    with TestClient(app) as c:
        yield c


# Direct connection for asserting on rows the API doesn't expose (e.g. event counts).
@pytest.fixture
def conn(db_path):
    c = db.get_connection(str(db_path))
    yield c
    c.close()
