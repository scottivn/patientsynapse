"""Admin user management and DB initialization."""

import logging
import aiosqlite
from pathlib import Path
from typing import Optional
import bcrypt

from server.config import get_settings

logger = logging.getLogger(__name__)

_DB_PATH: str = ""

# Valid roles — used for validation on create/update
VALID_ROLES = ("admin", "front_office", "dme", "demo")


def _get_db_path() -> str:
    global _DB_PATH
    if not _DB_PATH:
        settings = get_settings()
        # Strip sqlite:/// prefix
        _DB_PATH = settings.database_url.replace("sqlite:///", "")
    return _DB_PATH


async def init_db():
    """Create admin_users and phi_audit_log tables if they don't exist."""
    db_path = _get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_login TEXT
            )
        """)
        # Migration: add role column to existing tables that lack it
        try:
            await db.execute("SELECT role FROM admin_users LIMIT 1")
        except aiosqlite.OperationalError:
            await db.execute("ALTER TABLE admin_users ADD COLUMN role TEXT NOT NULL DEFAULT 'admin'")
            logger.info("Migrated admin_users: added role column")

        # Migration: add is_active column to existing tables that lack it
        try:
            await db.execute("SELECT is_active FROM admin_users LIMIT 1")
        except aiosqlite.OperationalError:
            await db.execute("ALTER TABLE admin_users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
            logger.info("Migrated admin_users: added is_active column")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS phi_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                user_type TEXT NOT NULL,
                user_id TEXT,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                ip_address TEXT,
                user_agent TEXT
            )
        """)
        await db.commit()
    logger.info("Auth database initialized")


async def seed_default_admin(username: str, password: str):
    """Insert default admin if the admin_users table is empty."""
    if not password:
        logger.info("No ADMIN_DEFAULT_PASSWORD set, skipping admin seed")
        return

    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM admin_users")
        (count,) = await cursor.fetchone()
        if count > 0:
            logger.info("Admin user(s) already exist, skipping seed")
        else:
            hashed = hash_password(password)
            await db.execute(
                "INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, hashed, "admin"),
            )
            await db.commit()
            logger.info(f"Default admin user '{username}' created")

    # Always ensure the demo user exists
    await _seed_demo_user()


async def _seed_demo_user():
    """Ensure a read-only demo user exists for recruiter/portfolio access."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT id FROM admin_users WHERE username = 'demo'"
        )
        if await cursor.fetchone():
            return
        hashed = hash_password("demo")
        await db.execute(
            "INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
            ("demo", hashed, "demo"),
        )
        await db.commit()
        logger.info("Demo user created (username: demo, password: demo)")


async def get_user_by_id(user_id: int) -> dict | None:
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, password_hash, role, is_active, created_at, last_login FROM admin_users WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_username(username: str) -> dict | None:
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, password_hash, role, is_active, created_at, last_login FROM admin_users WHERE username = ?",
            (username,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_users() -> list[dict]:
    """Return all users (without password hashes)."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, role, is_active, created_at, last_login FROM admin_users ORDER BY id"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def create_user(username: str, password: str, role: str = "dme") -> dict:
    """Create a new user. Returns the created user dict (no password hash)."""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")

    db_path = _get_db_path()
    hashed = hash_password(password)
    async with aiosqlite.connect(db_path) as db:
        try:
            cursor = await db.execute(
                "INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, hashed, role),
            )
            await db.commit()
            user_id = cursor.lastrowid
        except aiosqlite.IntegrityError:
            raise ValueError(f"Username '{username}' already exists")

    logger.info(f"User '{username}' created with role '{role}'")
    return {"id": user_id, "username": username, "role": role}


async def update_user(user_id: int, role: Optional[str] = None, is_active: Optional[bool] = None) -> dict | None:
    """Update a user's role and/or active status. Returns updated user or None if not found."""
    if role is not None and role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")

    db_path = _get_db_path()
    updates = []
    params = []
    if role is not None:
        updates.append("role = ?")
        params.append(role)
    if is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if is_active else 0)
    if not updates:
        return await get_user_by_id(user_id)

    params.append(user_id)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"UPDATE admin_users SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        if cursor.rowcount == 0:
            return None
        await db.commit()

    user = await get_user_by_id(user_id)
    changes = []
    if role is not None:
        changes.append(f"role={role}")
    if is_active is not None:
        changes.append(f"is_active={is_active}")
    logger.info(f"User {user_id} updated: {', '.join(changes)}")
    return {"id": user["id"], "username": user["username"], "role": user["role"], "is_active": user["is_active"]}


async def reset_password(user_id: int, new_password: str) -> bool:
    """Reset a user's password. Returns True on success, False if user not found."""
    db_path = _get_db_path()
    hashed = hash_password(new_password)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "UPDATE admin_users SET password_hash = ? WHERE id = ?",
            (hashed, user_id),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return False
    logger.info(f"Password reset for user {user_id}")
    return True


async def delete_user(user_id: int) -> bool:
    """Hard-delete a user. Returns True on success, False if not found."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))
        await db.commit()
        if cursor.rowcount == 0:
            return False
    logger.info(f"User {user_id} deleted")
    return True


async def update_last_login(user_id: int):
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE admin_users SET last_login = datetime('now') WHERE id = ?",
            (user_id,),
        )
        await db.commit()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
