"""
database.py
SQLite database for admins, exam centres, question papers and generated copies.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "leak_detector.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS admin (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS centres (
    centre_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    centre_name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    paper_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_name  TEXT NOT NULL,
    source_file TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS copies (
    copy_id    TEXT PRIMARY KEY,
    paper_id   INTEGER NOT NULL,
    centre_id  INTEGER NOT NULL,
    image_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (paper_id)  REFERENCES papers(paper_id),
    FOREIGN KEY (centre_id) REFERENCES centres(centre_id)
);
"""


@contextmanager
def get_db():
    """Open a connection, commit on success, always close."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row            # rows behave like dictionaries
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now_text() -> str:
    return datetime.now().strftime("%d-%m-%Y %H:%M")


def init_db():
    """Create all tables if they do not exist yet."""
    with get_db() as conn:
        conn.executescript(SCHEMA)


# ---------------- Admin ----------------
def get_admin(username: str):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM admin WHERE username = ?", (username,)
        ).fetchone()


def save_admin(username: str, password_hash: str) -> bool:
    """Create the admin, or update the password if it exists. True if created."""
    with get_db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM admin WHERE username = ?", (username,)
        ).fetchone()
        if exists:
            conn.execute(
                "UPDATE admin SET password_hash = ? WHERE username = ?",
                (password_hash, username),
            )
            return False
        conn.execute(
            "INSERT INTO admin (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        return True


# ---------------- Centres ----------------
def get_or_create_centre(centre_name: str) -> int:
    """Return the id of a centre, creating it the first time it is used."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT centre_id FROM centres WHERE centre_name = ?", (centre_name,)
        ).fetchone()
        if row:
            return row["centre_id"]
        cur = conn.execute(
            "INSERT INTO centres (centre_name) VALUES (?)", (centre_name,)
        )
        return cur.lastrowid


# ---------------- Papers ----------------
def add_paper(paper_name: str, source_file: str) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO papers (paper_name, source_file, created_at) VALUES (?, ?, ?)",
            (paper_name, source_file, now_text()),
        )
        return cur.lastrowid


# ---------------- Copies ----------------
def add_copy(copy_id: str, paper_id: int, centre_id: int,
             image_hash: str, created_at: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO copies (copy_id, paper_id, centre_id, image_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (copy_id, paper_id, centre_id, image_hash, created_at),
        )


_COPY_QUERY = """
    SELECT c.copy_id, c.created_at, c.image_hash,
           p.paper_id, p.paper_name,
           ce.centre_id, ce.centre_name
    FROM copies c
    JOIN papers  p  ON p.paper_id   = c.paper_id
    JOIN centres ce ON ce.centre_id = c.centre_id
"""


def get_copy(copy_id: str):
    with get_db() as conn:
        return conn.execute(
            _COPY_QUERY + " WHERE c.copy_id = ?", (copy_id,)
        ).fetchone()


def list_copies():
    with get_db() as conn:
        return conn.execute(
            _COPY_QUERY + " ORDER BY p.paper_id DESC, ce.centre_id"
        ).fetchall()


# ---------------- Self-test ----------------
if __name__ == "__main__":
    init_db()
    with get_db() as conn:
        tables = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
    print("Database ready:", DB_PATH)
    print("Tables:", ", ".join(tables))