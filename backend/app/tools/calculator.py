"""计算器工具"""

from app.tools.base import BaseAgentTool, ToolResult


class CalculatorTool(BaseAgentTool):
    """数学计算工具，支持基本四则运算"""

    name: str = "calculator"
    description: str = "执行数学计算，输入一个数学表达式并返回结果。例如: '2 + 3 * 4'"

    def run(self, *, expression: str = "", **kwargs) -> ToolResult:
        """执行数学表达式计算"""
        if not expression:
            return ToolResult(success=False, error="请提供数学表达式")

        try:
            # 安全起见，只允许基本数学运算符
            allowed_chars = set("0123456789+-*/().% ")
            if not all(c in allowed_chars for c in expression):
                return ToolResult(
                    success=False,
                    error="表达式包含不允许的字符，仅支持数字和基本运算符 (+-*/.%)",
                )

            result = eval(expression)  # noqa: S307
            return ToolResult(result=f"{expression} = {result}")
        except Exception as e:
            return ToolResult(success=False, error=f"计算错误: {e}")
