import sqlite3
from pathlib import Path


# ============================================================
# 1. 项目路径
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = PROJECT_ROOT / "database" / "chinook.db"


# ============================================================
# 2. 中文关键词 -> 数据表
# ============================================================

TABLE_ALIASES = {
    "歌手": ["Artist"],
    "艺术家": ["Artist"],

    "专辑": ["Album"],

    "歌曲": ["Track"],
    "音乐": ["Track"],

    "客户": ["Customer"],
    "顾客": ["Customer"],

    "员工": ["Employee"],

    "发票": ["Invoice"],
    "订单": ["Invoice"],

    "订单明细": ["InvoiceLine"],
    "发票明细": ["InvoiceLine"],

    "音乐类型": ["Genre"],
    "流派": ["Genre"],

    "媒体类型": ["MediaType"],

    "播放列表": ["Playlist"],
    "歌单": ["Playlist"],
}


# ============================================================
# 3. 中文关键词 -> 精确字段
# ============================================================

FIELD_ALIASES = {

    # -------------------------
    # Artist
    # -------------------------

    "歌手": [
        ("Artist", "Name")
    ],

    "艺术家": [
        ("Artist", "Name")
    ],

    "歌手姓名": [
        ("Artist", "Name")
    ],


    # -------------------------
    # Album
    # -------------------------

    "专辑": [
        ("Album", "Title")
    ],

    "专辑名": [
        ("Album", "Title")
    ],

    "专辑名称": [
        ("Album", "Title")
    ],


    # -------------------------
    # Track
    # -------------------------

    "歌曲": [
        ("Track", "Name")
    ],

    "歌曲名": [
        ("Track", "Name")
    ],

    "歌曲名称": [
        ("Track", "Name")
    ],


    # -------------------------
    # Genre
    # -------------------------

    "音乐类型": [
        ("Genre", "Name")
    ],

    "流派": [
        ("Genre", "Name")
    ],


    # -------------------------
    # Customer
    # -------------------------

    "客户": [
        ("Customer", "CustomerId")
    ],

    "顾客": [
        ("Customer", "CustomerId")
    ],

    "国家": [
        ("Customer", "Country")
    ],

    "所在国家": [
        ("Customer", "Country")
    ],

    "城市": [
        ("Customer", "City")
    ],

    "所在城市": [
        ("Customer", "City")
    ],

    "地址": [
        ("Customer", "Address")
    ],

    "邮箱": [
        ("Customer", "Email")
    ],

    "电子邮箱": [
        ("Customer", "Email")
    ],

    "电话": [
        ("Customer", "Phone")
    ],

    "名字": [
        ("Customer", "FirstName")
    ],

    "姓": [
        ("Customer", "LastName")
    ],

    "公司": [
        ("Customer", "Company")
    ],


    # -------------------------
    # Invoice
    # -------------------------

    "金额": [
        ("Invoice", "Total")
    ],

    "总金额": [
        ("Invoice", "Total")
    ],

    "总价": [
        ("Invoice", "Total")
    ],

    "订单日期": [
        ("Invoice", "InvoiceDate")
    ],

    "日期": [
        ("Invoice", "InvoiceDate")
    ],


    # -------------------------
    # InvoiceLine
    # -------------------------

    "单价": [
        ("InvoiceLine", "UnitPrice")
    ],

    "价格": [
        ("InvoiceLine", "UnitPrice")
    ],

    "数量": [
        ("InvoiceLine", "Quantity")
    ],


    # -------------------------
    # Track
    # -------------------------

    "作曲家": [
        ("Track", "Composer")
    ],

    "作曲": [
        ("Track", "Composer")
    ],

    "时长": [
        ("Track", "Milliseconds")
    ],

    "播放时长": [
        ("Track", "Milliseconds")
    ],
}


# ============================================================
# 4. 中文数据值 -> SQLite 中的真实值
# ============================================================

VALUE_ALIASES = {

    # 国家

    "美国": [
        ("Customer", "Country", "USA")
    ],

    "中国": [
        ("Customer", "Country", "China")
    ],

    "英国": [
        ("Customer", "Country", "United Kingdom")
    ],

    "加拿大": [
        ("Customer", "Country", "Canada")
    ],

    "法国": [
        ("Customer", "Country", "France")
    ],

    "德国": [
        ("Customer", "Country", "Germany")
    ],

    "巴西": [
        ("Customer", "Country", "Brazil")
    ],

    "印度": [
        ("Customer", "Country", "India")
    ],

    "葡萄牙": [
        ("Customer", "Country", "Portugal")
    ],

    "捷克": [
        ("Customer", "Country", "Czech Republic")
    ],


    # 音乐类型

    "摇滚": [
        ("Genre", "Name", "Rock")
    ],

    "爵士": [
        ("Genre", "Name", "Jazz")
    ],

    "金属": [
        ("Genre", "Name", "Metal")
    ],

    "古典": [
        ("Genre", "Name", "Classical")
    ],

    "流行": [
        ("Genre", "Name", "Pop")
    ],
}


# ============================================================
# 5. 读取 SQLite 数据库结构
# ============================================================

def load_database_schema():
    """
    直接从 Chinook SQLite 数据库读取真正的：

    1. 表
    2. 字段
    3. 主键
    4. 外键

    这样不会因为 schema.json 格式变化导致
    主键、外键解析错误。
    """

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"找不到数据库文件：\n{DB_PATH}"
        )

    conn = sqlite3.connect(DB_PATH)

    try:

        cursor = conn.cursor()

        # ----------------------------------------------------
        # 获取所有用户表
        # ----------------------------------------------------

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
        """)

        table_names = [
            row[0]
            for row in cursor.fetchall()
        ]

        schema = {}

        # ----------------------------------------------------
        # 逐个读取表结构
        # ----------------------------------------------------

        for table_name in table_names:

            # ================================================
            # 获取字段
            # ================================================

            cursor.execute(
                f'PRAGMA table_info("{table_name}");'
            )

            column_rows = cursor.fetchall()

            columns = []

            primary_keys = []

            for row in column_rows:

                # row 结构：
                #
                # 0 cid
                # 1 name
                # 2 type
                # 3 notnull
                # 4 default_value
                # 5 pk

                column_name = row[1]

                columns.append(column_name)

                # SQLite 中 pk > 0 表示属于主键
                if row[5] > 0:
                    primary_keys.append(
                        column_name
                    )

            # ================================================
            # 获取外键
            # ================================================

            cursor.execute(
                f'PRAGMA foreign_key_list("{table_name}");'
            )

            foreign_key_rows = cursor.fetchall()

            foreign_keys = []

            for row in foreign_key_rows:

                # SQLite foreign_key_list 常见结构：
                #
                # 0 id
                # 1 seq
                # 2 table
                # 3 from
                # 4 to
                # 5 on_update
                # 6 on_delete
                # 7 match
                # ...

                referenced_table = row[2]

                from_column = row[3]

                to_column = row[4]

                foreign_keys.append({
                    "column": from_column,
                    "references_table": referenced_table,
                    "references_column": to_column
                })

            schema[table_name] = {
                "columns": columns,
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys
            }

        return schema

    finally:

        conn.close()


# ============================================================
# 6. 找相关表
# ============================================================

def find_related_tables(
    question,
    schema_info
):

    related_tables = []

    for keyword, tables in TABLE_ALIASES.items():

        if keyword in question:

            for table in tables:

                if table in schema_info:

                    if table not in related_tables:

                        related_tables.append(table)

    return related_tables


# ============================================================
# 7. 找相关字段
# ============================================================

def find_related_fields(
    question,
    schema_info
):

    fields = []

    for keyword, mappings in FIELD_ALIASES.items():

        if keyword not in question:
            continue

        for table_name, column_name in mappings:

            if table_name not in schema_info:
                continue

            if column_name not in schema_info[
                table_name
            ]["columns"]:
                continue

            item = {
                "table": table_name,
                "column": column_name
            }

            if item not in fields:

                fields.append(item)

    return fields


# ============================================================
# 8. 找具体数据值
# ============================================================

def find_related_values(
    question,
    schema_info
):

    values = []

    for keyword, mappings in VALUE_ALIASES.items():

        if keyword not in question:
            continue

        for (
            table_name,
            column_name,
            actual_value
        ) in mappings:

            if table_name not in schema_info:
                continue

            if column_name not in schema_info[
                table_name
            ]["columns"]:
                continue

            item = {
                "table": table_name,
                "column": column_name,
                "value": actual_value
            }

            if item not in values:

                values.append(item)

    return values


# ============================================================
# 9. 根据问题补充相关表
# ============================================================

def expand_tables(
    question,
    related_tables,
    related_fields,
    related_values,
    schema_info
):

    result = list(related_tables)

    # --------------------------------------------------------
    # 字段对应的表
    # --------------------------------------------------------

    for field in related_fields:

        table_name = field["table"]

        if table_name not in result:

            result.append(table_name)

    # --------------------------------------------------------
    # 数据值对应的表
    # --------------------------------------------------------

    for value in related_values:

        table_name = value["table"]

        if table_name not in result:

            result.append(table_name)

    # --------------------------------------------------------
    # 歌手 + 专辑
    # --------------------------------------------------------

    if (
        "歌手" in question
        and "专辑" in question
    ):

        if "Artist" in schema_info:

            if "Artist" not in result:

                result.append("Artist")

        if "Album" in schema_info:

            if "Album" not in result:

                result.append("Album")

    # --------------------------------------------------------
    # 音乐类型 + 歌曲
    # --------------------------------------------------------

    if (
        (
            "音乐类型" in question
            or "流派" in question
        )
        and
        "歌曲" in question
    ):

        if "Genre" in schema_info:

            if "Genre" not in result:

                result.append("Genre")

        if "Track" in schema_info:

            if "Track" not in result:

                result.append("Track")

    return result


# ============================================================
# 10. 查找表之间的关系
# ============================================================

def find_relationships(
    related_tables,
    schema_info
):

    relationships = []

    for table_name in related_tables:

        if table_name not in schema_info:
            continue

        foreign_keys = schema_info[
            table_name
        ]["foreign_keys"]

        for fk in foreign_keys:

            referenced_table = fk[
                "references_table"
            ]

            # 只显示当前相关表之间的关系
            if referenced_table not in related_tables:
                continue

            relationship = {
                "left_table": table_name,
                "left_column": fk[
                    "column"
                ],
                "right_table": referenced_table,
                "right_column": fk[
                    "references_column"
                ]
            }

            if relationship not in relationships:

                relationships.append(
                    relationship
                )

    return relationships


# ============================================================
# 11. 判断问题意图
# ============================================================

def detect_intent(question):

    intents = []

    # -------------------------
    # 计数
    # -------------------------

    if (
        "多少" in question
        or "几个" in question
        or "多少个" in question
    ):

        intents.append("计数/统计")

    # -------------------------
    # 最大值
    # -------------------------

    if (
        "最多" in question
        or "最大" in question
        or "最高" in question
    ):

        intents.append("求最大值")

    # -------------------------
    # 最小值
    # -------------------------

    if (
        "最少" in question
        or "最小" in question
        or "最低" in question
    ):

        intents.append("求最小值")

    # -------------------------
    # 分组统计
    # -------------------------

    if (
        "每个" in question
        or "各个" in question
        or "分别" in question
    ):

        intents.append("分组统计")

    # -------------------------
    # 求和
    # -------------------------

    if (
        "总共" in question
        or "总计" in question
        or "总金额" in question
        or "总数" in question
    ):

        intents.append("求和")

    # -------------------------
    # 平均
    # -------------------------

    if "平均" in question:

        intents.append("平均值")

    return intents


# ============================================================
# 12. 主 Schema Linking
# ============================================================

def schema_link(question):

    # 读取数据库结构
    schema_info = load_database_schema()

    # --------------------------------------------------------
    # 1. 找表
    # --------------------------------------------------------

    related_tables = find_related_tables(
        question,
        schema_info
    )

    # --------------------------------------------------------
    # 2. 找字段
    # --------------------------------------------------------

    related_fields = find_related_fields(
        question,
        schema_info
    )

    # --------------------------------------------------------
    # 3. 找数据值
    # --------------------------------------------------------

    related_values = find_related_values(
        question,
        schema_info
    )

    # --------------------------------------------------------
    # 4. 根据问题补充表
    # --------------------------------------------------------

    related_tables = expand_tables(
        question,
        related_tables,
        related_fields,
        related_values,
        schema_info
    )

    # --------------------------------------------------------
    # 5. 找关系
    # --------------------------------------------------------

    relationships = find_relationships(
        related_tables,
        schema_info
    )

    # --------------------------------------------------------
    # 6. 意图识别
    # --------------------------------------------------------

    intents = detect_intent(
        question
    )

    # --------------------------------------------------------
    # 7. 整理相关表结构
    # --------------------------------------------------------

    selected_schema = {}

    for table_name in related_tables:

        if table_name in schema_info:

            selected_schema[table_name] = (
                schema_info[table_name]
            )

    return {
        "question": question,

        "related_tables": related_tables,

        "related_fields": related_fields,

        "related_values": related_values,

        "relationships": relationships,

        "intent": intents,

        "schema": selected_schema
    }


# ============================================================
# 13. 打印结果
# ============================================================

def print_result(result):

    print("=" * 70)

    print("用户问题：")

    print(result["question"])

    print()

    # ========================================================
    # 相关表
    # ========================================================

    print("相关表：")

    if result["related_tables"]:

        for table in result[
            "related_tables"
        ]:

            print(
                f"  - {table}"
            )

    else:

        print(
            "  暂未找到相关表"
        )

    print()

    # ========================================================
    # 相关字段
    # ========================================================

    print("可能相关字段：")

    if result["related_fields"]:

        for item in result[
            "related_fields"
        ]:

            print(
                f"  - "
                f"{item['table']}."
                f"{item['column']}"
            )

    else:

        print(
            "  暂未找到明确字段"
        )

    print()

    # ========================================================
    # 相关数据值
    # ========================================================

    print("可能相关数据值：")

    if result["related_values"]:

        for item in result[
            "related_values"
        ]:

            print(
                f"  - "
                f"{item['table']}."
                f"{item['column']} = "
                f"{item['value']}"
            )

    else:

        print(
            "  暂未找到明确数据值"
        )

    print()

    # ========================================================
    # 问题意图
    # ========================================================

    print("可能的问题意图：")

    if result["intent"]:

        for intent in result[
            "intent"
        ]:

            print(
                f"  - {intent}"
            )

    else:

        print(
            "  暂未判断"
        )

    print()

    # ========================================================
    # 表结构
    # ========================================================

    print("表结构：")

    if result["schema"]:

        for (
            table_name,
            table_info
        ) in result["schema"].items():

            print()

            print(
                f"[{table_name}]"
            )

            print(
                "字段："
            )

            for column in table_info[
                "columns"
            ]:

                print(
                    f"  - {column}"
                )

            print(
                "主键："
            )

            if table_info[
                "primary_keys"
            ]:

                for pk in table_info[
                    "primary_keys"
                ]:

                    print(
                        f"  - {pk}"
                    )

            else:

                print(
                    "  - 暂未找到"
                )

    else:

        print(
            "  暂未找到相关表结构"
        )

    print()

    # ========================================================
    # 表关系
    # ========================================================

    print(
        "表之间的关系："
    )

    if result["relationships"]:

        for rel in result[
            "relationships"
        ]:

            print(
                f"  - "
                f"{rel['left_table']}."
                f"{rel['left_column']} = "
                f"{rel['right_table']}."
                f"{rel['right_column']}"
            )

    else:

        print(
            "  暂未发现直接关系"
        )

    print(
        "=" * 70
    )


# ============================================================
# 14. 测试
# ============================================================

if __name__ == "__main__":

    test_questions = [

        "哪个歌手的专辑最多？",

        "美国有多少客户？",

        "每个国家有多少客户？",

        "哪种音乐类型的歌曲最多？",
    ]

    for question in test_questions:

        result = schema_link(
            question
        )

        print_result(
            result
        )