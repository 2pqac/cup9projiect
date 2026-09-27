from typing import Dict, Any, Optional


# ============================================================
# NL2SQL Generator
#
# 功能：
#   1. 接收自然语言问题
#   2. 接收 Schema Linking 结果
#   3. 根据问题意图生成 SQL
#
# 当前版本：
#   先使用规则生成 SQL
#
# 后续版本：
#   可以接入 LLM，让模型生成更加复杂的 SQL
# ============================================================


# ============================================================
# 1. 清理 SQL
# ============================================================

def clean_sql(sql: str) -> str:
    """
    清理生成出来的 SQL。
    """

    sql = sql.strip()

    # 去掉 Markdown SQL 代码块
    if sql.startswith("```sql"):

        sql = sql[6:]

    elif sql.startswith("```"):

        sql = sql[3:]

    if sql.endswith("```"):

        sql = sql[:-3]

    return sql.strip()


# ============================================================
# 2. 获取相关表
# ============================================================

def get_related_tables(
    linking_result: Dict[str, Any]
):
    """
    从 Schema Linking 结果中获取相关表。
    """

    return linking_result.get(
        "related_tables",
        []
    )


# ============================================================
# 3. 获取相关字段
# ============================================================

def get_related_fields(
    linking_result: Dict[str, Any]
):
    """
    从 Schema Linking 结果中获取相关字段。
    """

    return linking_result.get(
        "related_fields",
        []
    )


# ============================================================
# 4. 获取相关数据值
# ============================================================

def get_related_values(
    linking_result: Dict[str, Any]
):
    """
    从 Schema Linking 结果中获取具体数据值。
    """

    return linking_result.get(
        "related_values",
        []
    )


# ============================================================
# 5. 获取问题意图
# ============================================================

def get_intents(
    linking_result: Dict[str, Any]
):
    """
    获取：

    计数
    分组
    最大值
    最小值
    求和
    平均值
    """

    return linking_result.get(
        "intent",
        []
    )


# ============================================================
# 6. 创建 SQL
# ============================================================

def generate_sql(
    question: str,
    linking_result: Dict[str, Any]
) -> str:
    """
    根据自然语言问题和 Schema Linking 结果生成 SQL。

    当前支持：

    1. 哪个歌手的专辑最多？
    2. 美国有多少客户？
    3. 每个国家有多少客户？
    4. 哪种音乐类型的歌曲最多？
    """

    question = question.strip()

    tables = get_related_tables(
        linking_result
    )

    fields = get_related_fields(
        linking_result
    )

    values = get_related_values(
        linking_result
    )

    intents = get_intents(
        linking_result
    )


    # ========================================================
    # 情况 1：
    #
    # 哪个歌手的专辑最多？
    # ========================================================

    if (
        "Artist" in tables
        and "Album" in tables
        and "最多" in question
    ):

        sql = """
SELECT
    Artist.Name AS ArtistName,
    COUNT(Album.AlbumId) AS AlbumCount
FROM Artist
JOIN Album
    ON Artist.ArtistId = Album.ArtistId
GROUP BY Artist.ArtistId, Artist.Name
ORDER BY AlbumCount DESC
LIMIT 1;
"""

        return clean_sql(sql)


    # ========================================================
    # 情况 2：
    #
    # 美国有多少客户？
    # ========================================================

    if (
        "Customer" in tables
        and "多少" in question
        and values
    ):

        for value in values:

            if (
                value["table"] == "Customer"
                and value["column"] == "Country"
            ):

                country = value["value"]

                sql = f"""
SELECT
    COUNT(CustomerId) AS CustomerCount
FROM Customer
WHERE Country = '{country}';
"""

                return clean_sql(sql)


    # ========================================================
    # 情况 3：
    #
    # 每个国家有多少客户？
    # ========================================================

    if (
        "Customer" in tables
        and "国家" in question
        and (
            "每个" in question
            or "各个" in question
            or "分别" in question
        )
    ):

        sql = """
SELECT
    Country,
    COUNT(CustomerId) AS CustomerCount
FROM Customer
GROUP BY Country
ORDER BY CustomerCount DESC;
"""

        return clean_sql(sql)


    # ========================================================
    # 情况 4：
    #
    # 哪种音乐类型的歌曲最多？
    # ========================================================

    if (
        "Genre" in tables
        and "Track" in tables
        and "最多" in question
    ):

        sql = """
SELECT
    Genre.Name AS GenreName,
    COUNT(Track.TrackId) AS TrackCount
FROM Genre
JOIN Track
    ON Genre.GenreId = Track.GenreId
GROUP BY Genre.GenreId, Genre.Name
ORDER BY TrackCount DESC
LIMIT 1;
"""

        return clean_sql(sql)


    # ========================================================
    # 当前没有匹配
    # ========================================================

    raise ValueError(
        "当前规则生成器还不会处理这个问题：\n"
        f"{question}\n\n"
        "下一阶段将接入 LLM 处理复杂问题。"
    )


# ============================================================
# 7. 生成 SQL + 解释
# ============================================================

def generate_sql_with_explanation(
    question: str,
    linking_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    同时返回：

    SQL
    用户问题
    相关表
    相关字段
    相关数据值
    问题意图
    """

    sql = generate_sql(
        question,
        linking_result
    )

    return {
        "question": question,

        "sql": sql,

        "related_tables": get_related_tables(
            linking_result
        ),

        "related_fields": get_related_fields(
            linking_result
        ),

        "related_values": get_related_values(
            linking_result
        ),

        "intent": get_intents(
            linking_result
        )
    }


# ============================================================
# 8. 测试
# ============================================================

if __name__ == "__main__":

    # 为了避免这里重复实现 Schema Linking，
    # 直接调用你已经写好的 schema_linking.py。

    from schema_linking import schema_link


    test_questions = [

        "哪个歌手的专辑最多？",

        "美国有多少客户？",

        "每个国家有多少客户？",

        "哪种音乐类型的歌曲最多？"
    ]


    for question in test_questions:

        print("=" * 70)

        print("用户问题：")
        print(question)

        print()

        # ----------------------------------------------------
        # 第一步：Schema Linking
        # ----------------------------------------------------

        linking_result = schema_link(
            question
        )

        print("Schema Linking：")

        print(
            "相关表：",
            linking_result[
                "related_tables"
            ]
        )

        print(
            "相关字段：",
            linking_result[
                "related_fields"
            ]
        )

        print(
            "相关数据值：",
            linking_result[
                "related_values"
            ]
        )

        print(
            "问题意图：",
            linking_result[
                "intent"
            ]
        )

        print()

        # ----------------------------------------------------
        # 第二步：生成 SQL
        # ----------------------------------------------------

        try:

            result = generate_sql_with_explanation(
                question,
                linking_result
            )

            print("生成的 SQL：")

            print(result["sql"])

        except Exception as e:

            print("SQL 生成失败：")

            print(e)

        print("=" * 70)