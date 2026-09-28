import re
from typing import List, Dict


# ============================================================
# 1. 判断是否是中文章节标题
# ============================================================

SECTION_PATTERN = re.compile(
    r"^[一二三四五六七八九十百]+、.+$"
)


# ============================================================
# 2. 清理空行
# ============================================================

def clean_text(text: str) -> str:
    """
    清理多余空白。

    注意：
    不把所有换行都删除，
    因为换行有助于保留文档结构。
    """

    lines = []

    for line in text.splitlines():

        line = line.strip()

        if line:

            lines.append(line)

    return "\n".join(lines)


# ============================================================
# 3. 按章节拆分
# ============================================================

def split_by_sections(
    text: str
) -> List[Dict]:
    """
    优先按照：

    一、
    二、
    三、
    四、

    这样的章节标题拆分。

    返回：

    [
        {
            "title": "三、Album 表",
            "text": "..."
        }
    ]
    """

    text = clean_text(text)

    if not text:

        return []

    lines = text.splitlines()

    sections = []

    current_title = "文档开头"

    current_lines = []

    for line in lines:

        if SECTION_PATTERN.match(line):

            if current_lines:

                section_text = "\n".join(
                    current_lines
                ).strip()

                if section_text:

                    sections.append(
                        {
                            "title": current_title,
                            "text": section_text
                        }
                    )

            current_title = line

            current_lines = [
                line
            ]

        else:

            current_lines.append(line)

    # 处理最后一节
    if current_lines:

        section_text = "\n".join(
            current_lines
        ).strip()

        if section_text:

            sections.append(
                {
                    "title": current_title,
                    "text": section_text
                }
            )

    return sections


# ============================================================
# 4. 长章节进一步切片
# ============================================================

def split_long_section(
    section_text: str,
    chunk_size: int = 500,
    overlap: int = 80
) -> List[str]:
    """
    如果一个章节过长，
    再按照字符长度进行切片。

    但每个 Chunk 会尽量保留章节标题。
    """

    section_text = section_text.strip()

    if not section_text:

        return []

    if overlap >= chunk_size:

        raise ValueError(
            "overlap 必须小于 chunk_size"
        )

    if len(section_text) <= chunk_size:

        return [
            section_text
        ]

    chunks = []

    start = 0

    total_length = len(
        section_text
    )

    while start < total_length:

        end = min(
            start + chunk_size,
            total_length
        )

        chunk = section_text[
            start:end
        ].strip()

        if chunk:

            chunks.append(
                chunk
            )

        if end >= total_length:

            break

        start = end - overlap

    return chunks


# ============================================================
# 5. 完整构建 Chunk
# ============================================================

def build_chunks(
    documents: List[Dict],
    chunk_size: int = 500,
    overlap: int = 80
) -> List[Dict]:
    """
    Document -> Chunk。

    每个 Chunk 保留：

    chunk_id
    text
    source
    page
    section
    """

    all_chunks = []

    chunk_id = 0

    for document in documents:

        text = document[
            "text"
        ]

        sections = split_by_sections(
            text
        )

        # 如果没有检测到章节
        if not sections:

            sections = [
                {
                    "title": "正文",
                    "text": text
                }
            ]

        for section in sections:

            title = section[
                "title"
            ]

            section_chunks = (
                split_long_section(
                    section["text"],
                    chunk_size=chunk_size,
                    overlap=overlap
                )
            )

            for chunk_text in section_chunks:

                # 如果切出来的 Chunk 没包含标题，
                # 自动在前面加标题。
                if not chunk_text.startswith(
                    title
                ):

                    chunk_text = (
                        f"{title}\n"
                        f"{chunk_text}"
                    )

                all_chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "text": chunk_text,
                        "source": document[
                            "source"
                        ],
                        "page": document[
                            "page"
                        ],
                        "section": title,
                    }
                )

                chunk_id += 1

    return all_chunks


# ============================================================
# 6. 测试
# ============================================================

if __name__ == "__main__":

    from document_loader import (
        load_knowledge_base
    )

    documents = (
        load_knowledge_base()
    )

    chunks = build_chunks(
        documents,
        chunk_size=500,
        overlap=80
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

    for chunk in chunks[:5]:

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
            "章节：",
            chunk["section"]
        )

        print(
            "内容："
        )

        print(
            chunk["text"]
        )

    print("=" * 70)