from typing import List, Dict


def split_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 80
) -> List[str]:
    """
    将长文本切分为多个 Chunk。

    参数：

    chunk_size：
        每个 Chunk 最大字符数。

    overlap：
        相邻 Chunk 之间重叠多少字符。

    为什么要 overlap？

    因为如果一句话正好被切断，
    前后两个 Chunk 都保留部分内容，
    可以减少语义断裂。
    """

    text = text.strip()

    if not text:
        return []

    if overlap >= chunk_size:
        raise ValueError(
            "overlap 必须小于 chunk_size"
        )

    chunks = []

    start = 0

    text_length = len(text)

    while start < text_length:

        end = min(
            start + chunk_size,
            text_length
        )

        chunk = text[start:end].strip()

        if chunk:

            chunks.append(
                chunk
            )

        if end >= text_length:
            break

        start = end - overlap

    return chunks


def build_chunks(
    documents: List[Dict],
    chunk_size: int = 500,
    overlap: int = 80
) -> List[Dict]:
    """
    将 Document 转成 Chunk。

    每个 Chunk 保留：

    text
    source
    page
    chunk_id
    """

    all_chunks = []

    chunk_id = 0

    for document in documents:

        text = document["text"]

        chunks = split_text(
            text,
            chunk_size=chunk_size,
            overlap=overlap
        )

        for chunk in chunks:

            all_chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk,
                    "source": document[
                        "source"
                    ],
                    "page": document[
                        "page"
                    ],
                }
            )

            chunk_id += 1

    return all_chunks


if __name__ == "__main__":

    from document_loader import (
        load_knowledge_base
    )

    documents = load_knowledge_base()

    chunks = build_chunks(
        documents
    )

    print("=" * 70)

    print(
        "文档数量：",
        len(documents)
    )

    print(
        "Chunk 数量：",
        len(chunks)
    )

    for chunk in chunks[:3]:

        print()
        print(
            "Chunk ID：",
            chunk["chunk_id"]
        )

        print(
            "来源：",
            chunk["source"]
        )

        print(
            "页码：",
            chunk["page"]
        )

        print(
            "内容："
        )

        print(
            chunk["text"]
        )

    print("=" * 70)