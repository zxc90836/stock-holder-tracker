import sqlite3
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "stockbot.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                line_user_id TEXT NOT NULL,
                stock_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(line_user_id, stock_id)
            )
            """
        )
        conn.commit()


def add_watchlist(line_user_id: str, stock_id: str) -> bool:
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_watchlist (line_user_id, stock_id)
                VALUES (?, ?)
                """,
                (line_user_id, stock_id),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def remove_watchlist(line_user_id: str, stock_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM user_watchlist
            WHERE line_user_id = ? AND stock_id = ?
            """,
            (line_user_id, stock_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def list_watchlist(line_user_id: str) -> List[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT stock_id
            FROM user_watchlist
            WHERE line_user_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (line_user_id,),
        ).fetchall()
        return [row["stock_id"] for row in rows]