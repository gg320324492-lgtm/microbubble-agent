#!/usr/bin/env bash
# 商业化镜像入口
# 启动前先做 License 服务端校验 (离线 7 天宽限)
# 然后启动 uvicorn

set -euo pipefail

echo "[commercial] MicroBubble Commercial Phase 8 starting..."

# 1. License 服务端校验
python /app/license-check.py || {
    echo "[commercial] FATAL: license check failed, refusing to start"
    exit 1
}

# 2. 多租户路由初始化
python -c "from commercial.saas_platform.tenant_manager import init_routes; init_routes()" || {
    echo "[commercial] WARN: tenant route init failed, fallback to single-tenant"
}

# 3. 启动 uvicorn
exec "$@"
