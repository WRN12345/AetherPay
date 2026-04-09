"""搜索 Agent"""

from langchain_core.prompts import ChatPromptTemplate

from app.agents.base import AgentResponse, BaseAgent
from app.tools.search import SearchTool


class SearchAgent(BaseAgent):
    """搜索信息的专业 Agent"""

    name: str = "search_agent"
    description: str = "负责搜索互联网信息，回答用户的信息查询需求"
    tools: list = [SearchTool()]

    async def run(self, message: str, **kwargs) -> AgentResponse:
        """处理搜索类请求"""
        search_tool = SearchTool()

        # 先用工具获取搜索结果
        search_result = search_tool.run(query=message)

        if not search_result.success:
            return AgentResponse(
                agent_name=self.name,
                message=f"搜索失败: {search_result.error}",
                success=False,
                error=search_result.error,
            )

        # 用 LLM 基于搜索结果生成回答
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个搜索助手。根据搜索结果，用简洁的中文回答用户问题。",
                ),
                ("human", "搜索结果:\n{search_results}\n\n用户问题: {question}"),
            ]
        )

        chain = prompt | self.llm
        response = await chain.ainvoke(
            {
                "search_results": search_result.result,
                "question": message,
            }
        )

        return AgentResponse(
            agent_name=self.name,
            message=response.content,
            tools_used=["search"],
        )
