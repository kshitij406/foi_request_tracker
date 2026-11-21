import sqlite3
import os

def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    
    return conn

def init_db(conn, schema_path: str) -> None:
    with open(schema_path, mode="r", encoding="utf-8") as schema:
        data = schema.read()
    conn.executescript(data)
    
def get_db():
    db_path = os.environ.get("FOI_DB_PATH", "foi.db")
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()