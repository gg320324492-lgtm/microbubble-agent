"""微信客服消息轮询服务"""

import logging
import httpx
from app.config import settings

logger = logging.getLogger("microbubble.wechat.kf")


class KFService:
    """微信客服消息服务"""

    def __init__(self):
        self.api_base = settings.WECHAT_API_BASE_URL or "https://qyapi.weixin.qq.com"
        self.corp_id = settings.WECHAT_CORP_ID
        self.secret = settings.WECHAT_SECRET
        self._access_token = None

    async def get_access_token(self) -> str:
        """获取 access_token"""
        if self._access_token:
            return self._access_token

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_base}/cgi-bin/gettoken",
                params={"corpid": self.corp_id, "corpsecret": self.secret}
            )
            data = resp.json()
            if data.get("errcode") == 0:
                self._access_token = data["access_token"]
                return self._access_token
            else:
                logger.error(f"获取 access_token 失败: {data}")
                return ""

    async def get_kf_accounts(self) -> list:
        """获取客服账号列表"""
        token = await self.get_access_token()
        if not token:
            return []

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_base}/cgi-bin/kf/account/list",
                params={"access_token": token}
            )
            data = resp.json()
            if data.get("errcode") == 0:
                return data.get("account_list", [])
            else:
                logger.error(f"获取客服账号失败: {data}")
                return []

    async def sync_msg(self, open_kfid: str, cursor: str = "", limit: int = 100) -> dict:
        """拉取客服消息"""
        token = await self.get_access_token()
        if not token:
            return {"errcode": -1, "errmsg": "获取token失败"}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.api_base}/cgi-bin/kf/sync_msg?access_token={token}",
                json={
                    "open_kfid": open_kfid,
                    "cursor": cursor,
                    "limit": limit
                }
            )
            return resp.json()

    async def send_msg(self, open_kfid: str, external_userid: str, msg_type: str, content: str) -> dict:
        """发送客服消息"""
        token = await self.get_access_token()
        if not token:
            return {"errcode": -1, "errmsg": "获取token失败"}

        msg_body = {
            "touser": external_userid,
            "open_kfid": open_kfid,
            "msgtype": msg_type,
        }

        if msg_type == "text":
            msg_body["text"] = {"content": content}
        elif msg_type == "markdown":
            msg_body["markdown"] = {"content": content}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.api_base}/cgi-bin/kf/send_msg?access_token={token}",
                json=msg_body
            )
            return resp.json()


# 全局实例
kf_service = KFService()
