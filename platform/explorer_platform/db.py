"""SQLite storage for user accounts. Mirrors auto_compact/db.py pattern."""

import sqlite3
from pathlib import Path


def init_db(db_path: Path | str) -> sqlite3.Connection:
    """Initialize the database, creating tables if needed."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              TEXT PRIMARY KEY,
            email           TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            tier            TEXT DEFAULT 'unknown',
            claude_token    TEXT,
            wolfram_key     TEXT,
            vm_id           TEXT,
            vm_zone         TEXT,
            vm_status       TEXT DEFAULT 'none',
            vm_internal_ip  TEXT,
            vm_agent_token  TEXT
        );
    """)
    return conn


def create_user(
    conn: sqlite3.Connection,
    user_id: str,
    email: str,
    password_hash: str,
    created_at: str,
) -> None:
    """Insert a new user. Raises sqlite3.IntegrityError on duplicate email."""
    conn.execute(
        "INSERT INTO users (id, email, password_hash, created_at) "
        "VALUES (?, ?, ?, ?)",
        (user_id, email, password_hash, created_at),
    )
    conn.commit()


def get_user_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    """Look up a user by email."""
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    return dict(row) if row else None


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> dict | None:
    """Look up a user by ID."""
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def update_user_field(
    conn: sqlite3.Connection, user_id: str, field: str, value: str | None
) -> None:
    """Update a single field on a user. Field name is NOT from user input."""
    allowed = {
        "claude_token", "wolfram_key", "tier",
        "vm_id", "vm_zone", "vm_status", "vm_internal_ip", "vm_agent_token",
    }
    if field not in allowed:
        raise ValueError(f"Cannot update field: {field}")
    conn.execute(f"UPDATE users SET {field} = ? WHERE id = ?", (value, user_id))
    conn.commit()
