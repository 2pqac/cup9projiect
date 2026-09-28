"""
RAG 自动测试

测试分为两部分：

第一部分：
离线测试，不需要 LLM API。

第二部分：
检索测试，不需要 LLM API。

第三部分：
完整 RAG 测试，需要 LLM_API_KEY。
"""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv


# ============================================================
# 1. 项目根目录
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
# 2. 读取 .env
# ============================================================

load_dotenv(
    PROJECT_ROOT / ".env"
)


# ============================================================
# 3. 导入 RAG 模块
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
# 4. 判断 API 是否配置
# ============================================================

def has_api_key():

    key = os.getenv(
        "LLM_API_KEY",
        ""
    ).strip()

    if not key:
        return False

    if "your_api_key" in key.lower():
        return False

    if "请在这里填入" in key:
        return False

    return True


# ============================================================
# 5. 知识库读取测试
# ============================================================

def test_knowledge_base_exists():

    knowledge_base = (
        PROJECT_ROOT
        / "knowledge_base"
    )

    assert knowledge_base.exists()

    assert knowledge_base.is_dir()


# ============================================================
# 6. 文档读取测试
# ============================================================

def test_document_loading():

    documents = (
        load_knowledge_base()
    )

    assert len(documents) > 0

    for document in documents:

        assert "text" in document

        assert "source" in document

        assert document["text"].strip()


# ============================================================
# 7. Chunk 测试
# ============================================================

def test_chunking():

    documents = (
        load_knowledge_base()
    )

    chunks = build_chunks(
        documents,
        chunk_size=500,
        overlap=80
    )

    assert len(chunks) > 0

    for chunk in chunks:

        assert "chunk_id" in chunk

        assert "text" in chunk

        assert "source" in chunk

        assert chunk["text"].strip()


# ============================================================
# 8. 检索器初始化测试
# ============================================================

def build_test_retriever():

    documents = (
        load_knowledge_base()
    )

    chunks = build_chunks(
        documents,
        chunk_size=500,
        overlap=80
    )

    retriever = TfidfRetriever(
        chunks
    )

    return retriever


def test_retriever_initialization():

    retriever = build_test_retriever()

    assert retriever is not None

    assert len(
        retriever.chunks
    ) > 0


# ============================================================
# 9. Customer 检索测试
# ============================================================

def test_retrieval_customer():

    retriever = (
        build_test_retriever()
    )

    results = retriever.search(
        "Customer 表保存什么？",
        top_k=3
    )

    assert len(results) > 0

    text = "\n".join(
        result["text"]
        for result in results
    )

    assert (
        "Customer" in text
        or "客户" in text
    )


# ============================================================
# 10. Album / Artist 检索测试
# ============================================================

def test_retrieval_album_artist():

    retriever = (
        build_test_retriever()
    )

    results = retriever.search(
        "Album 和 Artist 有什么关系？",
        top_k=3
    )

    assert len(results) > 0

    text = "\n".join(
        result["text"]
        for result in results
    )

    assert "Album" in text

    assert "Artist" in text


# ============================================================
# 11. Track 检索测试
# ============================================================

def test_retrieval_track():

    retriever = (
        build_test_retriever()
    )

    results = retriever.search(
        "Track 表保存歌曲的哪些信息？",
        top_k=3
    )

    assert len(results) > 0

    text = "\n".join(
        result["text"]
        for result in results
    )

    assert "Track" in text

    assert (
        "歌曲" in text
        or "TrackId" in text
    )


# ============================================================
# 12. Invoice / Customer 检索测试
# ============================================================

def test_retrieval_invoice_customer():

    retriever = (
        build_test_retriever()
    )

    results = retriever.search(
        "Invoice 和 Customer 有什么关系？",
        top_k=3
    )

    assert len(results) > 0

    text = "\n".join(
        result["text"]
        for result in results
    )

    assert "Invoice" in text

    assert "Customer" in text


# ============================================================
# 13. Top-K 测试
# ============================================================

def test_top_k():

    retriever = (
        build_test_retriever()
    )

    results = retriever.search(
        "Customer 表",
        top_k=3
    )

    assert len(results) <= 3


# ============================================================
# 14. 相似度排序测试
# ============================================================

def test_score_sorted():

    retriever = (
        build_test_retriever()
    )

    results = retriever.search(
        "Customer 表保存什么？",
        top_k=3
    )

    scores = [
        result["score"]
        for result in results
    ]

    assert scores == sorted(
        scores,
        reverse=True
    )


# ============================================================
# 15. 来源测试
# ============================================================

def test_source_metadata():

    retriever = (
        build_test_retriever()
    )

    results = retriever.search(
        "Album 和 Artist 有什么关系？",
        top_k=3
    )

    assert len(results) > 0

    for result in results:

        assert result[
            "source"
        ] == "chinook_guide.txt"

        assert "chunk_id" in result

        assert "score" in result


# ============================================================
# 16. 完整 RAG 测试
# ============================================================

@pytest.mark.skipif(
    not has_api_key(),
    reason=(
        "没有配置 LLM_API_KEY，"
        "跳过完整 RAG 测试"
    )
)
def test_full_rag():

    from rag.rag_qa import (
        RAGSystem
    )

    rag = RAGSystem(
        top_k=3
    )

    result = rag.ask(
        "Album 和 Artist 有什么关系？"
    )

    assert result["success"] is True

    assert result["answer"]

    assert len(
        result["sources"]
    ) > 0

    assert len(
        result["trace"]
    ) > 0