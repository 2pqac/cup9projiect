from pathlib import Path
import sys


# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from database.executor import execute_sql
from nl2sql.validator import validate_sql
from nl2sql.schema_validator import validate_tables


def run_query(sql: str):
    """
    完整 SQL 查询流程：

    1. SQL 基础安全检查
    2. Schema 表检查
    3. 数据库执行
    """

    # ==================================================
    # 第一步：基础 SQL 检查
    # ==================================================

    validation = validate_sql(sql)

    if not validation["valid"]:

        return {
            "success": False,
            "stage": "validation",
            "message": validation["message"],
            "data": None
        }

    # ==================================================
    # 第二步：Schema 检查
    # ==================================================

    schema_validation = validate_tables(sql)

    if not schema_validation["valid"]:

        return {
            "success": False,
            "stage": "schema_validation",
            "message": schema_validation["message"],
            "data": None
        }

    # ==================================================
    # 第三步：执行 SQL
    # ==================================================

    try:

        result = execute_sql(sql)

        return {
            "success": True,
            "stage": "execution",
            "message": "查询成功",
            "data": result
        }

    except Exception as e:

        return {
            "success": False,
            "stage": "execution",
            "message": f"数据库执行失败：{e}",
            "data": None
        }


if __name__ == "__main__":

    tests = [

        # ==================================================
        # 测试1：正常SQL
        # ==================================================

        """
        SELECT Country, COUNT(*) AS CustomerCount
        FROM Customer
        GROUP BY Country
        ORDER BY CustomerCount DESC;
        """,

        # ==================================================
        # 测试2：危险SQL
        # ==================================================

        """
        DROP TABLE Customer;
        """,

        # ==================================================
        # 测试3：不存在的表
        # ==================================================

        """
        SELECT *
        FROM NotExistTable;
        """,

        # ==================================================
        # 测试4：JOIN正常
        # ==================================================

        """
        SELECT Artist.Name, Album.Title
        FROM Artist
        JOIN Album
        ON Artist.ArtistId = Album.ArtistId
        LIMIT 5;
        """
    ]

    for sql in tests:

        print("=" * 70)

        print("测试 SQL：")
        print(sql.strip())

        result = run_query(sql)

        print("\n结果：")
        print(result)