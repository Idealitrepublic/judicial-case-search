import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("JUDICIAL_DB", "judgments.db")

@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with connect() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS judgments (
            jid TEXT PRIMARY KEY,
            year TEXT,
            case_type TEXT,
            case_no TEXT,
            date TEXT,
            title TEXT,
            content TEXT NOT NULL,
            full_type TEXT,
            pdf_url TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS judgments_fts USING fts5(
            jid UNINDEXED, title, content, content='judgments', content_rowid='rowid'
        )
        """)
        db.execute("""
        CREATE TRIGGER IF NOT EXISTS judgments_ai AFTER INSERT ON judgments BEGIN
          INSERT INTO judgments_fts(rowid, jid, title, content)
          VALUES (new.rowid, new.jid, new.title, new.content);
        END;
        """)
        db.execute("""
        CREATE TRIGGER IF NOT EXISTS judgments_ad AFTER DELETE ON judgments BEGIN
          INSERT INTO judgments_fts(judgments_fts, rowid, jid, title, content)
          VALUES ('delete', old.rowid, old.jid, old.title, old.content);
        END;
        """)
        db.execute("""
        CREATE TRIGGER IF NOT EXISTS judgments_au AFTER UPDATE ON judgments BEGIN
          INSERT INTO judgments_fts(judgments_fts, rowid, jid, title, content)
          VALUES ('delete', old.rowid, old.jid, old.title, old.content);
          INSERT INTO judgments_fts(rowid, jid, title, content)
          VALUES (new.rowid, new.jid, new.title, new.content);
        END;
        """)

def upsert_judgment(item):
    with connect() as db:
        db.execute("""
        INSERT INTO judgments(jid, year, case_type, case_no, date, title, content, full_type, pdf_url)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(jid) DO UPDATE SET
          year=excluded.year, case_type=excluded.case_type, case_no=excluded.case_no,
          date=excluded.date, title=excluded.title, content=excluded.content,
          full_type=excluded.full_type, pdf_url=excluded.pdf_url,
          updated_at=CURRENT_TIMESTAMP
        """, (
            item["jid"], item.get("year", ""), item.get("case_type", ""),
            item.get("case_no", ""), item.get("date", ""), item.get("title", ""),
            item.get("content", ""), item.get("full_type", ""), item.get("pdf_url", "")
        ))

def delete_judgment(jid):
    with connect() as db:
        db.execute("DELETE FROM judgments WHERE jid = ?", (jid,))

def search_judgments(query, limit=20):
    with connect() as db:
        rows = db.execute("""
        SELECT j.jid, j.year, j.case_type, j.case_no, j.date, j.title,
               snippet(judgments_fts, 2, '<mark>', '</mark>', ' … ', 35) AS snippet
        FROM judgments_fts f
        JOIN judgments j ON j.rowid = f.rowid
        WHERE judgments_fts MATCH ?
        ORDER BY j.date DESC, j.jid DESC
        LIMIT ?
        """, (query, limit)).fetchall()
        return [dict(r) for r in rows]

def get_judgment(jid):
    with connect() as db:
        row = db.execute("SELECT * FROM judgments WHERE jid = ?", (jid,)).fetchone()
        return dict(row) if row else None
