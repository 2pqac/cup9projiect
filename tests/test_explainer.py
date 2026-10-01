"""explainer 确定性答案 / 查询解释离线测试（无需 API）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nl2sql.explainer import build_query_logic, build_answer


def test_logic_single_count():
    logic = build_query_logic("SELECT COUNT(*) FROM Customer")
    assert logic["tables"] == ["Customer"]
    assert any("COUNT" in a for a in logic["aggregations"])
    assert "客户" in logic["summary"]


def test_logic_where_filter():
    logic = build_query_logic(
        "SELECT COUNT(*) FROM Customer WHERE Country='USA'")
    assert logic["where"] is not None
    assert "过滤" in logic["summary"]


def test_logic_join():
    logic = build_query_logic(
        "SELECT * FROM Customer JOIN Invoice "
        "ON Customer.CustomerId=Invoice.CustomerId")
    assert {"Customer", "Invoice"}.issubset(set(logic["tables"]))
    assert len(logic["joins"]) == 1
    assert "关联" in logic["summary"]


def test_logic_group_order_limit():
    sql = ("SELECT Country, COUNT(*) FROM Customer GROUP BY Country "
           "ORDER BY COUNT(*) DESC LIMIT 3")
    logic = build_query_logic(sql)
    assert len(logic["group_by"]) == 1
    assert len(logic["order_by"]) == 1
    assert logic["limit"] == "3"


def test_answer_count_phrase():
    answer = build_answer("美国有多少客户？", ["COUNT(*)"], [(13,)])
    assert "13" in answer and "美国" in answer and "客户" in answer


def test_answer_generic_single():
    answer = build_answer("客户总数？", ["c"], [(59,)])
    assert "59" in answer


def test_answer_top1_row():
    answer = build_answer(
        "哪个国家客户最多？", ["Country", "CustomerCount"], [("USA", 13)])
    assert "USA" in answer and "13" in answer


def test_answer_multiple_rows():
    answer = build_answer(
        "前3", ["name", "n"], [("a", 1), ("b", 2), ("c", 3)])
    assert "a" in answer and "c" in answer


def test_answer_empty():
    assert "未查询到" in build_answer("q", ["a"], [])
