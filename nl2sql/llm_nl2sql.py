"""
LLM 版 NL2SQL（自然语言转 SQL）

对外提供：
- NL2SQL 类：agent/main.py 直接实例化，调用 run(question)
- nl2sql() 函数：向后兼容旧测试

内部流程：
问题 -> Schema Linking 粗召回相关表 -> 组装表结构
     -> LLM 生成 SELECT -> 安全校验 + 表字段校验
     -> 执行；失败把报错回喂模型自我修正（最多 3 次）
     -> LLM 不可用时用规则字典兜底
"""

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.executor import execute_sql
from nl2sql.validator import validate_sql
from nl2sql.schema_validator import validate_columns
from nl2sql.join_validator import validate_join_path
from nl2sql.explainer import build_query_logic, build_answer
from nl2sql.schema_linking import schema_link
from nl2sql.join_graph import (
    build_graph,
    connect_tables,
    detect_metric_tables,
)
import sqlglot
from sqlglot import exp


SCHEMA_JSON = PROJECT_ROOT / "database" / "schema.json"

load_dotenv(PROJECT_ROOT / ".env")


def actual_tables_in_sql(sql):
    """从 SQL AST 提取真实引用的表名（含 JOIN / 子查询）。"""
    tree = sqlglot.parse_one(sql, read="sqlite")
    names = []
    for table in tree.find_all(exp.Table):
        if table.name and table.name not in names:
            names.append(table.name)
    return names


# ============================================================
# 规则兜底（LLM 不可用 / 连续失败时使用）
# ============================================================

FALLBACK_SQL = {
    "美国有多少客户":
        "SELECT COUNT(*) FROM Customer WHERE Country='USA';",
    "每个国家分别有多少客户":
        "SELECT Country, COUNT(*) AS CustomerCount FROM Customer GROUP BY Country;",
    "哪个歌手的专辑最多":
        ("SELECT Artist.Name, COUNT(Album.AlbumId) AS AlbumCount FROM Artist "
         "JOIN Album ON Artist.ArtistId = Album.ArtistId "
         "GROUP BY Artist.ArtistId ORDER BY AlbumCount DESC LIMIT 1;"),
    "哪种音乐类型的歌曲最多":
        ("SELECT Genre.Name, COUNT(Track.TrackId) AS TrackCount FROM Genre "
         "JOIN Track ON Genre.GenreId = Track.GenreId "
         "GROUP BY Genre.GenreId ORDER BY TrackCount DESC LIMIT 1;"),
    "销售额最高的客户":
        ("SELECT Customer.FirstName, Customer.LastName, SUM(Invoice.Total) AS Sales "
         "FROM Customer JOIN Invoice ON Customer.CustomerId = Invoice.CustomerId "
         "GROUP BY Customer.CustomerId ORDER BY Sales DESC LIMIT 1;"),
    "所有发票的总金额":
        "SELECT SUM(Total) FROM Invoice;",
    "发票平均金额":
        "SELECT AVG(Total) FROM Invoice;",
    "客户总数":
        "SELECT COUNT(*) FROM Customer;",
}


class NL2SQL:
    """自然语言 -> SQL -> 查询结果"""

    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")

        # key 未填则不启用 LLM，走规则兜底
        self.client = None
        if self.api_key and not self.api_key.startswith("请"):
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

        with open(SCHEMA_JSON, encoding="utf-8") as f:
            self.schema = json.load(f)

        # 外键关系图：用于 BFS 自动补全多表 JOIN 路径
        self.graph = build_graph(self.schema)

    # --------------------------------------------------------
    # 1. 组装相关表的 CREATE 结构
    # --------------------------------------------------------

    def build_schema_text(self, table_names):
        tables = self.schema["tables"]
        names = []
        for t in table_names:
            if t in tables and t not in names:
                names.append(t)

        blocks = []
        for t in names:
            info = tables[t]
            cols = []
            for c in info["columns"]:
                line = f'  {c["name"]} {c["type"] or "TEXT"}'
                if c["primary_key"]:
                    line += " PRIMARY KEY"
                cols.append(line)
            for fk in info.get("foreign_keys", []):
                cols.append(
                    f'  FOREIGN KEY ({fk["from_column"]}) '
                    f'REFERENCES {fk["to_table"]}({fk["to_column"]})'
                )
            blocks.append(f"CREATE TABLE {t} (\n" + ",\n".join(cols) + "\n);")
        return "\n\n".join(blocks)

    # --------------------------------------------------------
    # 2. 调用大模型生成 SQL
    # --------------------------------------------------------

    def llm_generate(self, question, schema_text, error_feedback=None):
        rules = (
            "你是一个 SQLite SQL 生成专家。根据用户问题和数据库表结构，"
            "生成一条可直接执行的 SELECT 语句。要求：\n"
            "1. 只输出一条 SELECT 语句，不要解释、不要 markdown 代码块、不要注释。\n"
            "2. 表名和字段名必须来自给出的结构，禁止臆造。\n"
            "3. 多表关联必须使用给出的外键关系；求“最…/第一/前N”用 ORDER BY ... LIMIT。"
            "当问题问“是谁/哪个/哪些”时，SELECT 要返回名称，并同时给出对应统计数值；"
            "当问题只问“是多少”时，只返回统计数值，不要附带名称。\n"
            "4. 日期字段是文本，按年过滤用 LIKE '2023%'。\n"
            "5. “销量/销售量”指 SUM(Quantity) 按歌曲 TrackId 分组求和；"
            "问“最高销量”要先分组 SUM 再取 MAX，不能直接 MAX(Quantity)。"
        )
        user = f"数据库表结构：\n{schema_text}\n\n用户问题：{question}\n"
        if error_feedback:
            user += f"\n上一次的 SQL 报错：{error_feedback}\n请修正后重新输出。"

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": rules},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()

        # 去掉可能的 ```sql ... ``` 包裹，定位到 SELECT 起点
        match = re.search(r"select", raw, flags=re.IGNORECASE)
        if match:
            raw = raw[match.start():]
        raw = raw.replace("```", "").strip()
        return raw

    # --------------------------------------------------------
    # 3. 规则兜底生成
    # --------------------------------------------------------

    def fallback_generate(self, question):
        q = question.replace("？", "").replace("?", "").strip()
        for key, sql in FALLBACK_SQL.items():
            if key in q:
                return sql
        return None

    # --------------------------------------------------------
    # 4. 执行一条已通过校验的 SQL，统一返回结构
    # --------------------------------------------------------

    def _execute_and_pack(self, sql, trace, via, tables=None, attempts=1, question=""):
        safe = validate_sql(sql)
        if not safe["valid"]:
            return {"success": False, "message": safe["message"], "error": safe["message"], "trace": trace}

        schema_ok = validate_columns(sql)
        if not schema_ok["valid"]:
            return {"success": False, "message": schema_ok["message"], "error": schema_ok["message"], "trace": trace}

        join_ok = validate_join_path(sql)
        if not join_ok["valid"]:
            return {"success": False, "message": join_ok["message"], "error": join_ok["message"], "trace": trace}

        result = execute_sql(sql)
        actual_tables = actual_tables_in_sql(sql)
        trace.append({"step": via, "detail": f"{len(result['rows'])} 行结果"})
        trace.append({"step": "实际使用数据表", "detail": "、".join(actual_tables)})

        answer = build_answer(question, result["columns"], result["rows"])
        explanation = build_query_logic(sql)["summary"]
        trace.append({"step": "生成答案与查询解释", "detail": answer})

        return {
            "success": True,
            "sql": sql.strip(),
            "columns": result["columns"],
            "rows": result["rows"],
            "data": result["rows"],
            "tables": tables or [],
            "recalled_tables": tables or [],
            "actual_tables": actual_tables,
            "attempts": attempts,
            "answer": answer,
            "explanation": explanation,
            "trace": trace,
        }

    # --------------------------------------------------------
    # 5. 主流程
    # --------------------------------------------------------

    def run(self, question, use_join_graph=True):
        trace = [{"step": "理解问题", "detail": question}]

        # 1) 实体锚点表：规则召回（客户 / 歌曲 / 歌手 ...）
        anchors = []
        try:
            link = schema_link(question)
            anchors = link["related_tables"]
            trace.append({
                "step": "Schema Linking 召回实体表",
                "detail": "、".join(anchors) if anchors else "未召回到实体表",
            })
        except Exception:
            pass

        # 2) 指标字段所在表：指标词 -> 字段 -> 自动定位（消费额 / 销量 ...）
        metric_tables = detect_metric_tables(question, self.schema)

        if use_join_graph:
            # 3a) 外键图 + BFS 自动补全 JOIN 路径（含中间表，不写特例）
            required = list(anchors) + metric_tables
            if required:
                related, join_edges = connect_tables(self.graph, required)
                if join_edges:
                    trace.append({
                        "step": "外键路径补全 (BFS)",
                        "detail": "；".join(
                            f'{e["left"]}→{e["right"]}' for e in join_edges
                        ),
                    })
            else:
                related = list(self.schema["tables"].keys())
        else:
            # 3b) 基线：只用规则召回的锚点表，不做外键路径补全
            related = list(dict.fromkeys(anchors))
            if not related:
                related = list(self.schema["tables"].keys())

        schema_text = self.build_schema_text(related)

        # LLM 主干：生成 -> 校验 -> 执行，失败回喂自我修正
        if self.client:
            feedback = None
            for attempt in range(3):
                try:
                    sql = self.llm_generate(
                        question, schema_text, error_feedback=feedback
                    )
                    trace.append({
                        "step": f"LLM 生成 SQL（第 {attempt + 1} 次）",
                        "detail": sql,
                    })

                    safe = validate_sql(sql)
                    if not safe["valid"]:
                        feedback = safe["message"]
                        continue

                    schema_ok = validate_columns(sql)
                    if not schema_ok["valid"]:
                        feedback = schema_ok["message"]
                        continue

                    join_ok = validate_join_path(sql)
                    if not join_ok["valid"]:
                        feedback = join_ok["message"]
                        trace.append({
                            "step": "JOIN 校验未通过，回喂修正",
                            "detail": join_ok["message"],
                        })
                        continue

                    return self._execute_and_pack(
                        sql, trace, "执行 SQL 成功",
                        tables=related, attempts=attempt + 1, question=question,
                    )
                except Exception as e:
                    feedback = str(e)
                    continue

            # LLM 连续失败，尝试规则兜底
            fallback = self.fallback_generate(question)
            if fallback:
                trace.append({"step": "LLM 失败，降级规则兜底", "detail": fallback})
                return self._execute_and_pack(
                    fallback, trace, "规则兜底执行成功",
                    tables=related, attempts=0, question=question,
                )
            msg = feedback or "LLM 生成失败"
            return {
                "success": False,
                "message": msg,
                "error": msg,
                "trace": trace,
            }

        # 未配置 LLM：直接规则兜底
        fallback = self.fallback_generate(question)
        if fallback:
            return self._execute_and_pack(
                fallback, trace, "规则兜底执行成功",
                tables=related, attempts=0, question=question,
            )
        return {
            "success": False,
            "message": "未配置 LLM_API_KEY，且规则未命中该问题",
            "error": "未配置 LLM_API_KEY，且规则未命中该问题",
            "trace": trace,
        }


# ============================================================
# 模块级函数：向后兼容（from nl2sql.llm_nl2sql import nl2sql）
# ============================================================

_default_instance = None


def nl2sql(question):
    global _default_instance
    if _default_instance is None:
        _default_instance = NL2SQL()
    return _default_instance.run(question)


if __name__ == "__main__":
    service = NL2SQL()
    print("=" * 60)
    print("NL2SQL 交互（输入 exit 退出）")
    print("=" * 60)
    while True:
        q = input("\n请输入问题: ")
        if q == "exit":
            break
        answer = service.run(q)
        if answer["success"]:
            print("\n生成 SQL:\n", answer["sql"])
            print("\n查询结果:")
            for row in answer["rows"]:
                print(" ", row)
        else:
            print("\n失败：", answer["message"])
