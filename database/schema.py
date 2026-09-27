import json
import sqlite3
from pathlib import Path


# 当前脚本所在目录
BASE_DIR = Path(__file__).parent

# 数据库文件
DB_PATH = BASE_DIR / "chinook.db"

# 最终保存的 Schema 文件
SCHEMA_PATH = BASE_DIR / "schema.json"


def get_connection():
    """连接 SQLite 数据库"""
    return sqlite3.connect(DB_PATH)


def get_table_names(conn):
    """获取所有普通数据表名称"""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name;
    """)

    return [row[0] for row in cursor.fetchall()]


def get_columns(conn, table_name):
    """获取某张表的字段信息"""
    cursor = conn.cursor()

    cursor.execute(f'PRAGMA table_info("{table_name}")')

    rows = cursor.fetchall()

    columns = []

    for row in rows:
        # PRAGMA table_info 返回：
        # cid, name, type, notnull, dflt_value, pk
        columns.append({
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "primary_key": bool(row[5]),
        })

    return columns


def get_foreign_keys(conn, table_name):
    """获取某张表的外键信息"""
    cursor = conn.cursor()

    cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')

    rows = cursor.fetchall()

    foreign_keys = []

    for row in rows:
        # 常见 SQLite 返回结构：
        # id, seq, table, from, to, on_update, on_delete, match
        foreign_keys.append({
            "from_column": row[3],
            "to_table": row[2],
            "to_column": row[4],
        })

    return foreign_keys


def build_schema():
    """读取整个数据库 Schema"""
    conn = get_connection()

    try:
        table_names = get_table_names(conn)

        schema = {
            "database": "Chinook",
            "tables": {}
        }

        for table_name in table_names:

            columns = get_columns(conn, table_name)
            foreign_keys = get_foreign_keys(conn, table_name)

            schema["tables"][table_name] = {
                "columns": columns,
                "foreign_keys": foreign_keys
            }

        return schema

    finally:
        conn.close()


def print_schema(schema):
    """把 Schema 打印到终端"""
    print("=" * 70)
    print("Chinook Database Schema")
    print("=" * 70)

    for table_name, table_info in schema["tables"].items():

        print(f"\n[{table_name}]")

        print("字段：")

        for column in table_info["columns"]:

            pk = " [主键]" if column["primary_key"] else ""

            print(
                f"  - {column['name']}"
                f" ({column['type']})"
                f"{pk}"
            )

        if table_info["foreign_keys"]:

            print("外键：")

            for fk in table_info["foreign_keys"]:

                print(
                    f"  - {fk['from_column']}"
                    f" -> "
                    f"{fk['to_table']}.{fk['to_column']}"
                )


def save_schema(schema):
    """把 Schema 保存为 JSON 文件"""

    with open(
        SCHEMA_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            schema,
            f,
            ensure_ascii=False,
            indent=2
        )


def main():

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"找不到数据库：{DB_PATH}"
        )

    schema = build_schema()

    print_schema(schema)

    save_schema(schema)

    print("\n" + "=" * 70)
    print(f"Schema 已保存：{SCHEMA_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()