import sqlite3
import os

def get_connection(db_path: str) -> sqlite3.Connection:
    # FastAPI may run sync endpoints on a different thread than the one that opened the connection.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # rows behave like dicts, so dict(row) works
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores REFERENCES unless this is set per connection
    
    return conn

# Schema uses CREATE ... IF NOT EXISTS, so this is safe to run on every startup.
def init_db(conn, schema_path: str) -> None:
    with open(schema_path, mode="r", encoding="utf-8") as schema:
        data = schema.read()
    conn.executescript(data)
    
# FastAPI dependency: one connection per request, always closed afterwards.
def get_db():
    db_path = os.environ.get("FOI_DB_PATH", "foi.db")
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()