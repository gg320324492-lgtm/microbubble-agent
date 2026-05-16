"""腾讯会议 API 集成"""

import hashlib
import hmac
import time
import uuid
import httpx
from typing import Optional, Dict, Any

from app.config import settings


BASE_URL = "https://api.meeting.qq.com"


class TencentMeetingService:
    """腾讯会议 API 服务"""

    def __init__(self):
        self.app_id = settings.TENCENT_MEETING_APP_ID
        self.app_secret = settings.TENCENT_MEETING_APP_SECRET

    def _generate_signature(self, method: str, path: str, timestamp: str, nonce: str) -> str:
        """生成 HMAC-SHA256 签名"""
        body = f"{method}\n{path}\n{timestamp}\n{nonce}"
        signature = hmac.new(
            self.app_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _headers(self, method: str, path: str) -> Dict[str, str]:
        """构建请求头"""
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex[:16]
        signature = self._generate_signature(method, path, timestamp, nonce)

        return {
            "AppId": self.app_id,
            "X-TC-Timestamp": timestamp,
            "X-TC-Nonce": nonce,
            "X-TC-Signature": signature,
            "Content-Type": "application/json"
        }

    async def create_meeting(
        self,
        subject: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        meeting_type: int = 1,
        instance_id: int = 1
    ) -> Dict[str, Any]:
        """
        创建会议

        Args:
            subject: 会议主题
            start_time: 开始时间（Unix 时间戳字符串）
            end_time: 结束时间（Unix 时间戳字符串）
            meeting_type: 1=预约会议, 0=快速会议
            instance_id: 终端设备类型

        Returns:
            会议信息，含 meeting_id, join_url 等
        """
        path = "/v1/meetings"
        payload = {
            "instanceid": instance_id,
            "subject": subject,
            "type": meeting_type,
        }
        if start_time:
            payload["start_time"] = start_time
        if end_time:
            payload["end_time"] = end_time

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE_URL}{path}",
                json=payload,
                headers=self._headers("POST", path)
            )
            resp.raise_for_status()
            return resp.json()

    async def get_meeting_info(self, meeting_id: str) -> Dict[str, Any]:
        """获取会议详情"""
        path = f"/v1/meetings/{meeting_id}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}{path}",
                headers=self._headers("GET", path)
            )
            resp.raise_for_status()
            return resp.json()

    async def cancel_meeting(self, meeting_id: str) -> Dict[str, Any]:
        """取消会议"""
        path = f"/v1/meetings/{meeting_id}/cancel"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE_URL}{path}",
                headers=self._headers("POST", path)
            )
            resp.raise_for_status()
            return resp.json()

    async def get_meeting_recordings(self, meeting_id: str) -> Dict[str, Any]:
        """获取会议录制文件"""
        path = f"/v1/meetings/{meeting_id}/recordings"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}{path}",
                headers=self._headers("GET", path)
            )
            resp.raise_for_status()
            return resp.json()


# 全局实例
tencent_meeting = TencentMeetingService()
