import math
from collections import Counter


class Retriever:
    """
    简单 TF-IDF 检索器

    功能：
    1. 保存知识库 chunk
    2. 根据用户问题计算相似度
    3. 返回 top_k 相关内容

    每个结果包含：
    text
    content
    source
    page
    section
    chunk_id
    score
    """

    def __init__(self, documents):

        self.documents = documents

        self.index = []

        for i, doc in enumerate(documents):

            text = doc.get(
                "text",
                doc.get(
                    "content",
                    ""
                )
            )

            item = {

                # 原始文本
                "text": text,

                # 兼容测试
                "content": text,

                # 来源
                "source": doc.get(
                    "source",
                    "unknown"
                ),

                # PDF页码
                "page": doc.get(
                    "page",
                    1
                ),

                # 章节
                "section": doc.get(
                    "section",
                    "未知章节"
                ),

                # chunk编号
                "chunk_id": doc.get(
                    "chunk_id",
                    i
                )
            }


            self.index.append(item)



    def tokenize(self,text):

        """
        简单中文英文分词

        比赛初版够用
        """

        text = str(text)

        words=[]

        current=""

        for c in text:

            if c.isalnum():

                current += c

            else:

                if current:
                    words.append(current)
                    current=""

                if c.strip():

                    words.append(c)


        if current:
            words.append(current)


        return words



    def similarity(self,a,b):

        """
        计算余弦相似度
        """

        a_words=self.tokenize(a)

        b_words=self.tokenize(b)


        if not a_words or not b_words:
            return 0



        a_count=Counter(a_words)

        b_count=Counter(b_words)


        common=set(a_count)&set(b_count)


        numerator=sum(
            a_count[w]*b_count[w]
            for w in common
        )


        a_len=math.sqrt(
            sum(
                v*v
                for v in a_count.values()
            )
        )


        b_len=math.sqrt(
            sum(
                v*v
                for v in b_count.values()
            )
        )


        if a_len==0 or b_len==0:

            return 0


        return numerator/(a_len*b_len)




    def search(
        self,
        query,
        top_k=3
    ):

        """
        检索接口
        """

        if not query:

            return []



        results=[]


        for item in self.index:


            score=self.similarity(
                query,
                item["text"]
            )


            result=item.copy()

            result["score"]=score


            results.append(result)



        # 分数降序

        results.sort(
            key=lambda x:x["score"],
            reverse=True
        )


        return results[:top_k]