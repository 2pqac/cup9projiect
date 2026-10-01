# agent/main.py
# 系统总入口：根据问题路由到 NL2SQL 或 RAG，并展示答案、来源与推理链。

import os
import sys


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
sys.path.insert(0, BASE_DIR)

from agent.router import AgentRouter
from nl2sql.llm_nl2sql import NL2SQL
from rag.rag_qa import RAGService


class Cup8Agent:
    """多模态智能问数 / 问答智能体。"""

    def __init__(self):
        print("正在初始化系统...")
        self.nl2sql = NL2SQL()
        self.rag = RAGService()
        self.router = AgentRouter(self.nl2sql, self.rag)
        print("系统初始化完成\n")

    def run(self, question):
        mode = self.router.route(question)

        print("=" * 60)
        print("用户问题：", question)

        if mode == "sql":
            print("AI 分析：NL2SQL 数据库查询\n")
            result = self.nl2sql.run(question)
            self.show_sql(result)
        else:
            print("AI 分析：RAG 知识库检索\n")
            result = self.rag.run(question)
            self.show_rag(result)

    # ---------------- SQL 结果展示 ----------------

    def show_sql(self, result):
        if not result.get("success"):
            print("查询失败：", result.get("message"))
            self.show_trace(result.get("trace", []))
            return

        print("答案：")
        print(result.get("answer"))

        print("\n查询解释：")
        print(result.get("explanation"))

        print("\n生成 SQL：")
        print(result.get("sql"))

        print("\n查询结果：")
        columns = result.get("columns", [])
        if columns:
            print(" | ".join(str(c) for c in columns))
        rows = result.get("data", result.get("rows", []))
        for row in rows:
            print(" | ".join(str(v) for v in row))

        print("\n数据来源表：", "、".join(result.get("tables", [])))

        self.show_trace(result.get("trace", []))

    # ---------------- RAG 结果展示 ----------------

    def show_rag(self, result):
        if not result.get("success"):
            print("查询失败：", result.get("message"))
            return

        print("答案：")
        print(result.get("answer"))

        print("\n来源：")
        for s in result.get("sources", []):
            print(
                f'  - {s.get("source")} 第{s.get("page")}页 '
                f'{s.get("section")} (score={s.get("score")})'
            )

        self.show_trace(result.get("trace", []))

    # ---------------- 推理链（可解释性） ----------------

    def show_trace(self, trace):
        print("\n推理链：")
        for i, step in enumerate(trace, start=1):
            print(f'  {i}. {step.get("step")}: {step.get("detail")}')


if __name__ == "__main__":
    print("=" * 60)
    print("       Cup8 多模态智能问数/问答系统")
    print("=" * 60)

    agent = Cup8Agent()

    while True:
        q = input("\n请输入问题: ")
        if q == "exit":
            break
        agent.run(q)
