"""腾讯会议 REST API 集成

签名算法参考：https://meeting.tencent.com/developers/api
"""

import hashlib
import hmac
import time
import uuid
import logging
import httpx
from typing import Optional, Dict, Any

from app.config import settings

logger = logging.getLogger("microbubble.tencent_meeting")

BASE_URL = "https://api.meeting.qq.com"

# 路径前缀（签名时使用 openapi 前缀）
OPENAPI_PREFIX = "openapi"


class TencentMeetingService:
    """腾讯会议 API 服务"""

    def __init__(self):
        self.sdk_id = settings.TENCENT_MEETING_SDK_ID
        self.sdk_key = settings.TENCENT_MEETING_SDK_KEY
        self.default_userid = settings.TENCENT_MEETING_USERID

    @property
    def is_configured(self) -> bool:
        """检查是否已配置凭据"""
        return bool(self.sdk_id and self.sdk_key)

    def _generate_signature(self, method: str, uri: str, timestamp: str, nonce: str) -> str:
        """
        生成 HMAC-SHA256 签名

        签名原文格式：{HTTPMethod}\n{URI}\n{Timestamp}\n{Nonce}
        URI 需要加 openapi 前缀
        """
        # URI 格式：openapi/v1/meetings（不含查询参数）
        body = f"{method}\n{uri}\n{timestamp}\n{nonce}"
        signature = hmac.new(
            self.sdk_key.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _build_uri(self, path: str) -> str:
        """构建带 openapi 前缀的 URI"""
        # 去掉开头的 /，加上 openapi/ 前缀
        clean_path = path.lstrip("/")
        return f"{OPENAPI_PREFIX}/{clean_path}"

    def _headers(self, method: str, path: str) -> Dict[str, str]:
        """构建请求头"""
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex[:16]
        uri = self._build_uri(path)
        signature = self._generate_signature(method, uri, timestamp, nonce)

        return {
            "SdkId": self.sdk_id,
            "X-TC-Key": self.sdk_id,
            "X-TC-Timestamp": timestamp,
            "X-TC-Nonce": nonce,
            "X-TC-Signature": signature,
            "Content-Type": "application/json",
            "AppId": self.sdk_id,  # 兼容部分接口
        }

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        发送 API 请求（带重试）

        Args:
            method: HTTP 方法
            path: API 路径（不含 BASE_URL 和 openapi 前缀）
            json_data: 请求体
            max_retries: 最大重试次数

        Returns:
            API 响应 JSON

        Raises:
            Exception: API 调用失败
        """
        full_path = f"/v1{path}" if not path.startswith("/v1") else path
        uri = self._build_uri(full_path)
        headers = self._headers(method, full_path)
        url = f"{BASE_URL}/{uri}"

        last_error = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    if method == "GET":
                        resp = await client.get(url, headers=headers)
                    elif method == "POST":
                        resp = await client.post(url, headers=headers, json=json_data)
                    elif method == "PUT":
                        resp = await client.put(url, headers=headers, json=json_data)
                    elif method == "DELETE":
                        resp = await client.delete(url, headers=headers)
                    else:
                        raise ValueError(f"不支持的 HTTP 方法: {method}")

                    data = resp.json()
                    error_code = data.get("error_code", 0)

                    if error_code == 0:
                        return data

                    # 可重试的错误码（限流、服务端错误）
                    if error_code in (1001, 5001, 5002) and attempt < max_retries - 1:
                        wait = 2 ** attempt
                        logger.warning(f"腾讯会议 API 限流/错误，{wait}s 后重试: {data}")
                        import asyncio
                        await asyncio.sleep(wait)
                        continue

                    logger.error(f"腾讯会议 API 调用失败: {data}")
                    raise Exception(f"腾讯会议 API 错误: {data.get('error_message', '未知错误')} (code={error_code})")

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"腾讯会议 API 超时，{wait}s 后重试")
                    import asyncio
                    await asyncio.sleep(wait)
                    continue
                raise

        raise last_error or Exception("腾讯会议 API 调用失败")

    async def create_meeting(
        self,
        subject: str,
        userid: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        meeting_type: int = 1,
        instance_id: int = 1
    ) -> Dict[str, Any]:
        """
        创建会议

        Args:
            subject: 会议主题
            userid: 主持人企业用户ID（默认用配置中的）
            start_time: 开始时间（"YYYY-MM-DD HH:MM:SS" 格式或 Unix 时间戳字符串）
            end_time: 结束时间
            meeting_type: 1=预约会议, 0=快速会议
            instance_id: 终端设备类型

        Returns:
            会议信息，含 meeting_id, join_url 等
        """
        payload = {
            "instanceid": instance_id,
            "subject": subject,
            "type": meeting_type,
            "host": {
                "userid": userid or self.default_userid
            }
        }
        if start_time:
            payload["start_time"] = start_time
        if end_time:
            payload["end_time"] = end_time

        result = await self._request("POST", "/meetings", json_data=payload)
        logger.info(f"创建腾讯会议成功: {subject}")
        return result

    async def get_meeting_info(self, meeting_id: str) -> Dict[str, Any]:
        """获取会议详情"""
        return await self._request("GET", f"/meetings/{meeting_id}")

    async def cancel_meeting(self, meeting_id: str, userid: Optional[str] = None) -> Dict[str, Any]:
        """取消会议"""
        payload = {"userid": userid or self.default_userid}
        return await self._request("POST", f"/meetings/{meeting_id}/cancel", json_data=payload)

    async def end_meeting(self, meeting_id: str, userid: Optional[str] = None) -> Dict[str, Any]:
        """结束会议"""
        payload = {"userid": userid or self.default_userid}
        return await self._request("POST", f"/meetings/{meeting_id}/end", json_data=payload)

    async def list_meetings(
        self,
        userid: Optional[str] = None,
        meeting_type: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """查询会议列表"""
        params = {"userid": userid or self.default_userid}
        if meeting_type is not None:
            params["meeting_type"] = meeting_type
        # 实际使用 query params，这里简化为 POST body
        return await self._request("POST", "/meetings/list", json_data=params)

    async def get_meeting_recordings(self, meeting_id: str) -> Dict[str, Any]:
        """获取会议录制文件"""
        return await self._request("GET", f"/meetings/{meeting_id}/recordings")

    def verify_webhook_signature(self, token: str, timestamp: str, nonce: str, signature: str) -> bool:
        """
        验证 Webhook 回调签名

        签名原文：{token}\n{timestamp}\n{nonce}\n{SdkKey}
        """
        body = f"{token}\n{timestamp}\n{nonce}\n{self.sdk_key}"
        expected = hashlib.sha256(body.encode("utf-8")).hexdigest()
        return hmac.compare_digest(expected, signature)


# 全局实例
tencent_meeting = TencentMeetingService()
