"""计算 Agent"""

from langchain_core.prompts import ChatPromptTemplate

from app.agents.base import AgentResponse, BaseAgent
from app.tools.calculator import CalculatorTool


class CalculatorAgent(BaseAgent):
    """数学计算的专业 Agent"""

    name: str = "calculator_agent"
    description: str = "负责数学计算任务，处理用户的数学表达式和数值计算需求"
    tools: list = [CalculatorTool()]

    async def run(self, message: str, **kwargs) -> AgentResponse:
        """处理计算类请求"""
        # 先用 LLM 从用户消息中提取数学表达式
        extract_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "从用户消息中提取数学表达式。只返回数学表达式本身，不要其他内容。"
                    "如果没有数学表达式，返回 'NONE'。",
                ),
                ("human", "{message}"),
            ]
        )

        extract_chain = extract_prompt | self.llm
        extract_result = await extract_chain.ainvoke({"message": message})
        expression = extract_result.content.strip()

        if expression == "NONE":
            # 没有提取到表达式，直接用 LLM 回答
            general_prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "你是一个数学助手。用中文简洁地回答用户的数学问题。",
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

        # 用计算器工具执行计算
        calc_tool = CalculatorTool()
        calc_result = calc_tool.run(expression=expression)

        if not calc_result.success:
            return AgentResponse(
                agent_name=self.name,
                message=f"计算失败: {calc_result.error}",
                success=False,
                error=calc_result.error,
            )

        # 用 LLM 基于计算结果生成自然语言回答
        answer_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个数学助手。根据计算结果，用中文简洁地回答用户。",
                ),
                (
                    "human",
                    "用户问题: {question}\n计算结果: {result}\n请用自然语言回答。",
                ),
            ]
        )

        chain = answer_prompt | self.llm
        response = await chain.ainvoke(
            {
                "question": message,
                "result": calc_result.result,
            }
        )

        return AgentResponse(
            agent_name=self.name,
            message=response.content,
            tools_used=["calculator"],
        )
