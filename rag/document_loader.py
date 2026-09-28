from pathlib import Path
from typing import List, Dict

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"


def load_txt(file_path: Path) -> List[Dict]:
    """
    读取 TXT / MD 文件。

    返回格式：

    [
        {
            "text": "...",
            "source": "...",
            "page": None
        }
    ]
    """

    text = file_path.read_text(
        encoding="utf-8"
    )

    return [
        {
            "text": text,
            "source": file_path.name,
            "page": None,
        }
    ]


def load_pdf(file_path: Path) -> List[Dict]:
    """
    读取 PDF。

    PDF 会按照页进行读取。

    每一页都保留自己的 page 信息，
    后面做来源引用时可以显示：

    文件名 + 页码
    """

    reader = PdfReader(
        str(file_path)
    )

    documents = []

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        text = page.extract_text() or ""

        if not text.strip():
            continue

        documents.append(
            {
                "text": text,
                "source": file_path.name,
                "page": page_number,
            }
        )

    return documents


def load_document(file_path: Path) -> List[Dict]:
    """
    根据文件类型自动选择加载方式。
    """

    suffix = file_path.suffix.lower()

    if suffix in [".txt", ".md"]:

        return load_txt(file_path)

    if suffix == ".pdf":

        return load_pdf(file_path)

    raise ValueError(
        f"暂不支持的文件类型：{suffix}"
    )


def load_knowledge_base(
    directory: Path = KNOWLEDGE_BASE_DIR
) -> List[Dict]:
    """
    读取整个 knowledge_base 文件夹。

    当前支持：

    TXT
    MD
    PDF
    """

    if not directory.exists():

        raise FileNotFoundError(
            f"知识库目录不存在：{directory}"
        )

    documents = []

    supported_suffixes = {
        ".txt",
        ".md",
        ".pdf",
    }

    for file_path in sorted(
        directory.iterdir()
    ):

        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in supported_suffixes:
            continue

        try:

            docs = load_document(
                file_path
            )

            documents.extend(
                docs
            )

        except Exception as e:

            print(
                f"[警告] 读取失败："
                f"{file_path.name}"
                f" -> {e}"
            )

    if not documents:

        raise ValueError(
            "知识库中没有读取到有效文档。"
        )

    return documents


if __name__ == "__main__":

    docs = load_knowledge_base()

    print("=" * 70)

    print(
        "成功读取文档数量：",
        len(docs)
    )

    for index, doc in enumerate(
        docs,
        start=1
    ):

        text = doc["text"]

        print()
        print(
            f"第 {index} 个文档片段"
        )

        print(
            "来源：",
            doc["source"]
        )

        print(
            "页码：",
            doc["page"]
        )

        print(
            "字符数：",
            len(text)
        )

        print(
            "前100个字符："
        )

        print(
            text[:100]
        )

    print("=" * 70)