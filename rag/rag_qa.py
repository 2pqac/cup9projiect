import os
import sys
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# 项目路径
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT)
    )


# ============================================================
# 导入自己的 RAG 模块
# ============================================================

from rag.document_loader import (
    load_knowledge_base
)

from rag.chunker import (
    build_chunks
)

from rag.retriever import (
    TfidfRetriever
)


# ============================================================
# 环境变量
# ============================================================

load_dotenv(
    PROJECT_ROOT / ".env"
)


LLM_API_KEY = os.getenv(
    "LLM_API_KEY",
    ""
)

LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://api.deepseek.com"
)

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "deepseek-chat"
)


# ============================================================
# LLM Client
# ============================================================

client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL
)


# ============================================================
# RAG System
# ============================================================

class RAGSystem:

    def __init__(
        self,
        top_k: int = 3
    ):

        self.top_k = top_k

        # ----------------------------------------------------
        # 1. 加载文档
        # ----------------------------------------------------

        print(
            "[RAG] 正在读取知识库..."
        )

        self.documents = (
            load_knowledge_base()
        )

        print(
            "[RAG] 文档读取完成：",
            len(self.documents)
        )

        # ----------------------------------------------------
        # 2. 文档切片
        # ----------------------------------------------------

        self.chunks = build_chunks(
            self.documents,
            chunk_size=500,
            overlap=80
        )

        print(
            "[RAG] Chunk 数量：",
            len(self.chunks)
        )

        # ----------------------------------------------------
        # 3. 构建检索器
        # ----------------------------------------------------

        self.retriever = (
            TfidfRetriever(
                self.chunks
            )
        )

        print(
            "[RAG] 检索器初始化完成"
        )


    # ========================================================
    # 检索
    # ========================================================

    def retrieve(
        self,
        question: str
    ):

        return self.retriever.search(
            question,
            top_k=self.top_k
        )


    # ========================================================
    # 组装 Context
    # ========================================================

    def build_context(
        self,
        results
    ):

        context_blocks = []

        for index, result in enumerate(
            results,
            start=1
        ):

            source = result[
                "source"
            ]

            page = result[
                "page"
            ]

            if page is None:

                location = source

            else:

                location = (
                    f"{source} "
                    f"第 {page} 页"
                )

            block = (
                f"[资料 {index}]\n"
                f"来源：{location}\n"
                f"内容：\n"
                f"{result['text']}"
            )

            context_blocks.append(
                block
            )

        return "\n\n".join(
            context_blocks
        )


    # ========================================================
    # 调用 LLM
    # ========================================================

    def generate_answer(
        self,
        question: str,
        context: str
    ) -> str:

        system_prompt = """
你是一个企业知识库问答助手。

你的任务是：
根据提供的知识库资料回答用户问题。

必须遵守：

1. 只能根据提供的资料回答。
2. 不要凭空编造知识库中不存在的信息。
3. 如果资料无法回答，请明确说“知识库中没有足够的信息”。
4. 回答尽量准确、简洁。
5. 在回答中使用 [资料1]、[资料2] 这样的引用标记。
"""

        user_prompt = f"""
知识库资料：

{context}

用户问题：

{question}

请根据以上资料回答问题。
"""

        if not LLM_API_KEY:

            raise RuntimeError(
                "没有配置 LLM_API_KEY。"
                "请检查项目根目录 .env"
            )

        response = (
            client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=0
            )
        )

        return (
            response
            .choices[0]
            .message
            .content
            .strip()
        )


    # ========================================================
    # 完整问答链
    # ========================================================

    def ask(
        self,
        question: str
    ) -> Dict[str, Any]:

        # ----------------------------------------------------
        # Step 1
        # 检索
        # ----------------------------------------------------

        results = self.retrieve(
            question
        )

        # ----------------------------------------------------
        # Step 2
        # Context
        # ----------------------------------------------------

        context = self.build_context(
            results
        )

        # ----------------------------------------------------
        # Step 3
        # LLM
        # ----------------------------------------------------

        answer = self.generate_answer(
            question,
            context
        )

        # ----------------------------------------------------
        # Step 4
        # trace
        # ----------------------------------------------------

        trace = [
            {
                "step": "document_loading",
                "document_count": len(
                    self.documents
                )
            },
            {
                "step": "chunking",
                "chunk_count": len(
                    self.chunks
                )
            },
            {
                "step": "retrieval",
                "top_k": self.top_k,
                "retrieved_chunks": [
                    {
                        "chunk_id": r[
                            "chunk_id"
                        ],
                        "source": r[
                            "source"
                        ],
                        "page": r[
                            "page"
                        ],
                        "score": round(
                            r["score"],
                            4
                        )
                    }
                    for r in results
                ]
            },
            {
                "step": "generation",
                "model": LLM_MODEL
            }
        ]

        return {
            "success": True,
            "question": question,
            "answer": answer,
            "sources": results,
            "trace": trace
        }


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":

    rag = RAGSystem(
        top_k=3
    )

    questions = [
        "Customer 表保存什么？",
        "Album 和 Artist 有什么关系？",
        "Track 表主要保存哪些信息？",
        "Invoice 和 Customer 有什么关系？"
    ]

    for question in questions:

        print("=" * 70)

        print(
            "用户问题："
        )

        print(
            question
        )

        try:

            result = rag.ask(
                question
            )

            print()

            print(
                "答案："
            )

            print(
                result["answer"]
            )

            print()

            print(
                "引用来源："
            )

            for source in result[
                "sources"
            ]:

                print(
                    f"- "
                    f"{source['source']}"
                    f" "
                    f"第 {source['page'] or '-'} 页"
                    f" "
                    f"(score="
                    f"{source['score']:.4f}"
                    f")"
                )

        except Exception as e:

            print(
                "运行失败：",
                e
            )

        print(
            "=" * 70
        )