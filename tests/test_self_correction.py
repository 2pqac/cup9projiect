"""
自我修正机制的故障注入测试（离线、确定性，无需真实 API）

用 monkeypatch 让 llm_generate 第一次返回会被 JOIN 校验拦截的 SQL
（笛卡尔积 / 错误关联键），第二次返回正确 SQL，断言：
  - 最终 success；
  - attempts == 2（确实经历了一次回喂修正）；
  - trace 中存在“JOIN 校验未通过，回喂修正”。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nl2sql.llm_nl2sql import NL2SQL

GOOD = (
    "SELECT c.FirstName, i.Total FROM Customer c "
    "JOIN Invoice i ON c.CustomerId = i.CustomerId;"
)


def _make_engine(monkeypatch, bad_sql):
    engine = NL2SQL()
    # 强制进入 LLM 主干；llm_generate 被 mock，不会真正使用 client
    engine.client = object()

    state = {"n": 0}

    def fake_generate(question, schema_text, error_feedback=None):
        state["n"] += 1
        return bad_sql if state["n"] == 1 else GOOD

    monkeypatch.setattr(engine, "llm_generate", fake_generate)
    return engine


def test_correct_cartesian_product(monkeypatch):
    engine = _make_engine(monkeypatch, "SELECT * FROM Customer, Invoice;")
    result = engine.run("列出客户和发票")

    assert result["success"]
    assert result["attempts"] == 2
    assert any("JOIN 校验未通过" in step["step"]
               for step in result["trace"])


def test_correct_wrong_join_key(monkeypatch):
    bad = ("SELECT * FROM Customer JOIN Invoice "
           "ON Customer.City = Invoice.InvoiceDate;")
    engine = _make_engine(monkeypatch, bad)
    result = engine.run("列出客户和发票")

    assert result["success"]
    assert result["attempts"] == 2
    assert any("JOIN 校验未通过" in step["step"]
               for step in result["trace"])
