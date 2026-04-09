"""天气查询工具（示例）"""

from app.tools.base import BaseAgentTool, ToolResult


class WeatherTool(BaseAgentTool):
    """天气查询工具"""

    name: str = "weather"
    description: str = "查询指定城市的天气信息，输入城市名称返回天气数据。"

    def run(self, *, city: str = "", **kwargs) -> ToolResult:
        """查询天气（当前为模拟实现）"""
        if not city:
            return ToolResult(success=False, error="请提供城市名称")

        # 模拟天气数据
        mock_weather = {
            "city": city,
            "temperature": "22°C",
            "condition": "晴",
            "humidity": "45%",
            "wind": "东南风 3级",
        }
        result = (
            f"📍 {mock_weather['city']}\n"
            f"🌡️ 温度: {mock_weather['temperature']}\n"
            f"🌤️ 天气: {mock_weather['condition']}\n"
            f"💧 湿度: {mock_weather['humidity']}\n"
            f"🌬️ 风力: {mock_weather['wind']}"
        )
        return ToolResult(result=result)
