"""
Tool 基类
所有自定义工具继承此类，并实现 run 方法
"""

from abc import ABC, abstractmethod

from langchain_core.tools import BaseTool
from pydantic import BaseModel


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool = True
    result: str = ""
    error: str | None = None


class BaseAgentTool(ABC):
    """
    自定义工具基类
    子类需实现:
      - name: 工具名称
      - description: 工具描述
      - run(): 执行逻辑
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, **kwargs) -> ToolResult:
        """执行工具逻辑"""
        ...

    def to_langchain_tool(self) -> BaseTool:
        """将自定义工具转换为 LangChain Tool"""
        from langchain_core.tools import tool as lc_tool

        @lc_tool(name=self.name, description=self.description)
        def _wrapped(**kwargs) -> str:
            result = self.run(**kwargs)
            if result.success:
                return result.result
            return f"Error: {result.error}"

        return _wrapped
