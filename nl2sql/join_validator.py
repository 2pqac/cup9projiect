"""
JOIN 语义校验（validate_join_path）

统一判定思想：
  对每个 SELECT，把它直接涉及的表作为节点，把 ON / WHERE 中
  “经 schema.json 外键验证为真”的等值条件作为边；
  多表必须通过这些外键边构成连通图。

由此同时拦截：
  - 笛卡尔积：SELECT * FROM Customer, Invoice（表之间没有外键边，不连通）
  - 错误关联键：... JOIN Invoice ON Customer.City = Invoice.InvoiceDate
    （字段都存在，但不是外键）

单表查询、仅含子查询的外层 SELECT 不做此校验。
"""

from sqlglot import exp

from nl2sql.schema_validator import validate_tables


def build_fk_pairs(schema):
    """合法的无向外键边集合：frozenset( (table,col), (table,col) )。"""

    pairs = set()
    for t, info in schema["tables"].items():
        for fk in info.get("foreign_keys", []):
            ref = fk["to_table"]
            a = (t.lower(), fk["from_column"].lower())
            b = (ref.lower(), fk["to_column"].lower())
            pairs.add(frozenset((a, b)))
    return pairs


def _direct_tables(select):
    """该 SELECT 直接包含的表（FROM / 逗号 / JOIN），不钻入子查询。"""

    out = []
    frm = select.args.get("from_")

    if frm:
        if isinstance(frm.this, exp.Table):
            out.append(frm.this)
        for extra in frm.expressions:
            if isinstance(extra, exp.Table):
                out.append(extra)

    for join in select.args.get("joins", []) or []:
        if isinstance(join.this, exp.Table):
            out.append(join.this)

    return out


def _col_ref(node, alias_to_table):
    """把 Column 解析为 (真实表, 字段)；无法确定归属则返回 None。"""

    if not isinstance(node, exp.Column) or not node.table:
        return None

    real = alias_to_table.get(node.table.lower())
    if not real:
        return None

    return real, node.name.lower()


def _fk_hint(table_names, fk_pairs):
    """给出涉及这些表的合法外键连接提示，用于回喂模型修正。"""

    names = set(table_names)
    hints = []

    for pair in fk_pairs:
        a, b = tuple(pair)
        if a[0] in names or b[0] in names:
            hints.append(f"JOIN {b[0]} ON {a[0]}.{a[1]}={b[0]}.{b[1]}")

    return "；".join(sorted(set(hints)))


def validate_join_path(sql, schema=None):
    table_result = validate_tables(sql, schema=schema)
    if not table_result["valid"]:
        return table_result

    tree = table_result["tree"]
    alias_to_table = table_result["alias_to_table"]
    schema = table_result["schema"]
    fk_pairs = build_fk_pairs(schema)

    for select in tree.find_all(exp.Select):
        real_tables = [
            alias_to_table.get(t.name.lower())
            for t in _direct_tables(select)
        ]
        real_tables = [t for t in real_tables if t]
        nodes = set(real_tables)

        if len(nodes) <= 1:
            continue  # 单表 / 仅子查询，无多表关联问题

        parent = {n: n for n in nodes}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            parent[find(a)] = find(b)

        bad_key = None

        def scan(cond):
            nonlocal bad_key
            if not cond:
                return
            for eq in cond.find_all(exp.EQ):
                left = _col_ref(eq.left, alias_to_table)
                right = _col_ref(eq.right, alias_to_table)
                if not left or not right:
                    continue
                if frozenset((left, right)) in fk_pairs:
                    union(left[0], right[0])
                else:
                    bad_key = (left, right)

        # JOIN ... ON
        for join in select.args.get("joins", []) or []:
            scan(join.args.get("on"))

        # 老式隐式连接会把连接条件写在 WHERE
        where = select.args.get("where")
        if where:
            scan(where.this)

        if bad_key:
            left, right = bad_key
            return {
                "valid": False,
                "message": (
                    f"JOIN 关联键错误：{left[0]}.{left[1]} = "
                    f"{right[0]}.{right[1]} 不是 schema 中的外键。"
                    f"正确外键连接：{_fk_hint(nodes, fk_pairs)}"
                ),
            }

        if len({find(n) for n in nodes}) > 1:
            return {
                "valid": False,
                "message": (
                    "多表查询缺少有效 JOIN（疑似笛卡尔积，表未通过外键连接）。"
                    f"应使用外键连接：{_fk_hint(nodes, fk_pairs)}"
                ),
            }

    return {"valid": True, "message": "JOIN 路径检查通过"}
