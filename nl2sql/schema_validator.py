import json
from pathlib import Path

import sqlglot
from sqlglot import exp


# ============================================================
# 项目路径
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.json"


# ============================================================
# 读取 Schema
# ============================================================

def load_schema():
    """读取 schema.json"""

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"找不到 Schema 文件：{SCHEMA_PATH}"
        )

    with open(
        SCHEMA_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# ============================================================
# 获取数据库所有表
# ============================================================

def get_schema_tables(schema):
    """返回所有表名"""

    return {
        table_name.lower(): table_info
        for table_name, table_info
        in schema.get("tables", {}).items()
    }


# ============================================================
# 获取某张表的所有字段
# ============================================================

def get_table_columns(table_info):
    """返回某张表的字段集合"""

    return {
        column["name"].lower()
        for column
        in table_info.get("columns", [])
    }


# ============================================================
# 检查 SQL 中使用的表
# ============================================================

def validate_tables(sql: str):
    """
    检查 SQL 使用的表是否存在。
    """

    schema = load_schema()

    schema_tables = get_schema_tables(schema)

    try:

        tree = sqlglot.parse_one(
            sql,
            read="sqlite"
        )

    except Exception as e:

        return {
            "valid": False,
            "message": f"SQL解析失败：{e}"
        }

    # SQL中实际使用的表
    used_tables = set()

    # 表别名映射
    alias_to_table = {}

    for table in tree.find_all(exp.Table):

        table_name = table.name

        if not table_name:
            continue

        used_tables.add(table_name.lower())

        # 表别名
        alias = table.alias

        if alias:
            alias_to_table[alias.lower()] = table_name.lower()

        # 表名本身也可以作为引用
        alias_to_table[table_name.lower()] = table_name.lower()

    # 检查表是否存在
    unknown_tables = []

    for table_name in used_tables:

        if table_name not in schema_tables:
            unknown_tables.append(table_name)

    if unknown_tables:

        return {
            "valid": False,
            "message": (
                "发现不存在的表："
                + ", ".join(sorted(unknown_tables))
            )
        }

    return {
        "valid": True,
        "message": "Schema 表检查通过",
        "tree": tree,
        "schema": schema,
        "alias_to_table": alias_to_table
    }


# ============================================================
# 检查 SQL 中使用的字段
# ============================================================

def validate_columns(sql: str):
    """
    检查 SQL 中使用的字段是否存在。

    支持：
    1. 单表查询
    2. 多表 JOIN
    3. 表名.字段
    4. 表别名.字段
    5. SELECT *
    6. COUNT(*)
    7. SELECT 别名在 ORDER BY 中的引用
    """

    table_result = validate_tables(sql)

    if not table_result["valid"]:
        return table_result

    tree = table_result["tree"]
    schema = table_result["schema"]
    alias_to_table = table_result["alias_to_table"]

    schema_tables = get_schema_tables(schema)

    # --------------------------------------------------------
    # 当前 SQL 实际涉及的表
    # --------------------------------------------------------

    used_table_names = list(
        alias_to_table.values()
    )

    used_table_names = list(
        dict.fromkeys(used_table_names)
    )

    # --------------------------------------------------------
    # 找出 SELECT 中定义的别名
    # 例如：
    # COUNT(*) AS CustomerCount
    #
    # ORDER BY CustomerCount
    #
    # CustomerCount 并不是数据库字段
    # --------------------------------------------------------

    select_aliases = set()

    for alias_node in tree.find_all(exp.Alias):

        alias_name = alias_node.alias

        if alias_name:
            select_aliases.add(
                alias_name.lower()
            )

    # --------------------------------------------------------
    # 检查所有 Column
    # --------------------------------------------------------

    for column in tree.find_all(exp.Column):

        column_name = column.name

        if not column_name:
            continue

        # SELECT * / table.*
        if column_name == "*":
            continue

        column_name_lower = column_name.lower()

        # ORDER BY CustomerCount
        # 这里 CustomerCount 是 SELECT 别名
        if (
            not column.table
            and column_name_lower in select_aliases
        ):
            continue

        # ----------------------------------------------------
        # 情况1：
        # Customer.FirstName
        # Artist.Name
        # a.Title
        # ----------------------------------------------------

        if column.table:

            qualifier = column.table.lower()

            # 根据表名/别名找到真实表
            real_table = alias_to_table.get(
                qualifier
            )

            if not real_table:

                return {
                    "valid": False,
                    "message": (
                        f"字段引用使用了未知的表或别名："
                        f"{column.table}"
                    )
                }

            table_info = schema_tables.get(
                real_table
            )

            if not table_info:

                return {
                    "valid": False,
                    "message": (
                        f"找不到表：{real_table}"
                    )
                }

            valid_columns = get_table_columns(
                table_info
            )

            if column_name_lower not in valid_columns:

                return {
                    "valid": False,
                    "message": (
                        f"表 {real_table} "
                        f"不存在字段：{column_name}"
                    )
                }

        # ----------------------------------------------------
        # 情况2：
        # FirstName
        # Country
        # TrackId
        #
        # 没写表名
        # ----------------------------------------------------

        else:

            matched_tables = []

            for table_name in used_table_names:

                table_info = schema_tables.get(
                    table_name
                )

                if not table_info:
                    continue

                valid_columns = get_table_columns(
                    table_info
                )

                if column_name_lower in valid_columns:

                    matched_tables.append(
                        table_name
                    )

            # 一个表都没有
            if not matched_tables:

                return {
                    "valid": False,
                    "message": (
                        f"找不到字段：{column_name}"
                    )
                }

            # 多个表都有同名字段
            if len(matched_tables) > 1:

                return {
                    "valid": False,
                    "message": (
                        f"字段 {column_name} "
                        f"存在于多个表中，"
                        f"请明确指定表名："
                        + ", ".join(matched_tables)
                    )
                }

    return {
        "valid": True,
        "message": "Schema 字段检查通过"
    }


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":

    test_sql_list = [

        # ----------------------------------------------------
        # 1. 正确
        # ----------------------------------------------------

        """
        SELECT FirstName, LastName
        FROM Customer;
        """,

        # ----------------------------------------------------
        # 2. 正确 JOIN
        # ----------------------------------------------------

        """
        SELECT Artist.Name, Album.Title
        FROM Artist
        JOIN Album
        ON Artist.ArtistId = Album.ArtistId;
        """,

        # ----------------------------------------------------
        # 3. 错误：字段不存在
        # ----------------------------------------------------

        """
        SELECT ABC
        FROM Customer;
        """,

        # ----------------------------------------------------
        # 4. 错误：JOIN 中字段不存在
        # ----------------------------------------------------

        """
        SELECT Artist.Name, Album.ABC
        FROM Artist
        JOIN Album
        ON Artist.ArtistId = Album.ArtistId;
        """,

        # ----------------------------------------------------
        # 5. 正确：COUNT
        # ----------------------------------------------------

        """
        SELECT Country, COUNT(*) AS CustomerCount
        FROM Customer
        GROUP BY Country
        ORDER BY CustomerCount DESC;
        """,

        # ----------------------------------------------------
        # 6. 错误：表不存在
        # ----------------------------------------------------

        """
        SELECT *
        FROM NotExistTable;
        """
    ]


    for sql in test_sql_list:

        print("=" * 70)

        print("SQL：")
        print(sql.strip())

        result = validate_columns(sql)

        print("\n结果：")
        print(result["valid"])

        print("说明：")
        print(result["message"])