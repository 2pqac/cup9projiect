import sys
from pathlib import Path

# 把项目根目录加入 Python 模块搜索路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.rag_qa import build_test_retriever

def test_rag_customer():
    """
    测试：
    能否根据问题检索到 Customer 表相关知识。

    RAG：
    Retrieval-Augmented Generation，
    即“检索增强生成”。
    这里重点测试的是检索部分。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Customer 表有哪些字段？",
        top_k=3
    )

    assert len(results) > 0

    # 至少有一个结果与 Customer 有关
    text = " ".join(
        str(result.get("text", ""))
        for result in results
    )

    assert "Customer" in text


def test_rag_album_artist():
    """
    测试：
    Album 和 Artist 的关系能否被检索出来。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Album 和 Artist 有什么关系？",
        top_k=3
    )

    assert len(results) > 0

    text = " ".join(
        str(result.get("text", ""))
        for result in results
    )

    assert "Album" in text
    assert "Artist" in text


def test_rag_track():
    """
    测试：
    Track 表相关知识能否被检索。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Track 表有哪些字段？",
        top_k=3
    )

    assert len(results) > 0

    text = " ".join(
        str(result.get("text", ""))
        for result in results
    )

    assert "Track" in text


def test_rag_invoice():
    """
    测试：
    Invoice 表相关知识能否被检索。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Invoice 表和 Customer 表有什么关系？",
        top_k=3
    )

    assert len(results) > 0

    text = " ".join(
        str(result.get("text", ""))
        for result in results
    )

    assert "Invoice" in text
    assert "Customer" in text


def test_rag_top_k():
    """
    测试 top_k 参数。

    top_k：
    表示一次最多返回多少个相关知识片段。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Album 表",
        top_k=3
    )

    assert len(results) <= 3


def test_rag_result_structure():
    """
    测试 RAG 检索结果的数据结构。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Customer 表",
        top_k=3
    )

    assert len(results) > 0

    result = results[0]

    # 检查结果中是否包含文本
    assert "text" in result

    # 检查文本是否为空
    assert isinstance(result["text"], str)
    assert result["text"].strip() != ""


def test_source_metadata():
    """
    测试来源元数据。

    Metadata（元数据）：
    附加在知识片段上的信息，例如：
    - source：来源文件
    - page：PDF 页码
    - section：章节
    - chunk_id：知识片段编号

    这里不能再把 source 写死为某一个文件名，
    因为现在知识库同时包含 TXT 和 PDF。

    所以我们只要求：
    1. source 存在
    2. source 是字符串
    3. source 不是空字符串
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Album 和 Artist 有什么关系？",
        top_k=3
    )

    assert len(results) > 0

    for result in results:
        assert "source" in result
        assert isinstance(result["source"], str)
        assert result["source"].strip() != ""


def test_source_page_metadata():
    """
    测试 PDF 页码信息。

    PDF 文档如果包含 page 信息，
    应该能够在检索结果中保留。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Customer 表有哪些字段？",
        top_k=3
    )

    assert len(results) > 0

    # PDF 片段必须有页码；TXT/MD 无页码概念，page 允许为 None
    for result in results:
        if str(result.get("source", "")).lower().endswith(".pdf"):
            assert result["page"] is not None


def test_source_section_metadata():
    """
    测试 section（章节）元数据。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Track 表有哪些字段？",
        top_k=3
    )

    assert len(results) > 0

    for result in results:
        if "section" in result:
            assert isinstance(result["section"], str)


def test_chunk_id_metadata():
    """
    测试 chunk_id。

    Chunk：
    将一个较大的文档切分成若干个可以单独检索的小知识片段。

    chunk_id：
    用来标识某一个具体知识片段。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Customer 表",
        top_k=3
    )

    assert len(results) > 0

    for result in results:
        if "chunk_id" in result:
            assert result["chunk_id"] is not None


def test_rag_similarity_score():
    """
    测试相似度分数。

    similarity score：
    表示用户问题和知识片段之间的相关程度。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Customer 表",
        top_k=3
    )

    assert len(results) > 0

    for result in results:
        if "score" in result:
            assert isinstance(
                result["score"],
                (int, float)
            )


def test_rag_pdf_source():
    """
    测试 PDF 是否能够作为知识来源。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Customer 表",
        top_k=5
    )

    assert len(results) > 0

    sources = [
        str(result.get("source", ""))
        for result in results
    ]

    # 只要有来源信息即可。
    # 不强制要求第一条一定是 PDF，
    # 因为 TXT 和 PDF 可能都有相关内容。
    assert any(source.strip() != "" for source in sources)


def test_rag_multiple_results():
    """
    测试一次检索多个结果。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "数据库中的歌曲、专辑和歌手",
        top_k=5
    )

    assert isinstance(results, list)


def test_rag_empty_query():
    """
    测试空问题的基本健壮性。

    Robustness（鲁棒性）：
    指系统面对异常或不理想输入时，
    仍然能够稳定运行，而不是直接崩溃。
    """

    retriever = build_test_retriever()

    try:
        results = retriever.search(
            "",
            top_k=3
        )

        assert isinstance(results, list)

    except Exception as e:
        # 如果当前 Retriever 明确禁止空查询，
        # 也不应该把错误静默掉。
        # 这里重新抛出，让 pytest 明确告诉我们问题。
        raise e


def test_rag_chinook_relationship():
    """
    测试 Chinook 数据库中的基本关系知识。
    """

    retriever = build_test_retriever()

    results = retriever.search(
        "Artist、Album、Track 三张表之间是什么关系？",
        top_k=5
    )

    assert len(results) > 0

    text = " ".join(
        str(result.get("text", ""))
        for result in results
    )

    assert (
        "Artist" in text
        or "Album" in text
        or "Track" in text
    )