import asyncio
import httpx
import logging
import re
from typing import Dict, Any, List
from urllib.parse import quote_plus

logger = logging.getLogger("microbubble.search")


class SearchService:
    """联网搜索服务（搜狗微信 + 必应双引擎）"""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    @property
    def is_configured(self) -> bool:
        return True

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        try:
            results = await self._multi_search(query, max_results)

            if not results:
                return {
                    "status": "success",
                    "query": query,
                    "answer": "未找到相关搜索结果",
                    "results": [],
                    "result_count": 0,
                }

            snippets = []
            for i, r in enumerate(results, 1):
                line = f"{i}. {r['title']}"
                if r["snippet"]:
                    line += f"\n   {r['snippet']}"
                line += f"\n   来源: {r['url']}"
                snippets.append(line)

            return {
                "status": "success",
                "query": query,
                "answer": "\n\n".join(snippets),
                "results": results,
                "result_count": len(results),
            }

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return {
                "status": "error",
                "message": f"搜索失败: {str(e)}",
                "query": query,
                "results": [],
            }

    async def _multi_search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """双引擎搜索：搜狗微信（中文内容）+ 必应（英文内容）"""
        results = []

        sogou_task = asyncio.create_task(self._sogou_weixin_search(query, max_results))
        bing_task = asyncio.create_task(self._bing_search(query, max_results))

        sogou_results, bing_results = await asyncio.gather(
            sogou_task, bing_task, return_exceptions=True
        )

        if isinstance(sogou_results, list):
            results.extend(sogou_results)
        else:
            logger.warning(f"搜狗微信搜索失败: {sogou_results}")

        if isinstance(bing_results, list):
            existing_urls = {r["url"] for r in results}
            for r in bing_results:
                if r["url"] not in existing_urls:
                    results.append(r)
                    existing_urls.add(r["url"])
        else:
            logger.warning(f"必应搜索失败: {bing_results}")

        return results[:max_results]

    # ── 搜狗微信搜索 ──

    async def _sogou_weixin_search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        params = {"type": "2", "query": query}

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                "https://weixin.sogou.com/weixin",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            return self._parse_sogou(resp.text, max_results)

    @staticmethod
    def _parse_sogou(html: str, max_results: int) -> List[Dict[str, str]]:
        results = []
        h3_matches = list(re.finditer(r"<h3[^>]*>(.*?)</h3>", html, re.DOTALL))

        for idx, m in enumerate(h3_matches):
            if len(results) >= max_results:
                break

            h3_html = m.group(1)
            a_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', h3_html, re.DOTALL)
            if not a_match:
                continue

            url = a_match.group(1).strip()
            title = re.sub(r"<[^>]+>", "", a_match.group(2)).strip()

            if url.startswith("/link?"):
                url = f"https://weixin.sogou.com{url}"

            snippet = ""
            next_start = h3_matches[idx + 1].start() if idx + 1 < len(h3_matches) else m.end() + 3000
            between = html[m.end():next_start]
            for pm in re.finditer(r"<p[^>]*>(.*?)</p>", between, re.DOTALL):
                text = re.sub(r"<[^>]+>", "", pm.group(1)).strip()
                if text and len(text) > 10:
                    snippet = text
                    break

            if title:
                results.append({"title": title, "url": url, "snippet": snippet})

        return results

    # ── 必应搜索 ──

    async def _bing_search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        params = {"q": query, "setlang": "zh"}

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                "https://www.bing.com/search",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            return self._parse_bing(resp.text, max_results)

    @staticmethod
    def _parse_bing(html: str, max_results: int) -> List[Dict[str, str]]:
        results = []
        parts = html.split('class="b_algo"')

        for part in parts[1:]:
            if len(results) >= max_results:
                break

            title_match = re.search(
                r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                part,
                re.DOTALL,
            )
            if not title_match:
                continue

            url = title_match.group(1).strip()
            title = re.sub(r"<[^>]+>", "", title_match.group(2)).strip()

            snippet = ""
            snippet_match = re.search(r"<p[^>]*>(.*?)</p>", part, re.DOTALL)
            if snippet_match:
                snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()

            if title and url.startswith("http"):
                results.append({"title": title, "url": url, "snippet": snippet})

        return results


# 全局单例
search_service = SearchService()
