import sqlite3
from pathlib import Path


# 数据库文件路径
DB_PATH = Path(__file__).parent / "chinook.db"


def execute_sql(sql: str, db_path=None):
    """
    执行一条 SQL，并返回查询结果。

    当前版本只适合执行 SELECT 查询。
    db_path 可注入其它 SQLite 库（默认 Chinook）。
    """

    sql = sql.strip()

    if not sql:
        raise ValueError("SQL 不能为空")

    # 最基础的安全检查
    if not sql.lower().startswith("select"):
        raise ValueError("当前执行器只允许 SELECT 查询")

    # 连接 SQLite 数据库
    conn = sqlite3.connect(db_path or DB_PATH)

    try:
        cursor = conn.cursor()

        # 执行 SQL
        cursor.execute(sql)

        # 获取所有结果
        rows = cursor.fetchall()

        # 获取字段名
        columns = [
            description[0]
            for description in cursor.description
        ]

        return {
            "columns": columns,
            "rows": rows
        }

    finally:
        conn.close()


if __name__ == "__main__":

    test_sql = """
    SELECT Country, COUNT(*) AS CustomerCount
    FROM Customer
    GROUP BY Country
    ORDER BY CustomerCount DESC;
    """

    result = execute_sql(test_sql)

    print("查询字段：")
    print(result["columns"])

    print("\n查询结果：")

    for row in result["rows"]:
        print(row)