"""
NL2SQL 评估脚本：基线 vs 优化

基线 baseline：只用规则召回的实体锚点表，不做外键路径补全
优化 optimized：外键关系图 + BFS 自动补全 JOIN 路径（含中间表）

对每个问题记录：
  实际 SQL / 是否成功 / 执行结果是否匹配 / Schema Linking 是否命中 /
  LLM 尝试次数 / 是否首次成功 / 是否靠自我修正成功 / 耗时

汇总 5 项指标：
  执行准确率、Schema Linking 命中率、首次成功率、
  自我修正成功率、平均时延

运行（项目根目录，激活 .venv）：
  python evaluation/nl2sql_eval.py
结果保存到 evaluation/results/。
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from database.executor import execute_sql
from nl2sql.llm_nl2sql import NL2SQL


# (问题, 标准答案 SQL, 该问题必须用到的表)
EVAL_CASES = [
    {"q": "美国有多少客户？",
     "sql": "SELECT COUNT(*) FROM Customer WHERE Country='USA'",
     "need": ["Customer"]},

    {"q": "每个国家分别有多少客户？",
     "sql": "SELECT Country, COUNT(*) FROM Customer GROUP BY Country",
     "need": ["Customer"]},

    {"q": "所有发票的总金额是多少？",
     "sql": "SELECT SUM(Total) FROM Invoice",
     "need": ["Invoice"]},

    {"q": "发票的平均金额是多少？",
     "sql": "SELECT AVG(Total) FROM Invoice",
     "need": ["Invoice"]},

    {"q": "金额最高的一张发票是多少？",
     "sql": "SELECT MAX(Total) FROM Invoice",
     "need": ["Invoice"]},

    {"q": "2023年开了多少张发票？",
     "sql": "SELECT COUNT(*) FROM Invoice WHERE InvoiceDate LIKE '2023%'",
     "need": ["Invoice"]},

    {"q": "姓Smith的客户有多少？",
     "sql": "SELECT COUNT(*) FROM Customer WHERE LastName='Smith'",
     "need": ["Customer"]},

    {"q": "哪个歌手的专辑最多？",
     "sql": ("SELECT Artist.Name, COUNT(Album.AlbumId) AS c FROM Artist "
             "JOIN Album ON Artist.ArtistId=Album.ArtistId "
             "GROUP BY Artist.ArtistId ORDER BY c DESC LIMIT 1"),
     "need": ["Artist", "Album"]},

    {"q": "哪种音乐类型的歌曲最多？",
     "sql": ("SELECT Genre.Name, COUNT(*) AS c FROM Genre "
             "JOIN Track ON Genre.GenreId=Track.GenreId "
             "GROUP BY Genre.GenreId ORDER BY c DESC LIMIT 1"),
     "need": ["Genre", "Track"]},

    {"q": "消费总额最高的前5个客户是谁？",
     "sql": ("SELECT c.FirstName, c.LastName, SUM(i.Total) AS s "
             "FROM Invoice AS i JOIN Customer AS c ON i.CustomerId=c.CustomerId "
             "GROUP BY c.CustomerId ORDER BY s DESC LIMIT 5"),
     "need": ["Customer", "Invoice"]},

    {"q": "单首歌曲的最高销量是多少？",
     "sql": ("SELECT MAX(q) FROM (SELECT SUM(Quantity) AS q FROM InvoiceLine "
             "GROUP BY TrackId)"),
     "need": ["Track", "InvoiceLine"]},
]


def normalize(rows):
    out = []
    for row in rows:
        vals = [round(x, 2) if isinstance(x, float) else x for x in row]
        out.append(tuple(sorted(vals, key=lambda v: str(v))))
    return sorted(out, key=lambda r: str(r))


def has_api_key():
    key = os.getenv("LLM_API_KEY", "")
    return bool(key) and "请" not in key


def run_one(service, case, optimized):
    t0 = time.time()
    result = service.run(case["q"], use_join_graph=optimized)
    latency = time.time() - t0

    expected = execute_sql(case["sql"])
    match = (
        result.get("success")
        and normalize(result.get("rows", [])) == normalize(expected["rows"])
    )

    tables = result.get("tables", [])
    schema_hit = all(t in tables for t in case["need"])
    attempts = result.get("attempts", 0)

    return {
        "question": case["q"],
        "success": bool(result.get("success")),
        "match": bool(match),
        "schema_hit": bool(schema_hit),
        "attempts": attempts,
        "first_pass": bool(result.get("success") and attempts == 1),
        "self_correct_success": bool(result.get("success") and attempts > 1),
        "latency": round(latency, 2),
        "actual_sql": result.get("sql", ""),
        "tables": tables,
        "message": result.get("message", ""),
    }


def summarize(records):
    n = len(records)
    return {
        "样本数": n,
        "执行准确率(%)": round(100 * sum(x["match"] for x in records) / n, 1),
        "Schema命中率(%)": round(
            100 * sum(x["schema_hit"] for x in records) / n, 1
        ),
        "首次成功率(%)": round(
            100 * sum(x["first_pass"] for x in records) / n, 1
        ),
        "自我修正成功率(%)": round(
            100 * sum(x["self_correct_success"] for x in records) / n, 1
        ),
        "平均时延(s)": round(
            sum(x["latency"] for x in records) / n, 2
        ),
    }


def main():
    if not has_api_key():
        print("未配置 LLM_API_KEY，无法运行在线评估。")
        print("离线的外键图 / BFS 测试请运行：pytest tests/test_join_graph.py")
        return

    service = NL2SQL()
    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline": None,
        "optimized": None,
    }

    for label, optimized in [("baseline", False), ("optimized", True)]:
        records = []
        print(f"\n===== {label} =====")

        for case in EVAL_CASES:
            rec = run_one(service, case, optimized)
            records.append(rec)
            mark = "OK" if rec["match"] else " X"
            print(
                f'  [{mark}] schema_hit={str(rec["schema_hit"]):5} '
                f'attempts={rec["attempts"]} {rec["latency"]:5}s  {case["q"]}'
            )

        summary = summarize(records)
        output[label] = {"summary": summary, "records": records}
        print("  ---- 汇总 ----")
        for k, v in summary.items():
            print(f"    {k}: {v}")

    results_dir = ROOT / "evaluation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = results_dir / f"nl2sql_eval_{stamp}.json"
    with open(target, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    with open(results_dir / "latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n已保存评估结果：", target)


if __name__ == "__main__":
    main()
