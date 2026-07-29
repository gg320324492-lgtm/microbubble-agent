# GlitchTip + Sentry 接入与装机

> W87-B-1 只接入基础设施；当前默认关闭，尚未连接生产 GlitchTip。W87-X-2 再处理 `deploy-auto.sh`、域名/TLS 与生产密钥注入。

## 1. 版本与架构

- GlitchTip：`glitchtip/glitchtip:6.2.2`（Docker Hub patch 级钉死；2026-07-29 核验 manifest digest `sha256:ef28cc4b92c8c9e427b8ddd55682d6aa155129ddf1c5db5f6bbbd09155fd3b6e`）。
- 后端：`sentry-sdk[fastapi]==2.13.0`，SDK 内置 `FastApiIntegration` 和 `CeleryIntegration`。
- 前端：`@sentry/browser==8.55.2`、`@sentry/vue==8.55.2`。
- GlitchTip 用 `SERVER_ROLE=all_in_one`，单容器内运行 Web 与任务 worker；复用现有 PostgreSQL 与 Redis（独立 Redis DB 1）。

派工示例中的 `glitchtip/glitchtip-server:v4.1.0` 不是当前 Docker Hub 仓库；当前官方仓库是 `glitchtip/glitchtip`。`celery-sentry==0.4.0` 在 PyPI 也不存在，因此不写入不可安装依赖；Celery 接入由 `sentry-sdk.integrations.celery.CeleryIntegration` 提供。

## 2. 首次装机

GlitchTip 使用独立数据库 `glitchtip`，不能与 `microbubble` 表混用。首次启动前执行一次：

```bash
docker compose up -d db redis
docker compose exec db psql -U postgres -d postgres -tc \
  "SELECT 1 FROM pg_database WHERE datname = 'glitchtip'" | grep -q 1 || \
  docker compose exec db psql -U postgres -d postgres -c "CREATE DATABASE glitchtip"
```

生产密钥必须替换默认值：

```bash
openssl rand -hex 32
# 写入部署环境（不要提交真实值）
GLITCHTIP_SECRET_KEY=<上一步输出>
GLITCHTIP_DOMAIN=https://glitchtip.example.com
```

启动服务：

```bash
docker compose up -d glitchtip
docker compose logs -f glitchtip
```

开发栈与测试栈分别使用：

```bash
docker compose -f docker-compose.dev.yml up -d glitchtip   # http://localhost:8001
docker compose -f docker-compose.test.yml up -d glitchtip  # http://localhost:8002
```

生产端口是 `8000`。正式公网部署应由反向代理提供 HTTPS；本任务不改 nginx。

## 3. 创建项目并配置 DSN

1. 打开 GlitchTip，创建管理员、组织和项目。
2. 复制项目 DSN。
3. 后端运行环境设置：

```bash
SENTRY_DSN=https://<key>@<glitchtip-host>/<project-id>
```

4. 前端构建环境设置（Vite 只在构建时读取 `VITE_*`）：

```bash
VITE_SENTRY_DSN=https://<key>@<glitchtip-host>/<project-id>
```

5. 重新构建前端并重启 Python 进程：

```bash
cd web && npm run build
cd ..
docker compose restart app celery-worker
```

`SENTRY_DSN` 与 `VITE_SENTRY_DSN` 均不设置时完全不上报。前端即使误在开发环境设置 DSN，`!import.meta.env.DEV` 初始化守卫和 `beforeSend` 仍会拦截上报。

## 4. 验证

在非生产测试项目中故意触发一次错误：

```python
import sentry_sdk

sentry_sdk.capture_message("microbubble backend sentry smoke test")
sentry_sdk.flush(timeout=5)
```

浏览器控制台（仅已用 DSN 构建且非 dev）：

```javascript
window.reportMessage('microbubble frontend sentry smoke test', 'info')
window.reportError(new Error('microbubble frontend sentry smoke test'), { source: 'manual-smoke' })
```

然后在 GlitchTip 项目 Issues 中确认事件、`environment`、`release` 正确。完成后删除或 resolve 测试事件。

SW install hook 捕获失败时不能直接 import SDK，因此发送 `SW_INSTALL_FAILED` postMessage；客户端监听后调用 `reportMessage`。未初始化 Sentry 时该函数立即返回，不产生网络请求。

## 5. 回滚与后续

关闭监控只需删除两个 DSN 并重启/重建：

```bash
unset SENTRY_DSN
unset VITE_SENTRY_DSN
```

停止 GlitchTip：

```bash
docker compose stop glitchtip
```

W87-X-2 待办：

1. 把数据库幂等创建、GlitchTip 启停和健康检查接入 `deploy-auto.sh`。
2. 配置真实域名、TLS、备份和 secret manager。
3. 主指挥审核后才注入生产 DSN；此前保持默认 off。
