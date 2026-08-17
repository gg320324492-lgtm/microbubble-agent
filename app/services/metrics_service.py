"""app/services/metrics_service.py — 业务指标抽象 (P2 留口)

# 2026-08-17 #Step13 业务 prometheus_client metrics (Plan v1 P2)
# 0 业务代码改动: 不引入 prometheus_client 依赖, 仅定义 no-op 接口

设计:
- 默认 no-op 实现: 所有指标函数返回 None, 0 副作用
- PROMETHEUS_ENABLED=true 时切换真实实现 (P2 留口)
- 业务代码调用 metrics_service.inc_chat_count(...) 即可
- 真接入时: requirements.txt +prometheus_client, 加 /metrics endpoint

当前接口 (12 个指标):
- chat_total / chat_duration_seconds (chat 调用计数 + 延迟)
- llm_tokens_total (LLM token 用量)
- llm_cost_total (估算成本, USD)
- cache_hits_total / cache_misses_total (RAG 缓存命中率)
- search_total / search_duration_seconds (search_knowledge 调用)
- web_search_total (web_search 调用)
- knowledge_ingest_total (知识入库计数)
- errors_total (500 异常)
- ws_connections (WebSocket 当前连接数, Gauge)

P2 启用 (主拍决策时):
1. requirements.txt +prometheus_client
2. app/main.py 加 /metrics endpoint (generate_latest)
3. app/services/metrics_service.py 切换真实实现 (prometheus_client.Counter 等)
4. Grafana provisioning 加 scrape config
"""
from typing import Optional

# 2026-08-17 #Step13 启用开关 (默认 False, P2 留口启动时改 True)
PROMETHEUS_ENABLED: bool = False  # 环境变量: PROMETHEUS_ENABLED=true 切真实实现


def _noop(*args, **kwargs):
    """0 副作用 no-op 函数. P2 留口启动时换 prometheus_client.Counter().inc()"""
    return None


# 业务代码调用接口 (始终是 12 个函数名, 实现可换)
inc_chat_total = _noop
observe_chat_duration = _noop
inc_llm_tokens_total = _noop
inc_llm_cost_total = _noop
inc_cache_hits_total = _noop
inc_cache_misses_total = _noop
inc_search_total = _noop
observe_search_duration = _noop
inc_web_search_total = _noop
inc_knowledge_ingest_total = _noop
inc_errors_total = _noop
set_ws_connections = _noop
inc_errors_total = _noop


def get_metrics() -> str:
    """返回 /metrics endpoint 内容. 默认空 (P2 启用时换 generate_latest)."""
    return ""  # noop
