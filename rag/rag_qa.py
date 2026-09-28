import os
import sys
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# 项目路径
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT)
    )


# ============================================================
# 导入 RAG 模块
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
# RAG 系统
# ============================================================

class RAGSystem:

    def __init__(
        self,
        top_k: int = 3
    ):

        self.top_k = top_k

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
        # Document -> Chunk
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
        # Chunk -> TF-IDF
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
    # 构建上下文
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

            section = result.get(
                "section",
                "未知章节"
            )

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
                f"章节：{section}\n"
                f"Chunk ID："
                f"{result['chunk_id']}\n"
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
    # LLM
    # ========================================================

    def generate_answer(
        self,
        question: str,
        context: str
    ) -> str:

        if not LLM_API_KEY:

            raise RuntimeError(
                "没有配置 LLM_API_KEY"
            )

        system_prompt = """
你是企业知识库问答助手。

你的任务：
根据提供的知识库资料回答用户问题。

必须遵守：

1. 只能根据提供的资料回答。
2. 不得凭空编造知识库中不存在的信息。
3. 如果资料不足，请明确回答：
   “知识库中没有足够的信息”。
4. 回答中使用 [资料1]、[资料2] 等引用。
5. 不要把相似但不相关的内容当成事实。
6. 回答要清晰、准确、简洁。
"""

        user_prompt = f"""
【知识库资料】

{context}

【用户问题】

{question}

请根据知识库资料回答。
"""

        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL
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

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if not content:

            raise RuntimeError(
                "LLM 没有返回答案"
            )

        return content.strip()


    # ========================================================
    # 完整 RAG
    # ========================================================

    def ask(
        self,
        question: str
    ) -> Dict[str, Any]:

        # ----------------------------------------------------
        # 1. 检索
        # ----------------------------------------------------

        results = self.retrieve(
            question
        )

        # ----------------------------------------------------
        # 2. Context
        # ----------------------------------------------------

        context = self.build_context(
            results
        )

        # ----------------------------------------------------
        # 3. LLM
        # ----------------------------------------------------

        answer = self.generate_answer(
            question,
            context
        )

        # ----------------------------------------------------
        # 4. Trace
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

                        "section": r.get(
                            "section",
                            "未知"
                        ),

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
                    "--------------------------------"
                )

                print(
                    "文件：",
                    source["source"]
                )

                print(
                    "页码：",
                    source["page"]
                )

                print(
                    "章节：",
                    source.get(
                        "section",
                        "未知"
                    )
                )

                print(
                    "Chunk ID：",
                    source["chunk_id"]
                )

                print(
                    "相似度：",
                    round(
                        source["score"],
                        4
                    )
                )

        except Exception as e:

            print(
                "运行失败：",
                e
            )

        print(
            "=" * 70
        )