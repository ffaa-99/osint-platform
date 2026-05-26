from pathlib import Path
import sqlite3
import json
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / "osint_data.db"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS searches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            target      TEXT    NOT NULL,
            search_type TEXT    NOT NULL DEFAULT 'username',
            found_count INTEGER NOT NULL DEFAULT 0,
            total_count INTEGER NOT NULL DEFAULT 0,
            results     TEXT    NOT NULL DEFAULT '[]',
            created_at  TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_target      ON searches(target);
        CREATE INDEX IF NOT EXISTS idx_search_type ON searches(search_type);
        CREATE INDEX IF NOT EXISTS idx_created_at  ON searches(created_at);
    """)
    conn.commit()
    conn.close()


def save_search(target: str, search_type: str, results: list) -> int:
    found = sum(1 for r in results if r.get("status") == "FOUND")
    conn  = get_conn()
    cur   = conn.execute(
        """INSERT INTO searches (target, search_type, found_count, total_count, results, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (target, search_type, found, len(results),
         json.dumps(results), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_all_searches(limit: int = 50) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, target, search_type, found_count, total_count, created_at "
        "FROM searches ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_search_by_id(search_id: int) -> dict | None:
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM searches WHERE id = ?", (search_id,)
    ).fetchone()
    conn.close()
    if row:
        data = dict(row)
        data["results"] = json.loads(data["results"])
        return data
    return None


def delete_search(search_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM searches WHERE id = ?", (search_id,))
    conn.commit()
    conn.close()


def get_stats() -> dict:
    conn  = get_conn()
    row   = conn.execute(
        "SELECT COUNT(*) as total, "
        "SUM(found_count) as total_found, "
        "COUNT(DISTINCT target) as unique_targets "
        "FROM searches"
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


init_db()