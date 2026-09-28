# agent/router.py

class AgentRouter:
    """
    Agent 路由器

    作用：
    判断用户问题应该交给：
    1. NL2SQL
    2. RAG知识问答
    """

    def __init__(
        self,
        nl2sql_service=None,
        rag_service=None
    ):

        self.nl2sql_service = nl2sql_service
        self.rag_service = rag_service


    def route(self, question):

        question = question.strip()


        # SQL问题关键词
        sql_keywords = [
            "多少",
            "几个",
            "数量",
            "统计",
            "总数",
            "最多",
            "最高",
            "最低",
            "平均",
            "销售",
            "客户",
            "国家",
            "歌曲",
            "专辑"
        ]


        for key in sql_keywords:

            if key in question:

                return "sql"


        # 默认走RAG
        return "rag"



    def run(self, question):

        mode = self.route(question)


        if mode == "sql":

            if self.nl2sql_service:

                return {
                    "mode":"sql",
                    "result":
                        self.nl2sql_service.run(question)
                }


        else:

            if self.rag_service:

                return {
                    "mode":"rag",
                    "result":
                        self.rag_service.answer(question)
                }


        return {
            "mode":mode,
            "result":"没有可用服务"
        }