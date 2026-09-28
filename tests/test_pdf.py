from pathlib import Path
import sys


# ============================================================
# 项目根目录
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
# 导入
# ============================================================

from rag.document_loader import (
    load_document
)

from rag.chunker import (
    build_chunks
)


# ============================================================
# PDF 路径
# ============================================================

PDF_PATH = (
    PROJECT_ROOT
    / "knowledge_base"
    / "chinook_guide.pdf"
)


# ============================================================
# 1. PDF 文件存在
# ============================================================

def test_pdf_exists():

    assert PDF_PATH.exists()

    assert PDF_PATH.is_file()


# ============================================================
# 2. PDF 可以读取
# ============================================================

def test_pdf_loading():

    documents = load_document(
        PDF_PATH
    )

    assert len(documents) > 0


# ============================================================
# 3. PDF 必须有页码
# ============================================================

def test_pdf_has_page_number():

    documents = load_document(
        PDF_PATH
    )

    for document in documents:

        assert (
            document["page"]
            is not None
        )

        assert (
            document["page"]
            >= 1
        )


# ============================================================
# 4. PDF source 正确
# ============================================================

def test_pdf_source():

    documents = load_document(
        PDF_PATH
    )

    for document in documents:

        assert (
            document["source"]
            == "chinook_guide.pdf"
        )


# ============================================================
# 5. PDF 能生成 Chunk
# ============================================================

def test_pdf_chunking():

    documents = load_document(
        PDF_PATH
    )

    chunks = build_chunks(
        documents,
        chunk_size=500,
        overlap=80
    )

    assert len(chunks) > 0


# ============================================================
# 6. Chunk 保留页码
# ============================================================

def test_chunk_preserves_page():

    documents = load_document(
        PDF_PATH
    )

    chunks = build_chunks(
        documents
    )

    for chunk in chunks:

        assert (
            chunk["page"]
            is not None
        )


# ============================================================
# 7. Chunk 保留来源
# ============================================================

def test_chunk_preserves_source():

    documents = load_document(
        PDF_PATH
    )

    chunks = build_chunks(
        documents
    )

    for chunk in chunks:

        assert (
            chunk["source"]
            == "chinook_guide.pdf"
        )


# ============================================================
# 8. Chunk 保留章节
# ============================================================

def test_chunk_preserves_section():

    documents = load_document(
        PDF_PATH
    )

    chunks = build_chunks(
        documents
    )

    for chunk in chunks:

        assert "section" in chunk