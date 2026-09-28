"""
RAG（检索增强生成）问答服务

流程：
加载知识库(PDF/TXT/MD) -> 结构化切片 -> TF-IDF 检索 top_k
     -> 把命中片段喂给 LLM，严格基于片段生成答案
     -> 返回答案 + 来源(文件/页码/章节/原文片段) + 推理链 trace

对外接口：
- RAGService.answer(question)：Agent 路由调用
- RAGService.run(question)：命令行 / main.py 调用（answer 的别名）
- build_test_retriever()：供测试使用
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from rag.document_loader import load_knowledge_base
from rag.chunker import build_chunks
from rag.retriever import Retriever


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def build_test_retriever():
    """构建检索器（加载整个知识库并切片），供测试使用。"""
    documents = load_knowledge_base()
    chunks = build_chunks(documents, chunk_size=500, overlap=80)
    return Retriever(chunks)


class RAGService:
    """知识库检索 + LLM 生成问答。"""

    def __init__(self, top_k=3):
        self.top_k = top_k

        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")

        # key 未填则不启用 LLM，仅返回原文片段
        self.client = None
        if self.api_key and not self.api_key.startswith("请"):
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

        # 知识库 -> 切片 -> 检索器
        documents = load_knowledge_base()
        chunks = build_chunks(documents, chunk_size=500, overlap=80)
        self.retriever = Retriever(chunks)

    # --------------------------------------------------------
    # 1. 整理来源信息
    # --------------------------------------------------------

    def _build_sources(self, results):
        sources = []
        for item in results:
            sources.append({
                "source": item.get("source"),
                "page": item.get("page"),
                "section": item.get("section"),
                "score": round(float(item.get("score", 0)), 3),
                "snippet": item.get("text", "")[:200],
            })
        return sources

    # --------------------------------------------------------
    # 2. 把检索片段交给 LLM 生成答案
    # --------------------------------------------------------

    def _llm_answer(self, question, results):
        blocks = []
        for i, item in enumerate(results):
            blocks.append(
                f"[片段{i + 1}] 来源：{item.get('source')} "
                f"第{item.get('page')}页 {item.get('section')}\n{item.get('text')}"
            )
        context_text = "\n\n".join(blocks)

        system = (
            "你是知识库问答助手。必须严格依据提供的资料片段回答问题。"
            "要求：1. 只能使用片段中的信息，片段没有的内容就回答“根据现有资料无法确定”，"
            "禁止编造；2. 回答简洁准确；3. 不得输出资料中没有的数字或结论。"
        )
        user = f"资料片段：\n{context_text}\n\n用户问题：{question}"

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        return resp.choices[0].message.content.strip()

    # --------------------------------------------------------
    # 3. 主问答接口
    # --------------------------------------------------------

    def answer(self, question):
        trace = [{"step": "检索知识库", "detail": f"top_k={self.top_k}"}]

        # 多拉一些用于去重（同一文档的 PDF/TXT 会产生重复章节）
        candidates = self.retriever.search(
            question, top_k=max(self.top_k * 2, 6)
        )

        # 按章节去重：同一章节只保留一条，优先有页码(PDF)、其次 score 高
        best = {}
        for r in candidates:
            key = r.get("section")
            if key not in best:
                best[key] = r
                continue
            cur = best[key]
            r_pdf = r.get("page") is not None
            c_pdf = cur.get("page") is not None
            if (r_pdf and not c_pdf) or (
                r_pdf == c_pdf and r.get("score", 0) > cur.get("score", 0)
            ):
                best[key] = r

        results = sorted(
            best.values(), key=lambda x: x.get("score", 0), reverse=True
        )[:self.top_k]

        # 若全部 score 为 0，至少返回前几条，避免空
        if not any(r.get("score", 0) > 0 for r in results):
            results = candidates[:self.top_k]

        sources = self._build_sources(results)
        trace.append({
            "step": "召回相关片段",
            "detail": "；".join(
                f'{s["source"]} 第{s["page"]}页' for s in sources
            ),
        })

        if self.client and results:
            text = self._llm_answer(question, results)
            trace.append({"step": "LLM 基于片段生成答案", "detail": text})
        else:
            # 未配置 LLM 或无召回：返回原文片段作为兜底
            text = "\n".join(
                r.get("text", "") for r in results
            )[:1500]
            trace.append({"step": "未配置 LLM，返回原文片段", "detail": ""})

        return {
            "success": True,
            "answer": text,
            "sources": sources,
            "trace": trace,
        }

    # run 作为 answer 的别名
    def run(self, question):
        return self.answer(question)


if __name__ == "__main__":
    service = RAGService()
    print("=" * 60)
    print("RAG 知识库问答（输入 exit 退出）")
    print("=" * 60)
    while True:
        q = input("\n请输入问题: ")
        if q == "exit":
            break
        result = service.answer(q)
        print("\n答案：\n", result["answer"])
        print("\n来源：")
        for s in result["sources"]:
            print(f'  - {s["source"]} 第{s["page"]}页 {s["section"]}')
