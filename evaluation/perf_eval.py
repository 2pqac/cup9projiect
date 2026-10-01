"""
多规模性能测试（性能证据）

方法（隔离各阶段、可复现）：
  1. 用合成库生成器构造 3 种数据规模（scale = 1 / 10 / 40）；
  2. 每个问题的 SQL 只由 LLM 生成一次并固定，避免随机性，
     在不同规模库上用同一条 SQL 测“执行时延”；
  3. 分阶段计时：Schema Linking + BFS、LLM 生成、SQL 执行；
  4. 记录库文件大小（空间占用）。

运行：
  python evaluation/perf_eval.py
结果：
  evaluation/results/perf_results.json
"""

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation" / "synth"))

from database.executor import execute_sql
from nl2sql.join_graph import build_graph, connect_tables
from evaluation.synth.gen_synth_db import build, write_db, extract_schema
import synth_nl2sql as S

SCALES = [1, 10, 40]
QUESTIONS = [
    ("轻查询-会员计数", "一共有多少会员？"),
    ("JOIN聚合-订单金额", "订单金额最高的前3个会员是谁？"),
    ("重查询-明细销量", "销量最高的商品是哪个？"),
]
RESULTS_DIR = ROOT / "evaluation" / "results"


def median_time(fn, repeat):
    vals = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        vals.append(time.perf_counter() - t0)
    return statistics.median(vals)


def main():
    service = S.SynthNL2SQL()
    if not service.client:
        print("未配置 LLM_API_KEY，无法运行性能测试")
        return

    # 1) 每个问题固定 SQL，并测 LLM 生成时延（与数据规模无关）
    fixed = []
    for label, q in QUESTIONS:
        anchors = S.anchor_tables(q)
        metrics = S.metric_tables(q)
        related, _ = connect_tables(S.GRAPH, anchors + metrics)
        text = S.schema_text(related)
        sql = service.llm_generate(q, text)
        llm_ms = median_time(lambda: service.llm_generate(q, text), 3) * 1000
        schema_ms = median_time(
            lambda: connect_tables(S.GRAPH, anchors + metrics), 30) * 1000
        fixed.append({"label": label, "q": q, "sql": sql,
                      "llm_ms": round(llm_ms, 1),
                      "schema_bfs_ms": round(schema_ms, 3)})

    scales_out = []
    for scale in SCALES:
        db = ROOT / "evaluation" / "synth" / f"perf_s{scale}.db"
        write_db(db, build(scale))
        size_kb = round(db.stat().st_size / 1024, 1)
        schema = extract_schema(db, f"perf{scale}")
        import sqlite3
        count_conn = sqlite3.connect(db)
        conn_rows = {
            t: count_conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ["t_a", "t_b", "t_c", "t_d"]
        }
        count_conn.close()

        q_out = []
        for item in fixed:
            exec_ms = median_time(
                lambda sql=item["sql"]: execute_sql(sql, db_path=db), 5) * 1000
            q_out.append({"label": item["label"],
                          "exec_ms": round(exec_ms, 2)})

        scales_out.append({"scale": scale, "size_kb": size_kb,
                           "rows": conn_rows, "queries": q_out})
        db.unlink()  # 删除大库，不入库

    out = {"fixed_stage": fixed, "by_scale": scales_out}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / "perf_results.json"
    json.dump(out, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("saved", path)


if __name__ == "__main__":
    main()
