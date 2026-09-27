import sqlglot
from sqlglot import exp


# 允许执行的 SQL 类型
ALLOWED_TYPES = (
    exp.Select,
    exp.Union,
)


# 明确禁止的 SQL 类型
FORBIDDEN_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
)


def validate_sql(sql: str) -> dict:
    """
    检查 SQL 是否符合我们的基本安全规则。

    返回：
    {
        "valid": True/False,
        "message": "检查结果"
    }
    """

    # ---------- 1. 基础检查 ----------
    if not sql or not sql.strip():
        return {
            "valid": False,
            "message": "SQL 不能为空"
        }

    sql = sql.strip()

    # ---------- 2. 解析 SQL ----------
    try:
        tree = sqlglot.parse_one(
            sql,
            read="sqlite"
        )
    except Exception as e:
        return {
            "valid": False,
            "message": f"SQL 语法错误：{e}"
        }

    # ---------- 3. 检查是否为查询 ----------
    if not isinstance(tree, ALLOWED_TYPES):
        return {
            "valid": False,
            "message": "只允许 SELECT 查询"
        }

    # ---------- 4. 检查危险操作 ----------
    for forbidden_type in FORBIDDEN_TYPES:

        if tree.find(forbidden_type):

            return {
                "valid": False,
                "message": (
                    f"检测到禁止的 SQL 操作："
                    f"{forbidden_type.__name__}"
                )
            }

    # ---------- 5. 检查通过 ----------
    return {
        "valid": True,
        "message": "SQL 检查通过"
    }


if __name__ == "__main__":

    test_sql_list = [
        "SELECT * FROM Customer;",
        "SELECT COUNT(*) FROM Customer;",
        "DROP TABLE Customer;",
        "DELETE FROM Customer;",
        "SELECT * FROM NotExistTable;",
        "SELECT Country, COUNT(*) FROM Customer GROUP BY Country;"
    ]

    for sql in test_sql_list:

        print("=" * 60)
        print("SQL：")
        print(sql)

        result = validate_sql(sql)

        print("结果：", result["valid"])
        print("说明：", result["message"])