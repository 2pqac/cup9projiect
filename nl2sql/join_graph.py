"""
外键关系图 + BFS 自动补全多表 JOIN 路径

解决的问题：
  规则版 Schema Linking 只按关键词召回"实体表"，
  当指标字段在别的表（如消费额在 Invoice.Total、销量在 InvoiceLine.Quantity），
  若靠人工写"歌手+专辑""类型+歌曲"这类零散特例，换问法 / 换库就失效。

做法：
  1. 根据外键把所有表连成一张无向图；
  2. 指标词 -> 字段 -> 自动定位"指标字段所在表"；
  3. 用 BFS 求"实体锚点表 -> 指标表"的最短路径，
     自动补全路径上的中间表与 JOIN ON，不写特例。
"""

from collections import deque


# 指标词 -> 目标字段名（字段 -> 表 是自动从 schema 查的，不写死表）
METRIC_FIELDS = {
    "Total": [
        "消费", "消费额", "消费总额", "金额", "总额", "销售额", "total",
    ],
    "Quantity": [
        "销量", "销售量", "数量", "quantity",
    ],
}


def build_graph(schema):
    """
    从 schema(dict) 构建无向外键图。

    返回 adjacency：
      {table: [ {"to", "left_col", "right_col"}, ... ]}
    外键是有向的，但 JOIN 无向，因此正反两个方向都加入边，
    并记录该方向 JOIN 的左右列。
    """

    tables = schema["tables"]
    adj = {t: [] for t in tables}

    for t, info in tables.items():
        for fk in info.get("foreign_keys", []):
            ref = fk["to_table"]
            if ref not in tables:
                continue

            # t.from_col = ref.to_col
            adj[t].append({
                "to": ref,
                "left_col": fk["from_column"],
                "right_col": fk["to_column"],
            })

            # 反方向：ref.to_col = t.from_col
            adj[ref].append({
                "to": t,
                "left_col": fk["to_column"],
                "right_col": fk["from_column"],
            })

    return adj


def bfs_path(adj, src, dst):
    """最短表路径（表名列表）；不可达返回 None；相同表返回 [src]。"""

    if src == dst:
        return [src]

    prev = {src: None}
    queue = deque([src])

    while queue:
        cur = queue.popleft()
        for edge in adj.get(cur, []):
            nxt = edge["to"]
            if nxt in prev:
                continue
            prev[nxt] = cur
            if nxt == dst:
                path = [dst]
                while prev[path[-1]] is not None:
                    path.append(prev[path[-1]])
                return list(reversed(path))
            queue.append(nxt)

    return None


def _edge_between(adj, a, b):
    for edge in adj[a]:
        if edge["to"] == b:
            return edge
    return None


def connect_tables(adj, required):
    """
    连接所有 required 表：贪心选择最短 BFS 路径，自动加入中间表。

    返回 (all_tables, join_edges)：
      all_tables: 最终需要的表（含中间表，有序）
      join_edges: [{"left","right","left_col","right_col"}]
    """

    targets = []
    for t in required:
        if t in adj and t not in targets:
            targets.append(t)

    if not targets:
        return [], []

    connected = [targets[0]]
    in_set = {targets[0]}
    join_edges = []
    remaining = targets[1:]

    while remaining:
        best = None

        # 在"已连表 -> 未连目标"中选最短路径
        for dst in remaining:
            for src in connected:
                path = bfs_path(adj, src, dst)
                if path is not None and (
                    best is None or len(path) < len(best[0])
                ):
                    best = (path, dst)

        if best is None:
            break  # 剩余目标与当前子图不连通

        path, _dst = best
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            if b in in_set:
                continue
            edge = _edge_between(adj, a, b)
            join_edges.append({
                "left": a,
                "right": b,
                "left_col": edge["left_col"],
                "right_col": edge["right_col"],
            })
            in_set.add(b)
            connected.append(b)

        remaining = [t for t in remaining if t not in in_set]

    return connected, join_edges


def detect_metric_tables(question, schema):
    """
    指标词 -> 字段 -> 自动查找含该字段的表。

    返回目标表列表，例如：
      "消费总额..." -> 含 Total 的表 -> Invoice
      "...销量..."  -> 含 Quantity 的表 -> InvoiceLine
    """

    tables = schema["tables"]
    q = question.lower()
    found = []

    for field, words in METRIC_FIELDS.items():
        hit = any(
            (w in question) if not w.isascii() else (w in q)
            for w in words
        )
        if not hit:
            continue

        for t, info in tables.items():
            col_names = [c["name"] for c in info["columns"]]
            if field in col_names and t not in found:
                found.append(t)

    return found


def join_clause_text(join_edges):
    """生成 JOIN ON 文本，可放进 prompt 提示模型，也可直接使用。"""

    lines = []
    for e in join_edges:
        lines.append(
            f"JOIN {e['right']} ON {e['left']}.{e['left_col']} "
            f"= {e['right']}.{e['right_col']}"
        )
    return "\n".join(lines)
