import httpx
import json
import logging
from typing import Dict, Any
from app.config import settings

logger = logging.getLogger("microbubble.search")


class SearchService:
    """MiMo 联网搜索服务"""

    def __init__(self):
        self._api_key = settings.MIMO_API_KEY
        self._base_url = settings.MIMO_BASE_URL
        self._model = settings.MIMO_MODEL

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """
        执行联网搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数

        Returns:
            {"status": "success", "results": [...], "answer": "..."}
        """
        if not self.is_configured:
            return {
                "status": "error",
                "message": "搜索功能未配置（缺少 MIMO_API_KEY）",
                "query": query,
                "results": [],
            }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "api-key": self._api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "user", "content": query}
                        ],
                        "tools": [
                            {
                                "type": "web_search",
                                "max_keyword": 3,
                                "force_search": True,
                                "limit": max_results,
                                "user_location": {
                                    "type": "approximate",
                                    "country": "China"
                                }
                            }
                        ],
                        "max_completion_tokens": 2048,
                        "temperature": 1.0,
                        "top_p": 0.95,
                        "stream": False,
                    },
                )

                if response.status_code != 200:
                    logger.error(f"搜索 API 返回错误: {response.status_code} - {response.text}")
                    return {
                        "status": "error",
                        "message": f"搜索失败: HTTP {response.status_code}",
                        "query": query,
                        "results": [],
                    }

                data = response.json()

                # 提取搜索结果
                answer = ""
                results = []

                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    message = choice.get("message", {})
                    answer = message.get("content", "")

                    # 提取工具调用中的搜索结果
                    tool_calls = message.get("tool_calls", [])
                    for tc in tool_calls:
                        if tc.get("function", {}).get("name") == "web_search":
                            try:
                                search_result = json.loads(tc["function"].get("arguments", "{}"))
                                if "results" in search_result:
                                    results = search_result["results"]
                            except (json.JSONDecodeError, TypeError):
                                pass

                return {
                    "status": "success",
                    "query": query,
                    "answer": answer,
                    "results": results[:max_results] if results else [],
                    "result_count": len(results),
                }

        except httpx.TimeoutException:
            logger.error(f"搜索超时: {query}")
            return {
                "status": "error",
                "message": "搜索请求超时",
                "query": query,
                "results": [],
            }
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return {
                "status": "error",
                "message": f"搜索失败: {str(e)}",
                "query": query,
                "results": [],
            }


# 全局单例
search_service = SearchService()
