"""搜索工具（示例）"""

from app.tools.base import BaseAgentTool, ToolResult


class SearchTool(BaseAgentTool):
    """模拟搜索工具"""

    name: str = "search"
    description: str = "搜索互联网信息，输入搜索关键词返回相关结果。"

    def run(self, *, query: str = "", **kwargs) -> ToolResult:
        """执行搜索（当前为模拟实现）"""
        if not query:
            return ToolResult(success=False, error="请提供搜索关键词")

        # 模拟搜索结果
        mock_results = [
            f"搜索结果 1: 关于「{query}」的详细信息...",
            f"搜索结果 2: 「{query}」相关技术文档...",
            f"搜索结果 3: 「{query}」最新动态...",
        ]
        return ToolResult(result="\n".join(mock_results))
