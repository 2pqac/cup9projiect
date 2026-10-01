"""
合成业务库端到端 NL2SQL（泛化实验，证明系统不依赖模型记住 Chinook）

与 nl2sql/llm_nl2sql.py 的区别：
  - 数据库是表名 / 字段名完全陌生的合成电商库（t_a..t_f / f_xxx）；
  - 实体锚点与指标通过中文别名层 aliases.json 识别，而非 Chinook 关键词；
  - 校验 / 执行 / 外键图 BFS 复用同一套核心函数（注入合成 schema / db）。

运行：
  python evaluation/synth/synth_nl2sql.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

SYNTH_DIR = Path(__file__).resolve().parent
ROOT = SYNTH_DIR.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from database.executor import execute_sql
from nl2sql.validator import validate_sql
from nl2sql.schema_validator import validate_columns
from nl2sql.join_validator import validate_join_path
from nl2sql.join_graph import build_graph, connect_tables

DB_PATH = SYNTH_DIR / "synth.db"
SCHEMA = json.load(open(SYNTH_DIR / "schema_synth.json", encoding="utf-8"))
ALIASES = json.load(open(SYNTH_DIR / "aliases.json", encoding="utf-8"))
GRAPH = build_graph(SCHEMA)


def anchor_tables(question):
    out = []
    for word, tables in ALIASES["table_alias"].items():
        if word in question:
            for t in tables:
                if t not in out:
                    out.append(t)
    return out


def metric_tables(question):
    out = []
    for field, words in ALIASES["metric_field"].items():
        if any(w in question for w in words):
            t = ALIASES["table_of_metric"].get(field)
            if t and t not in out:
                out.append(t)
    return out


def schema_text(names):
    blocks = []
    for t in names:
        info = SCHEMA["tables"][t]
        cols = [
            f'  {c["name"]} {c["type"] or "TEXT"}'
            + (" PRIMARY KEY" if c["primary_key"] else "")
            for c in info["columns"]
        ]
        for fk in info.get("foreign_keys", []):
            cols.append(
                f'  FOREIGN KEY ({fk["from_column"]}) '
                f'REFERENCES {fk["to_table"]}({fk["to_column"]})'
            )
        blocks.append(f"CREATE TABLE {t} (\n" + ",\n".join(cols) + "\n);")
    return "\n\n".join(blocks)


class SynthNL2SQL:
    def __init__(self):
        key = os.getenv("LLM_API_KEY", "")
        self.client = None
        if key and "请" not in key:
            self.client = OpenAI(
                api_key=key,
                base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            )
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")

    def llm_generate(self, question, text, feedback=None):
        rules = (
            "你是 SQLite SQL 生成专家。该数据库使用中性表名与字段名，语义如下：\n"
            "t_a=会员/客户；t_b=订单(含金额 f_amount、日期 f_date)；"
            "t_c=订单明细(含数量 f_qty)；t_d=商品(含 f_title、f_price)；"
            "t_e=类别(f_label)；t_f=地区(f_area)。\n"
            "要求：\n"
            "1. 只输出一条 SELECT，不解释、不 markdown、不注释。\n"
            "2. 表名 / 字段名必须来自给出的结构，禁止臆造。\n"
            "3. 多表关联必须使用给出的外键；“最…/前N”用 ORDER BY...LIMIT；"
            "问“是谁/哪个”返回名称和数值，问“是多少”只返回数值。\n"
            "4. “销量”指 SUM(f_qty) 按商品分组；问“最高销量”先分组 SUM 再 MAX。"
        )
        user = f"数据库表结构：\n{text}\n\n用户问题：{question}\n"
        if feedback:
            user += f"\n上一次 SQL 报错：{feedback}\n请修正后重新输出。"

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": rules},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        return resp.choices[0].message.content.strip().replace("```", "")

    def run(self, question):
        trace = [{"step": "理解问题", "detail": question}]

        anchors = anchor_tables(question)
        metrics = metric_tables(question)
        required = anchors + metrics

        if required:
            related, join_edges = connect_tables(GRAPH, required)
            trace.append({
                "step": "别名锚点 + BFS 补全",
                "detail": "、".join(related),
            })
        else:
            related = list(SCHEMA["tables"].keys())

        text = schema_text(related)

        if not self.client:
            return {"success": False, "error": "未配置 LLM_API_KEY", "trace": trace}

        feedback = None
        for attempt in range(3):
            sql = self.llm_generate(question, text, feedback)
            trace.append({"step": f"LLM 生成（第 {attempt + 1} 次）", "detail": sql})

            safe = validate_sql(sql)
            if not safe["valid"]:
                feedback = safe["message"]
                continue

            cols_ok = validate_columns(sql, schema=SCHEMA)
            if not cols_ok["valid"]:
                feedback = cols_ok["message"]
                continue

            join_ok = validate_join_path(sql, schema=SCHEMA)
            if not join_ok["valid"]:
                feedback = join_ok["message"]
                continue

            result = execute_sql(sql, db_path=DB_PATH)
            trace.append({"step": "执行成功", "detail": f"{len(result['rows'])} 行"})
            return {
                "success": True, "sql": sql.strip(),
                "columns": result["columns"], "rows": result["rows"],
                "tables": related, "attempts": attempt + 1, "trace": trace,
            }

        return {"success": False, "error": feedback or "生成失败", "trace": trace}


if __name__ == "__main__":
    service = SynthNL2SQL()
    for q in [
        "订单金额最高的前3个会员是谁？",
        "销量最高的商品是哪个？",
        "一共有多少会员？",
    ]:
        r = service.run(q)
        print("=" * 60)
        print("问题：", q)
        print("success：", r["success"])
        print("SQL：", r.get("sql", ""))
        print("结果：", r.get("rows", ""))
