"""
泛化证明（离线，无需 API）：在真实生成的合成业务库上验证 BFS。

合成库表名 / 字段名与 Chinook 完全不同、外键拓扑为电商订单，
BFS 仍能求出正确最短路径与 JOIN 补全，证明 BFS 不依赖模型记住 Chinook
（BFS 本身是确定性图算法，全程不调用大模型）。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nl2sql.join_graph import build_graph, bfs_path, connect_tables

SCHEMA = json.load(open(
    ROOT / "evaluation" / "synth" / "schema_synth.json", encoding="utf-8"))
G = build_graph(SCHEMA)


def test_synth_has_six_nodes():
    assert len(G) == 6


def test_synth_undirected_edges():
    def neighbors(t):
        return {e["to"] for e in G[t]}

    assert "t_b" in neighbors("t_a")
    assert "t_a" in neighbors("t_b")
    assert "t_c" in neighbors("t_d")
    assert "t_e" in neighbors("t_d")
    assert "t_f" in neighbors("t_a")


def test_member_to_order_direct():
    assert bfs_path(G, "t_a", "t_b") == ["t_a", "t_b"]


def test_product_to_line_direct():
    assert bfs_path(G, "t_d", "t_c") == ["t_d", "t_c"]


def test_member_to_product_multi_hop():
    # 会员 -> 订单 -> 明细 -> 商品
    assert bfs_path(G, "t_a", "t_d") == ["t_a", "t_b", "t_c", "t_d"]


def test_connect_member_with_amount():
    tables, edges = connect_tables(G, ["t_a", "t_b"])
    assert {"t_a", "t_b"}.issubset(set(tables))
    assert len(edges) == 1


def test_connect_product_with_qty():
    tables, edges = connect_tables(G, ["t_d", "t_c"])
    assert {"t_d", "t_c"}.issubset(set(tables))


def test_connect_member_product_adds_intermediate():
    tables, edges = connect_tables(G, ["t_a", "t_d"])
    assert "t_b" in tables
    assert "t_c" in tables
    assert len(edges) == 3
