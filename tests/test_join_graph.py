"""
外键关系图 + BFS 补全的离线测试（无需 API）。

重点验证评审指出的两个漏召回：
  消费总额最高的前5个客户 -> 必须补 Invoice
  单首歌曲的最高销量       -> 必须补 InvoiceLine
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nl2sql.join_graph import (
    build_graph,
    bfs_path,
    connect_tables,
    detect_metric_tables,
    join_clause_text,
)

with open(ROOT / "database" / "schema.json", encoding="utf-8") as f:
    SCHEMA = json.load(f)

ADJ = build_graph(SCHEMA)


def test_graph_nodes():
    assert len(ADJ) == 11


def test_graph_edges_undirected():
    def neighbors(t):
        return {e["to"] for e in ADJ[t]}

    assert "Invoice" in neighbors("Customer")
    assert "Customer" in neighbors("Invoice")
    assert "InvoiceLine" in neighbors("Track")
    assert "Artist" in neighbors("Album")


def test_bfs_direct():
    assert bfs_path(ADJ, "Customer", "Invoice") == ["Customer", "Invoice"]
    assert bfs_path(ADJ, "Track", "InvoiceLine") == ["Track", "InvoiceLine"]


def test_bfs_multi_hop():
    # Customer -> Invoice -> InvoiceLine -> Track
    assert bfs_path(ADJ, "Customer", "Track") == [
        "Customer", "Invoice", "InvoiceLine", "Track"
    ]


def test_bfs_same_table():
    assert bfs_path(ADJ, "Customer", "Customer") == ["Customer"]


def test_connect_customer_invoice():
    tables, edges = connect_tables(ADJ, ["Customer", "Invoice"])
    assert {"Customer", "Invoice"}.issubset(set(tables))
    assert len(edges) == 1
    assert {edges[0]["left"], edges[0]["right"]} == {"Customer", "Invoice"}


def test_connect_track_invoiceline():
    tables, edges = connect_tables(ADJ, ["Track", "InvoiceLine"])
    assert {"Track", "InvoiceLine"}.issubset(set(tables))
    assert len(edges) == 1


def test_connect_adds_intermediate_table():
    # 只给 Customer 与 InvoiceLine，中间的 Invoice 必须自动补进来
    tables, edges = connect_tables(ADJ, ["Customer", "InvoiceLine"])
    assert "Invoice" in tables
    assert len(edges) >= 2


def test_metric_detects_invoice():
    t = detect_metric_tables("消费总额最高的前5个客户是谁？", SCHEMA)
    assert t == ["Invoice"]


def test_metric_detects_invoiceline():
    t = detect_metric_tables("单首歌曲的最高销量是多少？", SCHEMA)
    assert t == ["InvoiceLine"]


def test_case_top5_customers_full_pipeline():
    q = "消费总额最高的前5个客户是谁？"
    required = ["Customer"] + detect_metric_tables(q, SCHEMA)
    tables, _ = connect_tables(ADJ, required)
    assert "Customer" in tables
    assert "Invoice" in tables


def test_case_top_sales_full_pipeline():
    q = "单首歌曲的最高销量是多少？"
    required = ["Track"] + detect_metric_tables(q, SCHEMA)
    tables, _ = connect_tables(ADJ, required)
    assert "Track" in tables
    assert "InvoiceLine" in tables


def test_join_clause_text():
    _, edges = connect_tables(ADJ, ["Customer", "Invoice"])
    txt = join_clause_text(edges)
    assert "JOIN Invoice" in txt
    assert "CustomerId" in txt
