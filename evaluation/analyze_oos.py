"""
离线分析：模型生成的 SQL 是否引用了"系统未提供的表"（超纲 / 脑补表）。

读取 evaluation/results/latest.json，无需再次调用大模型。
用于佐证：基线靠模型先验脑补缺失表（不可控），
优化方案由外键图确定性提供表（不超纲、更可控、更安全）。
"""

import json
import sys
from pathlib import Path

import sqlglot

ROOT = Path(__file__).resolve().parent.parent
LATEST = ROOT / "evaluation" / "results" / "latest.json"


def tables_in_sql(sql):
    try:
        parsed = sqlglot.parse_one(sql)
        return {t.name for t in parsed.find_all(sqlglot.exp.Table)}
    except Exception:
        return set()


def main():
    if not LATEST.exists():
        print("未找到评估结果，请先运行：python evaluation/nl2sql_eval.py")
        sys.exit(1)

    data = json.load(open(LATEST, encoding="utf-8"))

    for label in ["baseline", "optimized"]:
        records = data[label]["records"]
        out_of_scope = []

        for r in records:
            used = tables_in_sql(r["actual_sql"])
            extra = used - set(r["tables"])
            if extra:
                out_of_scope.append((r["question"], sorted(extra)))

        print(f"\n===== {label} =====")
        print(f"超纲引用（引用未提供表）的问题数：{len(out_of_scope)} / {len(records)}")
        for q, extra in out_of_scope:
            print(f"   {q} -> 脑补表 {extra}")


if __name__ == "__main__":
    main()
