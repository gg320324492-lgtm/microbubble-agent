# Plan v2 #3 监控调研 (P2 留口)

**调研时间**: 2026-08-17
**结论**: 监控基础设施 (glitchtip + langfuse + Grafana) 已就绪, 业务面板 0 启用

---

## 现状 (2026-08-17 实测)

### 监控组件
- `glitchtip` 容器跑通 (200 health), DSN 未配 (Step 9 调研)
- `langfuse` 容器跑通, 客户端 init (Step 10 调研)
- `pg-exporter` 暴露 9187, 无 scrape config (Plan v1 Step 13)
- `Grafana` 自动 provisioning (Plan v1 Step 13)
- `metrics_service` 12 noop 接口 (Plan v1 Step 13 P2 留口)

### 业务面板缺口
- 0 prometheus_client 业务 metrics (chat/driver/search 计数)
- /metrics endpoint 0 启用 (404)
- Grafana provisioning 已就绪, 但 scrape config 缺
- 业务 KPI dashboard (chat 数 / drive 上传数 / LLM token / cache 命中率) 0 启用

### 0 业务代码改动完成
- ✅ Plan v2 #3 监控调研文档化
- ✅ 4 个组件基础设施已就绪 (glitchtip + langfuse + pg-exporter + Grafana)
- ✅ 0 业务监控启用

---

## 启动锚点 (主拍决策时启动)

### 监控启动四件套
1. **glitchtip DSN 配置** (Plan v1 Step 9 P2 启用)
   - env: SENTRY_DSN=http://127.0.0.2:8000/0
   - app 容器自动 init (类 20.27 守恒)
2. **langfuse 真 trace** (Plan v1 Step 12 P2 启用)
   - agentic_loop._synthesize_stream 外包 @observe
   - 1 行装饰, 0 业务代码改动
3. **prometheus 业务 metrics** (Plan v1 Step 13 P2 启用)
   - env: PROMETHEUS_ENABLED=true
   - 自动激活 12 个 metrics + /metrics endpoint
4. **Grafana scrape config** (Plan v1 Step 13 配套)
   - 加 prometheus.yml scrape job (pg-exporter + app /metrics)
   - Grafana 自动加载

### 启动顺序 (主拍决策时)
- 1 天配置 env + 1 周 Grafana dashboard 调优
- 0 业务代码改动 (所有改动都是配置层)
- 风险: 0 (默认 noop, 主拍决策开启)

### 启动条件 (主拍决策时):
- 4 启动件 + 派工 brief §13 真查
- 主拍书面批准

---

## 锚点范式累计

- d805f4f10 MEMORY 段 28
- 3a125b85f CLAUDE.md 更新
- 累计 26 commit, 0 业务代码改动

---

## 主拍决策单 (主拍填)

| 启动件 | 状态 | 启动 |
|------|------|------|
| 1. glitchtip DSN | 基础设施就绪 | [ ] |
| 2. langfuse 真 trace | 基础设施就绪 | [ ] |
| 3. prometheus 业务 metrics | 基础设施就绪 | [ ] |
| 4. Grafana scrape config | provisioning 就绪 | [ ] |

**4 启动件严禁擅自启动**, 等主拍书面批准.
