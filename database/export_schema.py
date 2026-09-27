"""从 chinook.db 导出所有用户表的建表语句到 schema.sql。"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
conn = sqlite3.connect(BASE / "chinook.db")
cur = conn.cursor()
cur.execute(
    "SELECT name, sql FROM sqlite_master "
    "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
)
rows = cur.fetchall()
conn.close()

parts = [
    "-- Chinook 数据库 Schema 定义（SQLite）",
    "-- 由 database/export_schema.py 自动导出",
    "",
]
for name, sql in rows:
    parts.append(sql.strip() + ";")
    parts.append("")

(BASE / "schema.sql").write_text("\n".join(parts), encoding="utf-8")
print(f"schema.sql 已生成，共 {len(rows)} 张表")
