# W87 第 1 批 B-1 — GlitchTip + Sentry 接入

日期：2026-07-29  
基线：`1a3ebbea5`（W86 D-2 tip，锚点 325）  
范围：已批 0 production code 改动例外；仅错误监控基础设施，不改业务 service/API/model/view。

## 真实施与上游核验

- Docker Hub 当前官方仓库是 `glitchtip/glitchtip`，不是派工示例的 `glitchtip/glitchtip-server`。
- 2026-07-29 查询 Docker Hub tags，最新稳定 patch tag 为 `6.2.2`；manifest 可取，digest 为 `sha256:ef28cc4b92c8c9e427b8ddd55682d6aa155129ddf1c5db5f6bbbd09155fd3b6e`。
- 3 个 compose 均钉死 `glitchtip/glitchtip:6.2.2`，端口生产/dev/test 分别为 8000/8001/8002。
- `celery-sentry==0.4.0` 在 PyPI 无发行版，若照抄会让依赖安装硬失败；`sentry-sdk` 自带 `CeleryIntegration`，因此仅钉死 `sentry-sdk[fastapi]==2.13.0`。
- `@sentry/vue` v8 没有派工示例里的 `SentryErrorHandler` export；采用受支持的 `Sentry.init({ app, integrations: [browserTracingIntegration({ router })] })`，由 Vue integration 挂 error handler。

## 接入设计

### GlitchTip

- 复用现有 PostgreSQL 容器，但使用独立数据库 `glitchtip`，避免与 `microbubble` 表混用。
- 复用 Redis，使用 DB 1 隔离缓存/任务键。
- `SERVER_ROLE=all_in_one` 让单 GlitchTip 容器包含 Web 与 worker。
- 邮件通过 `EMAIL_ENABLED=False` 关闭；正式域名、TLS、secret 与 deploy-auto 集成留 W87-X-2。

### 后端

- `Settings.SENTRY_DSN: str | None = None`，默认关闭。
- 仅 `if settings.SENTRY_DSN` 时初始化 FastAPI + Celery integrations。
- `traces_sample_rate=0.1`、`send_default_pii=False`。
- `environment=settings.APP_ENV`；新增 `APP_VERSION=1.0.0` 用于 release `microbubble-agent@1.0.0`。

### 前端

- runtime deps 钉死 `@sentry/browser==8.55.2`、`@sentry/vue==8.55.2` 并更新 lockfile。
- 初始化硬门禁：`if (import.meta.env.VITE_SENTRY_DSN && !import.meta.env.DEV)`。
- `beforeSend` 再次拒绝 DEV，默认不发送 PII。
- `web/src/utils/sentry.js` 的 `reportError/reportMessage` 先检查 `window.__SENTRY_INITIALIZED__`；无 DSN 时调用也是 no-op。
- 暴露 `window.reportError` / `window.reportMessage`，便于 smoke test 与现有客户端路径调用。

### Service Worker

- SW 不直接 import Sentry。
- install hook 真正 catch 到异常时向所有 window client postMessage `SW_INSTALL_FAILED`（含 timestamp/version）。
- main.js 监听消息并调用 `reportMessage`；Sentry 未初始化时 no-op。
- 只在失败 catch 上报，不把每次 install 误报为失败。

## 装机摘要

1. 启动 db/redis。
2. 幂等创建独立 `glitchtip` database。
3. 设置随机 `GLITCHTIP_SECRET_KEY` 与真实 `GLITCHTIP_DOMAIN`。
4. `docker compose up -d glitchtip`。
5. 在 dashboard 创建项目；主指挥批准后才设置后端 `SENTRY_DSN` 与构建期 `VITE_SENTRY_DSN`。
6. 完整步骤见 `docs/sentry-setup.md`。

## 默认关闭与生产状态

本次只完成接入基础设施，**没有真接入生产**：

- 无 `SENTRY_DSN`：后端 `sentry_sdk.init` 不调用。
- 无 `VITE_SENTRY_DSN`：前端 Sentry 不初始化。
- DEV：即使误设前端 DSN，也不初始化且 `beforeSend` 返回 null。
- 未部署 GlitchTip、未创建生产项目、未注入生产 DSN；等待 W87-X-2 与主指挥决定。

## 派工 v6 §5 反馈 — 类 20.27

**Sentry 默认必须 off + env guard，不可静默上报。**

1. SDK 初始化必须由显式 DSN 守卫，默认配置为 `None`/空。
2. dev/local 必须硬拒绝发送，不能只依赖操作员“不要配 DSN”。
3. 客户端辅助上报函数在 SDK 未初始化时必须 no-op，不能隐式创建 client。
4. `send_default_pii=False` 是默认安全值；真实生产启用需主指挥单独拍板。
5. 基础设施接入不等于生产启用；文档、报告和状态必须据实区分。

## 验证与锚点

硬门禁：`SKIP_DB_SETUP=1 pytest tests/sentry/ -v`。另验证 compose config、Python import/off guard、前端 build。  
锚点预期：325 → 326，单 commit +1 守恒。
