"""天气 Agent"""

from langchain_core.prompts import ChatPromptTemplate

from app.agents.base import AgentResponse, BaseAgent
from app.tools.weather import WeatherTool


class WeatherAgent(BaseAgent):
    """天气查询的专业 Agent"""

    name: str = "weather_agent"
    description: str = "负责查询天气信息，回答用户的天气相关问题"
    tools: list = [WeatherTool()]

    async def run(self, message: str, **kwargs) -> AgentResponse:
        """处理天气类请求"""
        # 先用 LLM 从用户消息中提取城市名称
        extract_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "从用户消息中提取城市名称。只返回城市名称本身，不要其他内容。"
                    "如果没有提到城市，返回 'NONE'。",
                ),
                ("human", "{message}"),
            ]
        )

        extract_chain = extract_prompt | self.llm
        extract_result = await extract_chain.ainvoke({"message": message})
        city = extract_result.content.strip()

        if city == "NONE":
            # 没有提取到城市，直接用 LLM 回答
            general_prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "你是一个天气助手。请提醒用户指定城市名称。",
                    ),
                    ("human", "{message}"),
                ]
            )
            chain = general_prompt | self.llm
            response = await chain.ainvoke({"message": message})
            return AgentResponse(
                agent_name=self.name,
                message=response.content,
            )

        # 用天气工具查询
        weather_tool = WeatherTool()
        weather_result = weather_tool.run(city=city)

        if not weather_result.success:
            return AgentResponse(
                agent_name=self.name,
                message=f"天气查询失败: {weather_result.error}",
                success=False,
                error=weather_result.error,
            )

        # 用 LLM 基于天气数据生成自然语言回答
        answer_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个天气助手。根据天气数据，用中文简洁地回答用户。",
                ),
                (
                    "human",
                    "用户问题: {question}\n天气数据: {weather}\n请用自然语言回答。",
                ),
            ]
        )

        chain = answer_prompt | self.llm
        response = await chain.ainvoke(
            {
                "question": message,
                "weather": weather_result.result,
            }
        )

        return AgentResponse(
            agent_name=self.name,
            message=response.content,
            tools_used=["weather"],
        )
