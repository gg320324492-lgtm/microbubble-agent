"""企业微信机器人模块"""

import httpx
import json
import logging
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from app.models.base import utcnow

from app.config import settings

if TYPE_CHECKING:
    from app.models.member import Member

logger = logging.getLogger("microbubble.wechat")


class WeChatBot:
    """企业微信机器人"""

    def __init__(self):
        self.corp_id = settings.WECHAT_CORP_ID
        self.agent_id = settings.WECHAT_AGENT_ID
        self.secret = settings.WECHAT_SECRET
        self.api_base = settings.WECHAT_API_BASE_URL.rstrip("/")
        self._access_token = None
        self._token_expires = None

    async def _get_access_token(self) -> str:
        """获取access_token"""
        now = utcnow()
        if self._access_token and self._token_expires and now < self._token_expires:
            return self._access_token

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base}/cgi-bin/gettoken",
                params={
                    "corpid": self.corp_id,
                    "corpsecret": self.secret
                }
            )
            data = response.json()

            if data.get("errcode") == 0:
                self._access_token = data["access_token"]
                # 提前5分钟过期
                self._token_expires = now + timedelta(seconds=data["expires_in"] - 300)
                return self._access_token
            else:
                raise Exception(f"获取access_token失败: {data}")

    async def send_message(
        self,
        user_id: str,
        content: str,
        msg_type: str = "text"
    ) -> dict:
        """
        发送消息给用户

        Args:
            user_id: 用户ID
            content: 消息内容
            msg_type: 消息类型（text/markdown）

        Returns:
            发送结果
        """
        token = await self._get_access_token()

        if msg_type == "text":
            data = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": self.agent_id,
                "text": {
                    "content": content
                }
            }
        elif msg_type == "markdown":
            data = {
                "touser": user_id,
                "msgtype": "markdown",
                "agentid": self.agent_id,
                "markdown": {
                    "content": content
                }
            }
        else:
            raise ValueError(f"不支持的消息类型: {msg_type}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/cgi-bin/message/send?access_token={token}",
                json=data
            )
            return response.json()

    async def list_department_members(self, department_id: int = 1) -> list:
        """获取部门成员列表，返回 [{userid, name, ...}]"""
        token = await self._get_access_token()
        all_members = []
        fetch_child = 1  # 递归获取子部门

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base}/cgi-bin/user/list",
                params={
                    "access_token": token,
                    "department_id": department_id,
                    "fetch_child": fetch_child
                }
            )
            data = response.json()
            if data.get("errcode") == 0:
                all_members = data.get("userlist", [])
            else:
                logger.warning(f"获取部门成员列表失败: {data}")

        return all_members

    async def send_task_reminder(
        self,
        user_id: str,
        task_title: str,
        due_date: str,
        status: str
    ) -> dict:
        """
        发送任务提醒

        Args:
            user_id: 用户ID
            task_title: 任务标题
            due_date: 截止日期
            status: 状态描述

        Returns:
            发送结果
        """
        content = f"""📋 **任务提醒**

**任务**: {task_title}
**截止**: {due_date}
**状态**: {status}

请及时处理！"""

        return await self.send_message(user_id, content, msg_type="markdown")

    async def send_meeting_notification(
        self,
        user_id: str,
        meeting_title: str,
        meeting_time: str,
        location: Optional[str] = None
    ) -> dict:
        """
        发送会议通知

        Args:
            user_id: 用户ID
            meeting_title: 会议主题
            meeting_time: 会议时间
            location: 会议地点

        Returns:
            发送结果
        """
        content = f"""📅 **会议通知**

**主题**: {meeting_title}
**时间**: {meeting_time}
"""
        if location:
            content += f"**地点**: {location}\n"

        content += "\n请准时参加！"

        return await self.send_message(user_id, content, msg_type="markdown")

    async def send_meeting_minutes(
        self,
        user_id: str,
        meeting_title: str,
        summary: str
    ) -> dict:
        """
        发送会议纪要

        Args:
            user_id: 用户ID
            meeting_title: 会议主题
            summary: 会议摘要

        Returns:
            发送结果
        """
        content = f"""📝 **会议纪要**

**会议**: {meeting_title}

**摘要**:
{summary}

详细内容请登录系统查看。"""

        return await self.send_message(user_id, content, msg_type="markdown")

    async def send_to_group(
        self,
        chat_id: str,
        content: str,
        msg_type: str = "text"
    ) -> dict:
        """
        发送消息到群聊

        Args:
            chat_id: 群聊ID
            content: 消息内容
            msg_type: 消息类型

        Returns:
            发送结果
        """
        token = await self._get_access_token()

        if msg_type == "text":
            data = {
                "chatid": chat_id,
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
        else:
            data = {
                "chatid": chat_id,
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/cgi-bin/appchat/send?access_token={token}",
                json=data
            )
            return response.json()

    async def send_to_external_user(
        self,
        external_userid: str,
        content: str,
        msg_type: str = "text"
    ) -> dict:
        """
        发送消息给外部联系人（普通微信用户）

        使用 /cgi-bin/externalcontact/message/send API

        Args:
            external_userid: 外部用户ID（wm 开头）
            content: 消息内容
            msg_type: 消息类型（text/markdown）

        Returns:
            发送结果
        """
        token = await self._get_access_token()
        sender = settings.WECHAT_EXTERNAL_SENDER
        if not sender:
            logger.error("未配置 WECHAT_EXTERNAL_SENDER，无法发送外部联系人消息")
            return {"errcode": -1, "errmsg": "未配置 WECHAT_EXTERNAL_SENDER"}

        if msg_type == "text":
            data = {
                "chat_type": "single",
                "external_userid": [external_userid],
                "sender": sender,
                "msg_type": "text",
                "text": {
                    "content": content
                }
            }
        elif msg_type == "markdown":
            # 外部联系人 API 不直接支持 markdown，降级为 text
            data = {
                "chat_type": "single",
                "external_userid": [external_userid],
                "sender": sender,
                "msg_type": "text",
                "text": {
                    "content": content
                }
            }
        else:
            raise ValueError(f"不支持的消息类型: {msg_type}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/cgi-bin/externalcontact/message/send?access_token={token}",
                json=data
            )
            return response.json()

    async def send_to_external_group(
        self,
        chat_id: str,
        content: str,
        msg_type: str = "text"
    ) -> dict:
        """
        发送消息到外部群（包含普通微信用户的群）

        使用 /cgi-bin/externalcontact/add_msg_template API
        注意：此 API 用于向客户群发送消息，需要配置「客户联系」权限

        Args:
            chat_id: 外部群聊ID（以 wr 开头）
            content: 消息内容
            msg_type: 消息类型（text/markdown）

        Returns:
            发送结果
        """
        token = await self._get_access_token()

        # 使用 add_msg_template API 发送消息到客户群
        # 注意：此 API 需要 external_userid 列表，而不是 chat_id
        # 对于外部群消息，我们使用 send_welcome_msg 或其他方式
        # 这里使用 add_msg_template，但需要调整参数格式

        # 外部群消息使用 text 格式（markdown 不支持）
        data = {
            "chat_type": "group",
            "external_userid": [chat_id],  # 使用 chat_id 作为外部联系人 ID
            "sender": settings.WECHAT_EXTERNAL_SENDER or "xiaoqi",
            "msg_type": "text",
            "text": {
                "content": content
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/cgi-bin/externalcontact/add_msg_template?access_token={token}",
                json=data
            )
            result = response.json()

            # 如果 add_msg_template 失败，尝试使用 send_welcome_msg
            if result.get("errcode") != 0:
                logger.warning(f"add_msg_template 失败: {result}，尝试其他方式")

                # 尝试使用 send_welcome_msg（需要配置欢迎语模板）
                # 这里暂时返回错误，需要进一步配置
                return result

            return result

    async def smart_send(
        self,
        member: "Member",
        content: str,
        msg_type: str = "text"
    ) -> dict:
        """
        智能发送：根据成员类型自动选择内部/外部 API

        优先使用 external_userid（普通微信用户），否则用 wechat_id（企业微信用户）

        Args:
            member: 成员对象
            content: 消息内容
            msg_type: 消息类型

        Returns:
            发送结果
        """
        if member.external_userid:
            return await self.send_to_external_user(member.external_userid, content, msg_type)
        elif member.wechat_id:
            return await self.send_message(member.wechat_id, content, msg_type)
        else:
            logger.warning(f"成员 {member.name} 无可用的微信标识，无法发送消息")
            return {"errcode": -1, "errmsg": "无可用的微信标识"}

    async def smart_send_to_group(
        self,
        chat_id: str,
        content: str,
        msg_type: str = "text"
    ) -> dict:
        """
        智能群发：根据 chat_id 前缀自动选择内部群/外部群 API

        外部群 chat_id 以 'wr' 开头，内部群使用 /cgi-bin/appchat/send

        Args:
            chat_id: 群聊ID
            content: 消息内容
            msg_type: 消息类型

        Returns:
            发送结果
        """
        if chat_id.startswith("wr"):
            return await self.send_to_external_group(chat_id, content, msg_type)
        else:
            return await self.send_to_group(chat_id, content, msg_type)

    async def reply_to_user(self, user_id: str, content: str, msg_type: str = "text") -> dict:
        """
        回复用户消息（别名，与 send_message 功能相同）

        Args:
            user_id: 用户ID
            content: 消息内容
            msg_type: 消息类型

        Returns:
            发送结果
        """
        return await self.send_message(user_id, content, msg_type)


# 全局实例
wechat_bot = WeChatBot()
