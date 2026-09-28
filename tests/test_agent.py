from agent.router import AgentRouter



class FakeSQL:


    def run(self,question):

        return "SQL查询结果"



class FakeRAG:


    def answer(self,question):

        return "RAG知识答案"



def test_sql_route():


    agent=AgentRouter(

        FakeSQL(),

        FakeRAG()

    )


    result=agent.run(
        "美国有多少客户？"
    )


    assert result["mode"]=="sql"



def test_rag_route():


    agent=AgentRouter(

        FakeSQL(),

        FakeRAG()

    )


    result=agent.run(
        "Customer表保存什么？"
    )


    assert result["mode"]=="rag"