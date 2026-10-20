"""
中级任务 1：要素精准识别与问题改写 —— 优化前 / 优化后对比

对同一批“不规范问题”（别名 / 错别字 / 口语），比较：
  基线（不归一化）：直接用原问题做表定位；
  优化（归一化）：先 normalize 再做表定位。
统计期望表命中率，输出 evaluation/results/question_rewrite_eval.json。

运行：python evaluation/question_rewrite_eval.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nl2sql.schema_linking import (
    find_related_tables,
    load_database_schema,
    normalize_question_with_changes,
)

RESULTS_DIR = ROOT / "evaluation" / "results"

# (不规范问题, [期望命中的表])
CASES = [
    ("哪个唱歌的人专集最多", ["Artist", "Album"]),
    ("哪个哥手的专集最多", ["Artist", "Album"]),
    ("帝都有多少顾客", ["Customer"]),
    ("申城有多少用户", ["Customer"]),
    ("哪个顾客的发票金额最高", ["Customer", "Invoice"]),
    ("上个礼拜的营收是多少", ["Invoice"]),
    ("哪个歌手的哥曲最多", ["Artist", "Track"]),
    ("法票总额是多少", ["Invoice"]),
    ("哪个买家消费最多", ["Customer", "Invoice"]),
    ("演唱者的转辑数量", ["Artist", "Album"]),
]


def is_hit(tables, expected):
    return all(name in tables for name in expected)


def main():
    schema = load_database_schema()
    records = []
    base_hits = opt_hits = 0

    for raw, expected in CASES:
        normalized, changes = normalize_question_with_changes(raw)

        baseline_tables = find_related_tables(raw, schema)
        optimized_tables = find_related_tables(normalized, schema)

        base_hit = is_hit(baseline_tables, expected)
        opt_hit = is_hit(optimized_tables, expected)
        base_hits += int(base_hit)
        opt_hits += int(opt_hit)

        records.append({
            "raw_question": raw,
            "normalized_question": normalized,
            "changes": changes,
            "expected_tables": expected,
            "baseline_tables": baseline_tables,
            "optimized_tables": optimized_tables,
            "baseline_hit": base_hit,
            "optimized_hit": opt_hit,
        })

    total = len(CASES)
    summary = {
        "task": "中级任务1 要素精准识别与问题改写",
        "total": total,
        "baseline_hit_rate": f"{base_hits}/{total}",
        "optimized_hit_rate": f"{opt_hits}/{total}",
        "records": records,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / "question_rewrite_eval.json"
    json.dump(summary, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("baseline", base_hits, "/", total,
          "optimized", opt_hits, "/", total)
    print("saved", path)


if __name__ == "__main__":
    main()
