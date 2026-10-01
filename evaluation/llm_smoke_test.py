"""
LLM 真实调用脱敏证据（smoke test）

真实调用一次大模型，记录可复核但脱敏的证据：provider 主机、model、
response_id、token 用量、提供的表、生成的 SQL、校验与执行结果、耗时、
是否真实创建了 client。不记录 API Key / Authorization。

其中“哪个国家客户最多？”不在规则字典中（fallback 为 None），
能答对即证明结果来自 LLM 而非规则。

运行：
  python evaluation/llm_smoke_test.py
结果：
  evaluation/results/llm_smoke_test.json
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.executor import execute_sql
from nl2sql.validator import validate_sql
from nl2sql.schema_validator import validate_columns
from nl2sql.join_validator import validate_join_path
from nl2sql.schema_linking import schema_link
from nl2sql.join_graph import connect_tables, detect_metric_tables
from nl2sql.llm_nl2sql import NL2SQL

RESULTS_DIR = ROOT / "evaluation" / "results"

SYSTEM = (
    "你是一个 SQLite SQL 生成专家。根据用户问题和数据库表结构，"
    "生成一条可直接执行的 SELECT 语句。要求：只输出一条 SELECT，"
    "不要解释 / markdown / 注释；表名字段名必须来自结构，禁止臆造；"
    "多表关联必须使用给出的外键；问“最…/前N”用 ORDER BY...LIMIT，"
    "问“是谁/哪个”返回名称和数值，问“是多少”只返回数值。"
)

QUESTIONS = [
    "哪个国家客户最多？",
    "美国有多少客户？",
    "消费总额最高的前3个客户是谁？",
]


def extract_sql(raw):
    match = re.search(r"select", raw, flags=re.IGNORECASE)
    if match:
        raw = raw[match.start():]
    return raw.replace("```", "").strip().rstrip(";") + ";"


def main():
    engine = NL2SQL()
    evidence = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "client_created": engine.client is not None,
        "provider_host": urlparse(engine.base_url).hostname,
        "model": engine.model,
        "note": "未记录 API Key / Authorization；.env 不入库。",
        "records": [],
    }

    if not engine.client:
        evidence["error"] = "本机未配置 LLM_API_KEY，无法生成真实调用证据"
        print(evidence["error"])
        return

    for question in QUESTIONS:
        anchors = schema_link(question)["related_tables"]
        metrics = detect_metric_tables(question, engine.schema)
        related, _ = connect_tables(engine.graph, anchors + metrics)
        schema_text = engine.build_schema_text(related)
        user = f"数据库表结构：\n{schema_text}\n\n用户问题：{question}\n"

        t0 = time.perf_counter()
        resp = engine.client.chat.completions.create(
            model=engine.model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)

        sql = extract_sql(resp.choices[0].message.content)
        usage = resp.usage
        record = {
            "question": question,
            "response_id": resp.id,
            "usage_tokens": usage.model_dump() if usage else None,
            "tables_provided": related,
            "generated_sql": sql,
            "latency_ms": latency_ms,
            "validation": {
                "safe": validate_sql(sql)["valid"],
                "columns": validate_columns(sql)["valid"],
                "join_path": validate_join_path(sql)["valid"],
            },
            "result_columns": execute_sql(sql)["columns"],
            "result_rows": execute_sql(sql)["rows"],
            "rule_fallback_sql": engine.fallback_generate(question),
            "engine": "llm",
        }
        evidence["records"].append(record)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / "llm_smoke_test.json"
    json.dump(evidence, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("saved", path)


if __name__ == "__main__":
    main()
