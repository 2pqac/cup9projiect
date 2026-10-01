"""
确定性结果解释模块（不调用大模型，可离线测试，避免二次幻觉）

- build_query_logic：解析 SQL，生成“查询解释”（表 / JOIN / 聚合 / WHERE /
  GROUP BY / ORDER BY / LIMIT）；
- build_answer：根据问题与结果，用模板生成一句中文“答案”。
"""

import re

import sqlglot
from sqlglot import exp

# Chinook 表的中文含义，让解释更易读
TABLE_CN = {
    "Customer": "客户", "Invoice": "发票", "InvoiceLine": "发票明细",
    "Track": "歌曲", "Album": "专辑", "Artist": "歌手", "Genre": "音乐类型",
    "MediaType": "媒体类型", "Playlist": "播放列表",
    "PlaylistTrack": "播放列表关联", "Employee": "员工",
}


def _direct_tables(tree):
    tables = []
    for select in tree.find_all(exp.Select):
        frm = select.args.get("from_")
        if frm and isinstance(frm.this, exp.Table) and frm.this.name not in tables:
            tables.append(frm.this.name)
        for join in select.args.get("joins", []) or []:
            if isinstance(join.this, exp.Table) and join.this.name not in tables:
                tables.append(join.this.name)
    return tables


def build_query_logic(sql):
    tree = sqlglot.parse_one(sql, read="sqlite")
    tables = _direct_tables(tree)

    joins = []
    for eq in tree.find_all(exp.EQ):
        left, right = eq.left, eq.right
        if isinstance(left, exp.Column) and isinstance(right, exp.Column):
            if left.table and right.table:
                joins.append(f"{left.table}.{left.name} = {right.table}.{right.name}")

    aggs = sorted({func.sql() for func in tree.find_all(exp.AggFunc)})

    group_by = []
    group = tree.find(exp.Group)
    if group:
        group_by = [c.sql() for c in group.expressions]

    order_by = []
    order = tree.find(exp.Order)
    if order:
        order_by = [o.sql() for o in order.expressions]

    limit = None
    limit_node = tree.find(exp.Limit)
    if limit_node:
        limit = limit_node.expression.sql()

    where_sql = None
    where = tree.find(exp.Where)
    if where:
        where_sql = where.this.sql()

    steps = []
    if tables:
        desc = "、".join(f"{t}（{TABLE_CN.get(t, t)}）" for t in tables)
        steps.append(f"从 {desc} 中查询")
    if where_sql:
        steps.append(f"按条件 {where_sql} 过滤")
    if joins:
        steps.append("通过外键 " + "；".join(joins) + " 关联")
    if group_by:
        steps.append("按 " + "、".join(group_by) + " 分组")
    if aggs:
        steps.append("使用聚合 " + "、".join(aggs))
    if order_by:
        steps.append("按 " + "、".join(order_by) + " 排序")
    if limit:
        steps.append(f"限制返回 {limit} 条")

    return {
        "tables": tables,
        "joins": joins,
        "aggregations": aggs,
        "group_by": group_by,
        "order_by": order_by,
        "limit": limit,
        "where": where_sql,
        "summary": "；".join(steps) + "。",
    }


def build_answer(question, columns, rows):
    """根据问题与结果，确定性地生成一句中文答案。"""
    q = (question or "").strip().rstrip("？?")

    if not rows:
        return "未查询到符合条件的结果。"

    # 单标量结果：尽量把“X有多少Y”改写为“X共有 N Y”
    if len(rows) == 1 and len(rows[0]) == 1:
        value = rows[0][0]
        match = re.search(r"(.+?)有多少(.+)", q)
        if match:
            return f"{match.group(1)}共有 {value} {match.group(2)}。"
        return f"{q}：{value}。"

    # 一行或多行：第一列视为名称，其余列作为统计值
    parts = []
    for row in rows[:10]:
        name = row[0]
        stats = "，".join(
            f"{columns[i]}：{row[i]}" for i in range(1, len(row))
        )
        parts.append(f"{name}（{stats}）" if stats else str(name))
    more = "……" if len(rows) > 10 else ""
    return "结果：" + "；".join(parts) + more + "。"
