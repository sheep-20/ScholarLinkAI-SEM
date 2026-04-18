"""
Initialize MySQL database and create tables according to README schema.

Priority of configuration sources (highest first):
1) config.yaml (project root) -> database section
2) Environment variables / .env
3) Built-in sensible defaults for MySQL

Tables:
- papers(paper_id, abstract, pdf_url, title, author)
- users(user_id, username, password, interest)
- recommendations(user_id, paper_id, blog)

Usage:
    python backend/service/init_db.py

Environment variables (used when config.yaml is absent or missing keys):
    DATABASE_HOST (default: localhost)
    DATABASE_PORT (default: 3306)
    DATABASE_NAME (default: scholarlink_ai)
    DATABASE_USER (default: root)
    DATABASE_PASSWORD (default: empty)

Note:
- This script uses PyMySQL to talk to MySQL and PyYAML to read config.yaml
- You can also use a .env file. Values in config.yaml override .env/env vars.
"""
from __future__ import annotations

import os
from typing import Optional, Dict, Any

try:
    import pymysql
except ImportError:
    print("[ERROR] PyMySQL 未安装。请先安装依赖: pip install PyMySQL")
    raise

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # 延迟报错，允许无 YAML 时继续使用环境变量

from pymysql.cursors import DictCursor

# 尝试从项目根目录加载 .env（若存在）
try:
    from dotenv import load_dotenv  # type: ignore
    # 允许从 backend 或项目根目录启动
    ROOT_DIR_CANDIDATES = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    ]
    for _p in ROOT_DIR_CANDIDATES:
        env_path = os.path.join(_p, ".env")
        if os.path.isfile(env_path):
            load_dotenv(env_path)
            break
    else:
        load_dotenv()  # fallback to default lookup
except Exception:
    pass


def _project_root_candidates() -> list[str]:
    base = os.path.dirname(__file__)
    return [
        os.path.abspath(os.path.join(base, "..", "..")),  # project root
        os.path.abspath(os.path.join(base, "..")),          # backend
        os.path.abspath(os.path.join(base, ".")),           # service
    ]


def _load_yaml_config() -> Optional[Dict[str, Any]]:
    """Load config.yaml if present. Returns dict or None."""
    for root in _project_root_candidates():
        cfg = os.path.join(root, "config.yaml")
        if os.path.isfile(cfg):
            if yaml is None:
                raise RuntimeError("检测到 config.yaml，但未安装 PyYAML。请先执行: pip install PyYAML")
            with open(cfg, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return None


def _get_db_conf() -> dict:
    """Read DB config with precedence: config.yaml > env/.env > defaults."""
    # defaults
    conf = {
        "host": "localhost",
        "port": 3306,
        "database": "scholarlink_ai",
        "user": "root",
        "password": "",
        "charset": "utf8mb4",
    }

    # env overrides (may be further overridden by YAML below if present)
    conf.update({
        "host": os.getenv("DATABASE_HOST", conf["host"]),
        "port": int(os.getenv("DATABASE_PORT", str(conf["port"]))),
        "database": os.getenv("DATABASE_NAME", conf["database"]),
        "user": os.getenv("DATABASE_USER", conf["user"]),
        "password": os.getenv("DATABASE_PASSWORD", conf["password"]),
    })

    # YAML overrides
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
    except Exception as e:
        print(f"[WARN] 读取 config.yaml 失败，改用环境变量: {e}")

    return conf


def _connect(db: Optional[str] = None) -> pymysql.connections.Connection:
    conf = _get_db_conf()
    if db is not None:
        conf["database"] = db
    else:
        conf.pop("database", None)
    return pymysql.connect(
        host=conf["host"],
        port=conf["port"],
        user=conf["user"],
        password=conf["password"],
        database=conf.get("database"),
        charset=conf["charset"],
        autocommit=True,
        cursorclass=DictCursor,
    )


def create_database_if_not_exists() -> None:
    conf = _get_db_conf()
    db_name = conf["database"]
    print(f"[INFO] 尝试创建数据库（若不存在）：{db_name}")
    with _connect(db=None) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
    print("[OK] 数据库已准备就绪")


def create_tables() -> None:
    conf = _get_db_conf()
    db_name = conf["database"]
    print(f"[INFO] 在数据库 `{db_name}` 中创建数据表（若不存在）...")
    with _connect(db=db_name) as conn:
        with conn.cursor() as cur:
            # papers 表
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `papers` (
                    `paper_id` INT AUTO_INCREMENT PRIMARY KEY,
                    `abstract` TEXT,
                    `pdf_url` VARCHAR(512),
                    `title` VARCHAR(255) NOT NULL,
                    `author` VARCHAR(255)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # users 表
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `users` (
                    `user_id` INT AUTO_INCREMENT PRIMARY KEY,
                    `username` VARCHAR(100) NOT NULL UNIQUE,
                    `password` VARCHAR(255) NOT NULL,
                    `interest` VARCHAR(255)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # recommendations 表
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `recommendations` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` INT NOT NULL,
                    `paper_id` INT NOT NULL,
                    `blog` TEXT,
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT `fk_reco_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`user_id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_reco_paper` FOREIGN KEY (`paper_id`) REFERENCES `papers`(`paper_id`) ON DELETE CASCADE,
                    UNIQUE KEY `uniq_user_paper` (`user_id`, `paper_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # paper_embeddings 表
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `paper_embeddings` (
                    `paper_id` INT PRIMARY KEY,
                    `embedding` TEXT NOT NULL,
                    CONSTRAINT `fk_paper_emb` FOREIGN KEY (`paper_id`) REFERENCES `papers`(`paper_id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # interest_embeddings 表
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `interest_embeddings` (
                    `user_id` INT PRIMARY KEY,
                    `embedding` LONGTEXT NOT NULL,
                    CONSTRAINT `fk_interest_emb` FOREIGN KEY (`user_id`) REFERENCES `users`(`user_id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # paper_liked 表
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `paper_liked` (
                    `user_id` INT NOT NULL,
                    `paper_id` INT NOT NULL,
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`user_id`, `paper_id`),
                    CONSTRAINT `fk_like_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`user_id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_like_paper` FOREIGN KEY (`paper_id`) REFERENCES `papers`(`paper_id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # chat_history 表
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `chat_history` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `recommendation_id` INT NOT NULL,
                    `user_message` TEXT NOT NULL,
                    `ai_response` TEXT NOT NULL,
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT `fk_chat_reco` FOREIGN KEY (`recommendation_id`) REFERENCES `recommendations`(`id`) ON DELETE CASCADE,
                    INDEX `idx_recommendation_id` (`recommendation_id`),
                    INDEX `idx_created_at` (`created_at`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # 检查并升级embedding字段类型（如果表已存在但字段类型不匹配）
            try:
                cur.execute("ALTER TABLE `paper_embeddings` MODIFY COLUMN `embedding` LONGTEXT NOT NULL")
                print("[INFO] 已升级 paper_embeddings.embedding 字段为 LONGTEXT")
            except Exception:
                # 字段类型已正确或升级失败，忽略错误
                pass

            try:
                cur.execute("ALTER TABLE `interest_embeddings` MODIFY COLUMN `embedding` LONGTEXT NOT NULL")
                print("[INFO] 已升级 interest_embeddings.embedding 字段为 LONGTEXT")
            except Exception:
                # 字段类型已正确或升级失败，忽略错误
                pass

    print("[OK] 数据表已准备就绪")


def init_database() -> None:
    conf = _get_db_conf()
    masked_pwd = "***" if conf["password"] else "(empty)"
    print("-" * 60)
    print("ScholarLinkAI 数据库初始化开始")
    print(
        f"host={conf['host']}, port={conf['port']}, user={conf['user']}, password={masked_pwd}, db={conf.get('database','<none>')}"
    )
    print("-" * 60)

    try:
        create_database_if_not_exists()
        create_tables()
        print("[SUCCESS] 数据库初始化完成 ✅")
    except pymysql.err.OperationalError as e:
        print(
            f"[ERROR] 无法连接到 MySQL: {e}\n\n"
            f"请检查: \n"
            f"  1) MySQL 服务是否已启动\n"
            f"  2) 连接参数是否正确（主机、端口、用户、密码）\n"
            f"  3) 用户是否有创建数据库/表的权限\n"
        )
        raise
    except Exception as e:
        print(f"[ERROR] 初始化失败: {e}")
        raise


if __name__ == "__main__":
    # 运行方式：python backend/service/init_db.py
    # 也可在项目根目录运行：python -m backend.service.init_db
    init_database()
