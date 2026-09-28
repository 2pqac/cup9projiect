from typing import List, Dict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class TfidfRetriever:
    """
    TF-IDF 文本检索器。

    TF-IDF：
    用数字表示文本中的词/字符重要程度。

    Cosine Similarity：
    计算用户问题与 Chunk 的相似程度。

    返回 Top-K：
    最相关的 K 个 Chunk。
    """

    def __init__(
        self,
        chunks: List[Dict]
    ):

        if not chunks:

            raise ValueError(
                "chunks 不能为空"
            )

        self.chunks = chunks

        self.vectorizer = (
            TfidfVectorizer(
                analyzer="char",
                ngram_range=(2, 4),
                sublinear_tf=True,
            )
        )

        texts = [
            chunk["text"]
            for chunk in chunks
        ]

        self.matrix = (
            self.vectorizer.fit_transform(
                texts
            )
        )

    # ========================================================
    # 检索
    # ========================================================

    def search(
        self,
        query: str,
        top_k: int = 3
    ) -> List[Dict]:

        query = query.strip()

        if not query:

            raise ValueError(
                "query 不能为空"
            )

        if top_k <= 0:

            raise ValueError(
                "top_k 必须大于 0"
            )

        query_vector = (
            self.vectorizer.transform(
                [query]
            )
        )

        scores = cosine_similarity(
            query_vector,
            self.matrix
        )[0]

        ranked_indexes = (
            scores.argsort()[::-1]
        )

        results = []

        for index in ranked_indexes[
            :top_k
        ]:

            chunk = dict(
                self.chunks[index]
            )

            chunk["score"] = float(
                scores[index]
            )

            results.append(
                chunk
            )

        return results


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":

    from document_loader import (
        load_knowledge_base
    )

    from chunker import (
        build_chunks
    )

    documents = (
        load_knowledge_base()
    )

    chunks = build_chunks(
        documents
    )

    retriever = TfidfRetriever(
        chunks
    )

    test_questions = [

        "Customer 表保存什么？",

        "Album 和 Artist 有什么关系？",

        "Track 表保存哪些信息？",

        "Invoice 和 Customer 有什么关系？",
    ]

    for question in test_questions:

        print("=" * 70)

        print(
            "用户问题：",
            question
        )

        results = retriever.search(
            question,
            top_k=3
        )

        for result in results:

            print()

            print(
                "Chunk ID：",
                result["chunk_id"]
            )

            print(
                "相似度：",
                round(
                    result["score"],
                    4
                )
            )

            print(
                "来源：",
                result["source"]
            )

            print(
                "页码：",
                result["page"]
            )

            print(
                "章节：",
                result.get(
                    "section",
                    "未知"
                )
            )

            print(
                "内容："
            )

            print(
                result["text"]
            )

    print("=" * 70)