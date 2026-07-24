"""KbIntakeAlertService — W68 第 10 批 B-3 健康监控告警 (2026-07-24)

设计要点:
- 失败率 > 20% 触发告警
- 通过 Redis pub/sub channel `kb_intake:alerts` 推送 (WeChat bot / 邮件 daemon 订阅)
- 防抖: 同一窗口内不重复告警 (Redis SET 标记 + 24h TTL)
- best-effort: 告警失败不阻塞 health_check task

铁律:
- 不引入新告警通道, 复用 Redis pub/sub 模式 (与其他 service 告警对齐)
- 告警内容含失败率 + 阈值 + 候选转人工数 (给运维快速判断严重度)
- 失败告警记录 logger.error(exc_info=True), 便于排查
"""
import json
import logging
from datetime import datetime

from app.core.redis import get_redis

logger = logging.getLogger("microbubble.kb_intake_alert")

# 告警防抖 TTL (24h, 避免每分钟告警)
ALERT_DEBOUNCE_TTL_SECONDS = 24 * 3600

# Redis key 前缀 (per metric 类型独立 debounce)
REDIS_DEBOUNCE_PREFIX = "kb_intake_alert:debounce:"

# Redis pub/sub channel (其他 service / WeChat bot 订阅)
REDIS_ALERT_CHANNEL = "kb_intake:alerts"


def _debounce_key(metric: str) -> str:
    """生成 debounce Redis key (per metric 类型)"""
    return f"{REDIS_DEBOUNCE_PREFIX}{metric}"


class KbIntakeAlertService:
    """KB 入库健康监控告警服务

    触发场景:
    1. 失败率 > 20% (auto_intake_rollback_service.get_failure_rate)
    2. 永久挂起转人工数 > N (可选, 留待后续)
    3. 24h 内无任何成功入库 (TODO)

    设计要点:
    - 防抖: 同一 metric 24h 内只告警一次 (Redis SET NX EX)
    - 通过 Redis pub/sub 推送, 不直接调 WeChat/邮件 API (解耦)
    - best-effort: 告警失败 logger.error 不抛
    """

    def __init__(self):
        # 不持有 db/redis 句柄, 每次 send 时按需获取 (避免 Celery 跨 loop 陷阱)
        pass

    async def send_alert_if_high_failure_rate(
        self,
        *,
        failure_rate_data: dict,
    ) -> bool:
        """失败率 > 阈值时触发告警 (带 24h 防抖)

        Args:
            failure_rate_data: AutoIntakeRollbackService.get_failure_rate 返回值

        Returns:
            True if 告警已发送 / False if 未达阈值或防抖中

        设计要点:
        - Redis pub/sub channel `kb_intake:alerts` 推送
        - 防抖 key: kb_intake_alert:debounce:failure_rate (24h TTL)
        - 告警内容含具体数据, 给运维排查用
        """
        if not failure_rate_data.get("should_alert"):
            logger.debug(
                f"kb_intake_alert: failure_rate={failure_rate_data.get('failure_rate', 0):.2%} "
                f"<= threshold={failure_rate_data.get('alert_threshold', 0.20):.2%}, skip"
            )
            return False

        failure_rate = failure_rate_data["failure_rate"]
        threshold = failure_rate_data["alert_threshold"]
        window_days = failure_rate_data["window_days"]
        rejected_count = failure_rate_data["rejected_count"]
        success_count = failure_rate_data["success_count"]
        pending_count = failure_rate_data["pending_review_count"]

        # 防抖: Redis SET NX EX 24h
        redis = await get_redis()
        debounce_key = _debounce_key("failure_rate")
        try:
            # 原子操作: 24h 内已告警过 → False
            sent = await redis.set(
                debounce_key,
                json.dumps(
                    {
                        "failure_rate": failure_rate,
                        "rejected_count": rejected_count,
                        "pending_review_count": pending_count,
                    }
                ),
                nx=True,
                ex=ALERT_DEBOUNCE_TTL_SECONDS,
            )
            if not sent:
                logger.info(
                    f"📢 [kb_intake_alert] debounced (24h TTL active): failure_rate={failure_rate:.2%}"
                )
                return False
        except Exception as e:
            # 防抖失败: 兜底不告警 (避免告警风暴), 仅 logger.error
            logger.error(
                f"❌ [kb_intake_alert] redis debounce failed: {e}", exc_info=True
            )
            return False

        # 实际告警: Redis pub/sub 推送 (WeChat bot / 邮件 daemon 订阅)
        title = "🚨 KB 自动入库失败率告警"
        body_lines = [
            f"**失败率**: {failure_rate:.2%} (阈值 {threshold:.2%})",
            f"**统计窗口**: {window_days} 天",
            f"**失败数**: {rejected_count}",
            f"**成功数**: {success_count}",
            f"**永久挂起转人工**: {pending_count}",
            "",
            "请检查:",
            "1. qa-bench 评分模型是否有回归",
            "2. save_to_kb.py 灰度配置",
            "3. 5 道防线是否过严",
            "4. Celery worker 是否正常运行",
        ]
        body = "\n".join(body_lines)

        return await self._publish_alert(title=title, body=body)

    async def _publish_alert(
        self,
        *,
        title: str,
        body: str,
    ) -> bool:
        """通过 Redis pub/sub 推送告警

        Args:
            title: 告警标题
            body: 告警正文 (Markdown 格式)

        Returns:
            True if 发送成功 / False if 失败 (best-effort)

        设计要点:
        - Redis pub/sub channel `kb_intake:alerts` 推送 JSON payload
        - 订阅方 (WeChat bot / 邮件 daemon / Slack) 各自决定渲染格式
        - 失败 logger.error 不抛 (告警不应该阻塞 health_check)
        """
        try:
            redis = await get_redis()
            payload = json.dumps(
                {
                    "title": title,
                    "body": body,
                    "severity": "high",
                    "source": "kb_intake_rollback",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                ensure_ascii=False,
            )
            # publish 返回订阅者数 (>=0), 不抛即视为成功
            subs = await redis.publish(REDIS_ALERT_CHANNEL, payload)
            logger.warning(
                f"📢 [kb_intake_alert] published to {REDIS_ALERT_CHANNEL!r} "
                f"(subscribers={subs}): {title!r}"
            )
            return True
        except Exception as e:
            logger.error(
                f"❌ [kb_intake_alert] publish failed: {e}", exc_info=True
            )
            return False