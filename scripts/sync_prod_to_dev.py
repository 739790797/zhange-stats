#!/usr/bin/env python3
"""将生产库 zhange_stats 整库同步到开发库 zhange_stats_dev（同机 MariaDB 最快）。

用法（在仓库根目录）:
  backend\\.venv\\Scripts\\python.exe scripts\\sync_prod_to_dev.py

默认从 .env.production / .env 读取 DATABASE_URL；也可用环境变量覆盖:
  SYNC_SOURCE_URL / SYNC_TARGET_URL
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def parse_mysql_url(url: str) -> dict:
    # mysql+pymysql://user:pass@host:3306/dbname
    url = re.sub(r"^mysql\+pymysql://", "mysql://", url)
    parsed = urlparse(url)
    if parsed.scheme not in ("mysql", "mariadb"):
        raise ValueError(f"不支持的 DATABASE_URL: {url!r}")
    db = (parsed.path or "").lstrip("/")
    if not db:
        raise ValueError(f"DATABASE_URL 缺少库名: {url!r}")
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "database": db,
        "charset": "utf8mb4",
    }


def connect(cfg: dict, database: str | None = None):
    kwargs = {**cfg}
    if database is not None:
        kwargs["database"] = database
    return pymysql.connect(**kwargs, cursorclass=pymysql.cursors.DictCursor, autocommit=False)


def list_base_tables(cur, schema: str) -> list[str]:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
        (schema,),
    )
    return [r["table_name"] for r in cur.fetchall()]


def quote_ident(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def main() -> int:
    prod_env = load_dotenv(ROOT / ".env.production")
    dev_env = load_dotenv(ROOT / ".env")

    source_url = os.environ.get("SYNC_SOURCE_URL") or prod_env.get("DATABASE_URL")
    target_url = os.environ.get("SYNC_TARGET_URL") or dev_env.get("DATABASE_URL")
    if not source_url or not target_url:
        print("缺少 DATABASE_URL：请配置 .env.production / .env，或设置 SYNC_*_URL", file=sys.stderr)
        return 1

    source = parse_mysql_url(source_url)
    target = parse_mysql_url(target_url)

    if source["database"] == target["database"]:
        print("源库与目标库同名，拒绝同步以免覆盖生产。", file=sys.stderr)
        return 1
    if "dev" not in target["database"].lower() and target["database"] == "zhange_stats":
        print(f"目标库 {target['database']!r} 看起来像生产库，已中止。", file=sys.stderr)
        return 1

    print(f"源: {source['host']}:{source['port']}/{source['database']}")
    print(f"目标: {target['host']}:{target['port']}/{target['database']}")

    # 同机同账号时用一条连接跨库复制；否则走客户端中转
    same_server = (
        source["host"] == target["host"]
        and source["port"] == target["port"]
        and source["user"] == target["user"]
        and source["password"] == target["password"]
    )

    src_conn = connect(source)
    try:
        with src_conn.cursor() as cur:
            tables = list_base_tables(cur, source["database"])
        if not tables:
            print("源库没有表，退出。")
            return 1
        print(f"将同步 {len(tables)} 张表: {', '.join(tables)}")

        if same_server:
            with src_conn.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS {quote_ident(target['database'])} "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                cur.execute("SET FOREIGN_KEY_CHECKS=0")
                # 先删目标库全部基表
                dest_tables = list_base_tables(cur, target["database"])
                for t in dest_tables:
                    cur.execute(
                        f"DROP TABLE IF EXISTS {quote_ident(target['database'])}.{quote_ident(t)}"
                    )
                for t in tables:
                    src_t = f"{quote_ident(source['database'])}.{quote_ident(t)}"
                    dst_t = f"{quote_ident(target['database'])}.{quote_ident(t)}"
                    cur.execute(f"CREATE TABLE {dst_t} LIKE {src_t}")
                    cur.execute(f"INSERT INTO {dst_t} SELECT * FROM {src_t}")
                    cur.execute(f"SELECT COUNT(*) AS c FROM {dst_t}")
                    count = cur.fetchone()["c"]
                    print(f"  {t}: {count} 行")
                cur.execute("SET FOREIGN_KEY_CHECKS=1")
            src_conn.commit()
        else:
            tgt_conn = connect({**target, "database": None})
            try:
                with tgt_conn.cursor() as tcur:
                    tcur.execute(
                        f"CREATE DATABASE IF NOT EXISTS {quote_ident(target['database'])} "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                tgt_conn.commit()
                tgt_conn.select_db(target["database"])

                with src_conn.cursor() as scur, tgt_conn.cursor() as tcur:
                    tcur.execute("SET FOREIGN_KEY_CHECKS=0")
                    for t in list_base_tables(tcur, target["database"]):
                        tcur.execute(f"DROP TABLE IF EXISTS {quote_ident(t)}")

                    for t in tables:
                        scur.execute(f"SHOW CREATE TABLE {quote_ident(source['database'])}.{quote_ident(t)}")
                        create_sql = scur.fetchone()["Create Table"]
                        tcur.execute(create_sql)
                        scur.execute(f"SELECT * FROM {quote_ident(source['database'])}.{quote_ident(t)}")
                        rows = scur.fetchall()
                        if rows:
                            cols = list(rows[0].keys())
                            placeholders = ", ".join(["%s"] * len(cols))
                            col_list = ", ".join(quote_ident(c) for c in cols)
                            sql = f"INSERT INTO {quote_ident(t)} ({col_list}) VALUES ({placeholders})"
                            tcur.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
                        print(f"  {t}: {len(rows)} 行")
                    tcur.execute("SET FOREIGN_KEY_CHECKS=1")
                tgt_conn.commit()
            finally:
                tgt_conn.close()
    finally:
        src_conn.close()

    print("完成：生产数据已同步到开发库。")
    print("提示：头像等文件若在生产机 uploads/，需另行复制到本地 UPLOAD_DIR。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
