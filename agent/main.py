import os
import sys


BASE_DIR=os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


sys.path.append(BASE_DIR)



from agent.router import AgentRouter

from nl2sql.llm_nl2sql import NL2SQL

from rag.rag_qa import RAGService





class Cup8Agent:



    def __init__(self):


        print("正在初始化系统...")


        self.nl2sql=NL2SQL()


        self.rag=RAGService()



        self.router=AgentRouter(

            self.nl2sql,

            self.rag

        )


        print("系统初始化完成")




    def run(self,question):


        print("\n")
        print("="*60)


        print(
            "用户问题:"
        )


        print(question)



        mode=self.router.route(
            question
        )


        print("\nAI分析模块:")



        if mode=="sql":


            print(
                "NL2SQL 数据库查询"
            )


            result=self.nl2sql.run(
                question
            )


            self.show_sql(result)



        else:


            print(
                "RAG 知识库检索"
            )


            result=self.rag.run(
                question
            )


            self.show_rag(result)





    def show_sql(self,result):


        print("\n")
        print("-"*40)


        print(
            "SQL执行结果"
        )


        print("-"*40)



        if not result["success"]:


            print(
                result["message"]
            )


            return



        print("\n生成SQL:\n")


        print(
            result["sql"]
        )



        print("\n查询结果:\n")



        for row in result["data"]:


            print(row)



        print("\n")





    def show_rag(self,result):


        print("\n")
        print("-"*40)


        print(
            "知识库回答"
        )


        print("-"*40)



        print(result)







if __name__=="__main__":



    print("="*60)

    print(
        "       Cup8 智能数据库问答系统"
    )

    print("="*60)



    agent=Cup8Agent()



    while True:


        q=input(
            "\n请输入问题:"
        )



        if q=="exit":

            break



        agent.run(q)