"""
A 同学测试文件：tests/test_nl2sql.py

两部分：
  1. 离线测试：执行器 / 安全校验 / 表字段校验，无需 API，随时可跑。
  2. 端到端测试：12 个中文问题，比对 LLM 生成 SQL 的执行结果
     与"标准答案 verify_sql"的结果是否一致（execution match）。
     未在 .env 配置 LLM_API_KEY 时自动 skip。

运行（项目根目录，激活 .venv 后）：
  pytest tests/test_nl2sql.py -v
"""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from database.executor import execute_sql
from nl2sql.validator import validate_sql
from nl2sql.schema_validator import validate_columns
from nl2sql.llm_nl2sql import nl2sql


def has_api_key():
    key = os.getenv("LLM_API_KEY", "")
    return bool(key) and "请" not in key


# ============ 一、离线测试（无需 API）============

def test_executor_single_table():
    r = execute_sql("SELECT COUNT(*) AS c FROM Customer")
    assert r["rows"][0][0] == 59


def test_executor_aggregation():
    r = execute_sql(
        "SELECT Country, COUNT(*) AS c FROM Customer GROUP BY Country "
        "ORDER BY c DESC LIMIT 1"
    )
    assert r["rows"][0] == ("USA", 13)


def test_validator_blocks_write():
    assert validate_sql("DROP TABLE Customer;")["valid"] is False
    assert validate_sql("DELETE FROM Customer;")["valid"] is False


def test_validator_allows_select():
    assert validate_sql("SELECT * FROM Customer;")["valid"] is True


def test_schema_validator_unknown_table():
    assert validate_columns("SELECT * FROM NotExist;")["valid"] is False


def test_schema_validator_unknown_column():
    assert validate_columns("SELECT FakeCol FROM Customer;")["valid"] is False


# ============ 二、12 个端到端用例 ============
# 每条 = (中文问题, 标准答案 SQL)；比对两者执行结果。

CASES = [
    ("美国有多少客户？",
     "SELECT COUNT(*) FROM Customer WHERE Country='USA'"),

    ("每个国家分别有多少客户？",
     "SELECT Country, COUNT(*) FROM Customer GROUP BY Country"),

    ("哪个歌手的专辑最多？",
     "SELECT Artist.Name, COUNT(Album.AlbumId) AS c FROM Artist "
     "JOIN Album ON Artist.ArtistId=Album.ArtistId "
     "GROUP BY Artist.ArtistId ORDER BY c DESC LIMIT 1"),

    ("哪种音乐类型的歌曲最多？",
     "SELECT Genre.Name, COUNT(*) AS c FROM Genre "
     "JOIN Track ON Genre.GenreId=Track.GenreId "
     "GROUP BY Genre.GenreId ORDER BY c DESC LIMIT 1"),

    ("所有发票的总金额是多少？",
     "SELECT SUM(Total) FROM Invoice"),

    ("发票的平均金额是多少？",
     "SELECT AVG(Total) FROM Invoice"),

    ("金额最高的一张发票是多少？",
     "SELECT MAX(Total) FROM Invoice"),

    ("消费总额最高的前5个客户是谁？",
     "SELECT c.FirstName, c.LastName, SUM(i.Total) AS s "
     "FROM Invoice AS i JOIN Customer AS c ON i.CustomerId=c.CustomerId "
     "GROUP BY c.CustomerId ORDER BY s DESC LIMIT 5"),

    ("单首歌曲的最高销量是多少？",
     "SELECT MAX(q) FROM (SELECT SUM(Quantity) AS q FROM InvoiceLine "
     "GROUP BY TrackId)"),

    ("2023年开了多少张发票？",
     "SELECT COUNT(*) FROM Invoice WHERE InvoiceDate LIKE '2023%'"),

    ("顾客总数是多少？",
     "SELECT COUNT(*) FROM Customer"),

    ("姓Smith的客户有多少？",
     "SELECT COUNT(*) FROM Customer WHERE LastName='Smith'"),
]


def normalize(rows):
    """归一化：浮点保留2位；每行内部排序(忽略列顺序)，整体再排序(忽略行顺序)。"""
    out = []
    for row in rows:
        vals = [
            round(x, 2) if isinstance(x, float) else x for x in row
        ]
        out.append(tuple(sorted(vals, key=lambda v: str(v))))
    return sorted(out, key=lambda r: str(r))


@pytest.mark.parametrize("question,verify_sql", CASES)
def test_nl2sql_end_to_end(question, verify_sql):
    if not has_api_key():
        pytest.skip("尚未配置 LLM_API_KEY（在 .env 填入后自动运行）")

    expected = execute_sql(verify_sql)
    result = nl2sql(question)

    assert result["success"], result.get("message")
    assert normalize(result["rows"]) == normalize(expected["rows"])
