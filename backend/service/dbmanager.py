"""
DbManager - Simple MySQL access helper using PyMySQL.

Configuration precedence (highest first):
1) config.yaml at project root (database section)
2) Environment variables / .env
3) Built-in MySQL defaults

Environment variables (when config.yaml is absent or partial):
- DATABASE_HOST (default: localhost)
- DATABASE_PORT (default: 3306)
- DATABASE_NAME (default: scholarlink_ai)
- DATABASE_USER (default: root)
- DATABASE_PASSWORD (default: empty)

Example:
    from service.dbmanager import DbManager

    db = DbManager()
    users = db.query_all("SELECT * FROM users LIMIT %s", (5,))
    print(users)

    # transaction example
    with db.transaction() as cur:
        cur.execute("INSERT INTO users(username, password) VALUES(%s,%s)", ("alice", "xxx"))
        cur.execute("UPDATE users SET interest=%s WHERE username=%s", ("ML", "alice"))
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:  # pragma: no cover - dependency error message
    raise RuntimeError("PyMySQL 未安装，请先执行: pip install PyMySQL")

# Optional YAML support
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

# Try load .env if present
try:  # pragma: no cover - best effort
    from dotenv import load_dotenv  # type: ignore
    for _p in [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),  # project root
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),          # backend
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),           # service
    ]:
        env_path = os.path.join(_p, ".env")
        if os.path.isfile(env_path):
            load_dotenv(env_path)
            break
    else:
        load_dotenv()
except Exception:
    pass


def _project_root_candidates() -> List[str]:
    base = os.path.dirname(__file__)
    return [
        os.path.abspath(os.path.join(base, "..", "..")),
        os.path.abspath(os.path.join(base, "..")),
        os.path.abspath(os.path.join(base, ".")),
    ]


def _load_yaml_config() -> Optional[Dict[str, Any]]:
    for root in _project_root_candidates():
        cfg = os.path.join(root, "config.yaml")
        if os.path.isfile(cfg):
            if yaml is None:
                raise RuntimeError("检测到 config.yaml，但未安装 PyYAML。请先执行: pip install PyYAML")
            with open(cfg, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return None


def _resolve_db_conf() -> Dict[str, Any]:
    # defaults
    conf: Dict[str, Any] = {
        "host": "localhost",
        "port": 3306,
        "database": "scholarlink_ai",
        "user": "root",
        "password": "",
        "charset": "utf8mb4",
        "autocommit": True,
    }

    # env overrides
    conf.update({
        "host": os.getenv("DATABASE_HOST", conf["host"]),
        "port": int(os.getenv("DATABASE_PORT", str(conf["port"]))),
        "database": os.getenv("DATABASE_NAME", conf["database"]),
        "user": os.getenv("DATABASE_USER", conf["user"]),
        "password": os.getenv("DATABASE_PASSWORD", conf["password"]),
    })

    # YAML overrides if available
    try:
        data = _load_yaml_config()
        if data and isinstance(data, dict):
            db = data.get("database") or {}
            if isinstance(db, dict):
                conf["host"] = db.get("host", conf["host"]) or conf["host"]
                conf["port"] = int(db.get("port", conf["port"]))
                conf["database"] = db.get("name", conf["database"]) or conf["database"]
                conf["user"] = db.get("user", conf["user"]) or conf["user"]
                conf["password"] = db.get("password", conf["password"]) or conf["password"]
                conf["charset"] = db.get("charset", conf["charset"]) or conf["charset"]
    except Exception as e:  # pragma: no cover
        print(f"[WARN] 读取 config.yaml 失败，改用环境变量: {e}")

    return conf


class DbManager:
    """Lightweight database access helper for MySQL using PyMySQL.

    Provides:
    - get_connection: raw connection (caller responsible for closing)
    - query_one / query_all: SELECT helpers returning dict rows
    - execute / executemany: DML helpers returning rowcount and lastrowid
    - transaction: context manager for BEGIN/COMMIT/ROLLBACK
    """

    def __init__(self, override: Optional[Dict[str, Any]] = None) -> None:
        conf = _resolve_db_conf()
        if override:
            conf.update(override)
        self._conf = conf

    # --- connection ---
    def get_connection(self, with_db: bool = True) -> pymysql.connections.Connection:
        params = dict(self._conf)
        if not with_db:
            params = {k: v for k, v in params.items() if k != "database"}
        return pymysql.connect(
            host=params["host"],
            port=params["port"],
            user=params["user"],
            password=params["password"],
            database=params.get("database"),
            charset=params["charset"],
            autocommit=params.get("autocommit", True),
            cursorclass=DictCursor,
        )

    def ping(self) -> bool:
        try:
            with self.get_connection() as conn:
                conn.ping(reconnect=True)
            return True
        except Exception:
            return False

    # --- querying ---
    def query_one(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                row = cur.fetchone()
                return row

    def query_all(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                rows = cur.fetchall()
                return list(rows)

    # --- DML ---
    def execute(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> Dict[str, Any]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                return {"rowcount": cur.rowcount, "lastrowid": cur.lastrowid}

    def executemany(self, sql: str, seq_of_params: Iterable[Tuple[Any, ...]]) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, list(seq_of_params))
                return cur.rowcount

    # --- transaction ---
    @contextmanager
    def transaction(self):
        """Provide a cursor in a transaction (autocommit off). Commit on success, rollback on error.
        Usage:
            with db.transaction() as cur:
                cur.execute(...)
                cur.execute(...)
        """
        conn = self.get_connection()
        try:
            conn.autocommit(False)
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
        finally:
            conn.autocommit(True)
            conn.close()


__all__ = ["DbManager"]

