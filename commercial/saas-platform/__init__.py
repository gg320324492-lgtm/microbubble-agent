"""
商业化 SaaS 平台模块 (W72 Phase 8 起步)

4 脚本:
- tenant_manager: 多租户注册/隔离/路由
- usage_tracker: 按 tenant 统计用量
- billing_gateway: 计费网关 (mock, 预留接口)
- audit_export: 审计日志导出
"""

__version__ = "0.1.0-commercial-phase8"
__all__ = [
    "tenant_manager",
    "usage_tracker",
    "billing_gateway",
    "audit_export",
]
