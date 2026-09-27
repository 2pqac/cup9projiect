"""
LLM 版 NL2SQL 主模块（A 同学核心交付）

完整链路：
  用户问题
    -> Schema Linking 粗召回相关表（复用 schema_linking）
    -> 组装相关表的 SQLite 建表结构
    -> 调大模型生成 SELECT 语句
    -> 安全校验（sqlglot）+ 表/字段真实存在校验
    -> 执行；若校验或执行失败，把报错回喂模型自我修正（最多 2 次）
    -> 返回 SQL、查询结果、完整推理链路 trace（供前端做可解释展示）

配置（项目根目录 .env）：
  LLM_API_KEY=你的key
  LLM_BASE_URL=https://api.deepseek.com
  LLM_MODEL=deepseek-chat
任何 OpenAI 兼容接口（DeepSeek / 智谱GLM / 通义 / 本地模型）都可用。
"""

import os
import json
from pathlib import Path
import sys

# 保证无论从哪个目录运行，都能 import 项目根下的模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openai import OpenAI
from dotenv import load_dotenv

from database.executor import execute_sql
from nl2sql.validator import validate_sql
from nl2sql.schema_validator import validate_columns
from nl2sql.nl2sql_generator import clean_sql
from nl2sql.schema_linking import schema_link

load_dotenv(PROJECT_ROOT / ".env")

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.json"
MAX_RETRY = 2


def load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def format_schema(tables, schema):
    """把指定表结构转成 SQLite 建表语句 + 外键说明，喂给模型参考。"""
    blocks = []
    for t in tables:
        info = schema["tables"].get(t)
        if not info:
            continue
        col_lines = []
        for c in info["columns"]:
            extra = " PRIMARY KEY" if c["primary_key"] else ""
            extra += " NOT NULL" if c["notnull"] else ""
            col_lines.append(f"  {c['name']} {c['type']}{extra}")
        blocks.append(f"CREATE TABLE {t} (\n" + ",\n".join(col_lines) + "\n);")
        for fk in info.get("foreign_keys", []):
            blocks.append(
                f"-- {t}.{fk['from_column']} 关联 "
                f"{fk['to_table']}.{fk['to_column']}"
            )
    return "\n".join(blocks)


SYSTEM_PROMPT = """你是资深数据库工程师，任务是把用户的中文问题翻译成一条可执行的 SQLite SELECT 语句。
必须遵守：
1. 只输出一条 SELECT 语句本身，禁止任何解释、注释或 Markdown 代码块。
2. 只能使用下面提供的表和字段，严禁臆造表名或字段名。
3. 多表关联必须使用给出的外键关系；求"最…/第一/前N"用 ORDER BY ... LIMIT。当问题问"是谁/哪个/哪些"时，SELECT 要返回名称，并同时给出对应统计数值；当问题只问"是多少"时，只返回统计数值，不要附带名称。
4. 统计数量用 COUNT，求和用 SUM，平均用 AVG，分组用 GROUP BY。
5. 文本值用单引号；日期为文本，按 'YYYY-MM-DD' 形式比较。"""


def call_llm(messages):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0,
    )
    return resp.choices[0].message.content.strip()


def nl2sql(question):
    """主入口：自然语言 -> SQL + 执行结果 + 推理链路。"""
    trace = []

    # 1. Schema Linking 粗召回
    linking = schema_link(question)
    related = linking["related_tables"]
    schema = load_schema()
    if not related:
        # 规则没召回到，Chinook 表少，直接给全部表，避免漏表
        related = list(schema["tables"].keys())
    trace.append({"step": "schema_linking", "related_tables": related})

    schema_text = format_schema(related, schema)

    # 2. 组装对话
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"数据库结构：\n{schema_text}\n\n问题：{question}"},
    ]

    last_error = ""
    for attempt in range(MAX_RETRY + 1):
        raw = call_llm(messages)
        sql = clean_sql(raw)
        trace.append({"step": f"生成SQL(第{attempt + 1}次)", "sql": sql})

        # 3. 安全 + 表字段校验
        safety = validate_sql(sql)
        if not safety["valid"]:
            last_error = safety["message"]
        else:
            col_check = validate_columns(sql)
            if not col_check["valid"]:
                last_error = col_check["message"]
            else:
                # 4. 真正执行
                try:
                    data = execute_sql(sql)
                    trace.append({"step": "执行成功", "rows": len(data["rows"])})
                    return {
                        "question": question,
                        "success": True,
                        "sql": sql,
                        "related_tables": related,
                        "columns": data["columns"],
                        "rows": data["rows"],
                        "trace": trace,
                    }
                except Exception as e:
                    last_error = f"数据库执行失败：{e}"

        # 记录错误并让模型修正
        trace.append({"step": "校验/执行报错", "error": last_error})
        messages.append({"role": "assistant", "content": sql})
        messages.append({
            "role": "user",
            "content": f"上面的 SQL 有问题：{last_error}\n请修正后，只输出正确的 SELECT 语句。",
        })

    return {
        "question": question,
        "success": False,
        "sql": sql,
        "related_tables": related,
        "columns": [],
        "rows": [],
        "trace": trace,
        "message": f"经{MAX_RETRY + 1}次尝试仍失败：{last_error}",
    }


if __name__ == "__main__":
    test_questions = [
        "哪个歌手的专辑最多？",
        "美国有多少客户？",
        "每个国家分别有多少客户？",
        "销售额最高的客户是谁？",
        "哪种音乐类型的歌曲最多？",
    ]
    for q in test_questions:
        print("=" * 70)
        print("问题：", q)
        r = nl2sql(q)
        print("是否成功：", r["success"])
        print("SQL：\n", r["sql"])
        if r["success"]:
            print("前3行结果：", r["rows"][:3])
        else:
            print(r.get("message"))
