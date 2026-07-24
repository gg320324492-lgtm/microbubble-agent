# 主指挥监测脚本使用手册 (W68 第 11 批 D-5, 2026-07-24)

> 锚点范式第 146 守恒 — 3 个实时监测脚本 + SSH 命令汇总, 供主指挥部署后一键探活。
> 纪律: 3 脚本均 0 production code 改动 (仅 `scripts/` + `logs/` 输出), 兼容 Linux (云 server) + Windows Git Bash (本地 PC)。

## 1. 脚本总览

| 脚本 | 监测对象 | 报警项 | 日志 |
|------|---------|--------|------|
| `scripts/monitor_vapid_persistence.sh` | Web Push VAPID 密钥持久化 (C-3 部署) | 缺目录 / 缺密钥 / 公钥变更 | `logs/vapid-monitor-YYYYMMDD.log` |
| `scripts/monitor_qa_bench_phase2.sh` | qa-bench D6 Phase 2 报告 (C-2 SOP) | gate 失败 / 缺报告 / 7 维缺 / 陈旧 | `logs/qa-bench-phase2-monitor-YYYYMMDD.log` |
| `scripts/monitor_deployment_health.sh` | 6 endpoint + alembic + baseline | 5xx / 5xx 比率>1% / alembic 多头 / baseline drift | `logs/deployment-health-YYYYMMDD.log` |

三脚本统一约定:
- **退出码**: `0` = 全部正常 / `1` = 有报警 (需人工介入) / `2` = 配置错误
- **DRY_RUN=1**: 只打印将执行的检查, 不真跑 (安全预览)
- **日志**: 每次运行 append 到 `logs/<name>-$(date +%Y%m%d).log`, 带时间戳
- **报警时**: 末尾打印**恢复路径** (编号步骤), 直接照做

---

## 2. 必做时机 (何时跑哪个)

### 2.1 VAPID 持久化监测

| 时机 | 原因 |
|------|------|
| **部署后 24h 内一次** | 确认新 deploy 未重生成 key (否则所有订阅失效) |
| **每周 1 次例行** | 及早发现公钥漂移 / 目录被清 |
| **季度 backup (`scp vapid_*.pem`) 前一次** | 确认 backup 的是当前有效 key |

> ⚠️ 公钥**变更**是私钥泄露/被覆盖的强信号 — 收到此报警必须先确认无恶意再更新基线。

### 2.2 qa-bench Phase 2 监测

| 时机 | 原因 |
|------|------|
| **Phase 2 真跑后立即** | 校验报告 7 维完整 + 90% gate 达标 (防"绿条骗人") |
| **每周 1 次 smoke** | 确认 gate 未回归 (模型/数据退化早发现) |

### 2.3 部署健康监测

| 时机 | 原因 |
|------|------|
| **部署后 1h 内一次** | 探活 6 endpoint + alembic 单头 + baseline 守恒 |
| **每天 1 次例行** | 常态化探活, 早发现 5xx / 服务挂 |
| **任何异常报告时立即** | 用户报"进不去"/"报错"时第一手诊断 |

> ⚠️ **alembic 多头 (heads != 1)** 是 W68 第 3 批真实事故 (CLAUDE.md 2026-07-24 铁律), 会直接阻塞 `alembic upgrade head`。部署前必查。

---

## 3. 主指挥 SSH 命令汇总表

> 前提: 已 SSH 到云 server 或在本地 PC Git Bash。`cd` 到仓库根 (`/e/microbubble-agent` 或部署路径)。

### 3.1 一键三连 (部署后标准流程)

```bash
# 部署后 1h: 先探活部署健康
BASE_URL=https://agent.mnb-lab.cn TOKEN=eyJ... bash scripts/monitor_deployment_health.sh

# 部署后 24h: VAPID 持久化
VAPID_DIR=/data/push BASE_URL=https://agent.mnb-lab.cn bash scripts/monitor_vapid_persistence.sh

# Phase 2 真跑后: qa-bench 报告
REPORT=qa-bench/reports/phase2_latest.json bash scripts/monitor_qa_bench_phase2.sh
```

### 3.2 逐脚本命令

| 目的 | 命令 |
|------|------|
| VAPID 默认检查 | `bash scripts/monitor_vapid_persistence.sh` |
| VAPID 指定目录 + 域名 | `VAPID_DIR=/data/push BASE_URL=https://agent.mnb-lab.cn bash scripts/monitor_vapid_persistence.sh` |
| VAPID 预览 (不真跑) | `DRY_RUN=1 bash scripts/monitor_vapid_persistence.sh` |
| Phase 2 默认检查 | `bash scripts/monitor_qa_bench_phase2.sh` |
| Phase 2 指定报告 + gate | `REPORT=qa-bench/reports/phase2_20260724.json GATE_THRESHOLD=0.90 bash scripts/monitor_qa_bench_phase2.sh` |
| Phase 2 放宽陈旧阈值 | `MAX_AGE_HOURS=336 bash scripts/monitor_qa_bench_phase2.sh` |
| 部署健康默认 (公开 endpoint) | `bash scripts/monitor_deployment_health.sh` |
| 部署健康带 token (鉴权期望 200) | `TOKEN=eyJ... bash scripts/monitor_deployment_health.sh` |
| 部署健康 + baseline (本地 PC) | `CHECK_BASELINE=1 bash scripts/monitor_deployment_health.sh` |
| 部署健康跳过 alembic (无 docker) | `CHECK_ALEMBIC=0 bash scripts/monitor_deployment_health.sh` |

### 3.3 环境变量速查

**monitor_vapid_persistence.sh**: `VAPID_DIR`(/data/push) · `VAPID_PRIVATE`(vapid_private.pem) · `VAPID_PUBLIC`(vapid_public.pem) · `BASE_URL`(https://localhost) · `BASELINE_FILE`(logs/.vapid-public-key.baseline) · `DRY_RUN`(0)

**monitor_qa_bench_phase2.sh**: `REPORT`(qa-bench/reports/phase2_latest.json) · `GATE_THRESHOLD`(0.90) · `MIN_QUESTIONS`(30) · `MAX_AGE_HOURS`(168) · `DIMENSIONS`(7 维) · `DRY_RUN`(0)

**monitor_deployment_health.sh**: `BASE_URL`(https://localhost) · `TOKEN`(空) · `SAMPLE_COUNT`(20) · `RATE_THRESHOLD`(1) · `CHECK_ALEMBIC`(1) · `CHECK_BASELINE`(0) · `BASELINE_PASS`(71) · `BASELINE_SKIP`(7) · `APP_CONTAINER`(microbubble-agent-app-1) · `DRY_RUN`(0)

---

## 4. 6 个探活 endpoint (monitor_deployment_health.sh §1)

| 路径 | 鉴权 | 无 token 期望 | 带 token 期望 |
|------|------|--------------|--------------|
| `/health` | 公开 | 200 | 200 |
| `/api/v1/push/vapid-public-key` | 公开 | 200 | 200 |
| `/api/v1/drive/comments` | 鉴权 | 401/403 | 200 |
| `/api/v1/auth/me` | 鉴权 | 401/403 | 200 |
| `/api/v1/chat/sessions` | 鉴权 | 401/403 | 200 |
| `/api/v1/knowledge` | 鉴权 | 401/403 | 200 |

任一返 **5xx** → ALERT (服务端错误)。无 token 时鉴权 endpoint 返 200 → WARN (可能鉴权漏放行)。

---

## 5. 报警 → 恢复路径 (脚本末尾也会打印)

### VAPID
1. **缺目录**: `mkdir -p /data/push && docker compose restart app` (重启会重新生成并写盘)
2. **缺密钥**: 确认 volume 挂载 `docker inspect microbubble-agent-app-1 | grep /data/push`
3. **公钥变更**: 若私钥泄露 → 立即轮换 + 通知用户重新订阅; 若合法重生成 → 更新基线 `echo '<新公钥>' > logs/.vapid-public-key.baseline`

### qa-bench Phase 2
1. **缺报告/陈旧**: 重跑 Phase 2 真跑生成新报告
2. **7 维缺失**: 检查评分 pipeline 是否所有维度都产出 (LLM-as-judge prompt)
3. **gate 失败**: 定位失败题目 (`results[].score < 阈值`), 分析数据 bug vs 模型退化

### 部署健康
1. **endpoint 5xx**: `docker logs microbubble-agent-app-1 --tail 100` 定位 → `docker compose restart app`
2. **5xx 比率高**: 查 CPU/内存/DB 连接池 `docker stats`
3. **alembic 多头**: `docker exec microbubble-agent-app-1 alembic heads` → 改 `down_revision` 串单链 → 清 `__pycache__` → `upgrade head` (CLAUDE.md 2026-07-24 alembic 铁律)
4. **baseline drift**: `cd web && npm run lint` 看新增违规, 修复或更新基线

---

## 6. 定期化建议 (cron)

主指挥可加 crontab (云 server) 让监测自动化:

```cron
# 每天 08:00 部署健康
0 8 * * *  cd /path/to/microbubble-agent && BASE_URL=https://agent.mnb-lab.cn bash scripts/monitor_deployment_health.sh >> logs/cron-deploy.log 2>&1
# 每周一 09:00 VAPID + qa-bench smoke
0 9 * * 1  cd /path/to/microbubble-agent && bash scripts/monitor_vapid_persistence.sh; bash scripts/monitor_qa_bench_phase2.sh
```

> 报警 (退出码 1) 可接入告警渠道 (企业微信 webhook / 邮件): `bash monitor_xxx.sh || curl -X POST <webhook> -d '监测报警'`

---

*W68 第 11 批 D-5 · 锚点范式第 146 守恒 · 0 production code 改动铁律维持*
