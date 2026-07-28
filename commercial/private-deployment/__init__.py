"""商业化私有化部署包 (W79 第 1 批 B-2, W78 A-2 §5.4 阶段 4 实战).

私有化部署 = W78 C-1 SaaS 平台部署的 **offline-first 单租户变体**:
- 镜像层: Dockerfile.private (继承 Dockerfile.commercial, 加 offline-first + 公网隐藏)
- SaaS 平台层: private_config.py 单租户变体 (5 脚本降级为 single-tenant 模式)
- 计费服务层: billing_degrade.py (离线环境无法访问支付网关 → mock 降级)
- 前端层: 公网隐藏 (BillingView / PlanSelector 私有化部署下不暴露公网)

License 校验 (W73 B-5 license_service.py + W78 C-1 license_check 复用):
- 离线 7 天宽限 (OFFLINE_GRACE_DAYS=7)
- 过期触发自动降级 read-only 模式
- 服务端校验 + 客户端 fallback

0 production code 改动铁律例外 2 已批 — 本包**全部新增文件**, 不动 app/ web/ alembic/ 老链路.
"""

__all__ = [
    "PRIVATE_DEPLOYMENT_VERSION",
    "OFFLINE_GRACE_DAYS",
]

PRIVATE_DEPLOYMENT_VERSION = "1.0.0-private"
OFFLINE_GRACE_DAYS = 7
