"""中级任务 1：要素识别与问题改写（同义词 / 别名 / 错别字）离线测试。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nl2sql.schema_linking import (
    schema_link,
    normalize_question_with_changes,
)


def test_synonym_singer():
    r = schema_link("哪个唱歌的人专辑最多")
    assert "Artist" in r["related_tables"]
    assert "Album" in r["related_tables"]


def test_typo_singer():
    r = schema_link("哪个哥手专辑最多")
    assert "Artist" in r["related_tables"]


def test_customer_aliases():
    for word in ["顾客", "用户", "买家"]:
        r = schema_link("有多少" + word)
        assert "Customer" in r["related_tables"], word


def test_place_alias_and_changes():
    r = schema_link("帝都有多少客户")
    assert "Customer" in r["related_tables"]
    assert r["original_question"] == "帝都有多少客户"
    assert any("帝都" in c for c in r["question_changes"])


def test_invoice_typo_and_synonyms():
    assert "Invoice" in schema_link("法票总额")["related_tables"]
    assert "Invoice" in schema_link("收入是多少")["related_tables"]
    assert "Invoice" in schema_link("消费最多")["related_tables"]


def test_album_typo():
    assert "Album" in schema_link("歌手的转辑")["related_tables"]


def test_normalize_changes_detail():
    normalized, changes = normalize_question_with_changes("哪个哥手的专集最多")
    assert normalized == "哪个歌手的专辑最多"
    assert len(changes) == 2
