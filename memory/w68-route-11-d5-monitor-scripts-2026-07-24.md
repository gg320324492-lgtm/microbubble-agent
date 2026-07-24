# W68 第 11 批 D-5: 实时监测脚本 3 件套 (2026-07-24)

> 锚点范式第 146 守恒 — VAPID 持久化 + qa-bench Phase 2 + 部署健康 3 个监测脚本 + 1 手册 + 本 memory。
> 0 production code 改动铁律维持 (仅 `scripts/` + `docs/` + `memory/`)。

## 背景

主指挥 SSH 部署必用 + D-3 调研需要:
- **VAPID 持久化** (C-3 部署) — Web Push VAPID 密钥必须持久化到磁盘, 否则每次重启生成新 key → 所有订阅失效, 公钥变更是私钥泄露信号
- **qa-bench D6 Phase 2 真跑** (C-2 SOP) — 真跑后需校验报告 7 维完整 + 90% gate
- **部署监控** — CI/CD + 服务探活 (6 endpoint + alembic 单头 + baseline 守恒)

W68 累计 170+ commits + Drive v2 PR8-12 + Mobile PWA push (VAPID) + qa-bench D6, 部署面变宽, 需要一键探活脚本收口。

## 交付物 (5 文件)

| 文件 | 行数 | 职责 |
|------|------|------|
| `scripts/monitor_vapid_persistence.sh` | ~200 | VAPID 目录 + 私钥权限 + 公钥不变性 (基线对比) |
| `scripts/monitor_qa_bench_phase2.sh` | ~250 | phase2 报告存在 + JSON + 7 维 + 90% gate + 新鲜度 |
| `scripts/monitor_deployment_health.sh` | ~270 | 6 endpoint + 5xx 比率 + alembic heads + baseline |
| `docs/main-command-scripts-2026-07-24.md` | ~180 | 必做时机 + SSH 命令汇总表 + 恢复路径 + cron |
| `memory/w68-route-11-d5-monitor-scripts-2026-07-24.md` | 本文件 | 沉淀 + 5 新铁律 |

## 三脚本统一设计

- **退出码**: `0` 正常 / `1` 有报警 (需人工) / `2` 配置错误
- **DRY_RUN=1**: 只打印检查项, 不真跑 (安全预览)
- **日志**: append 到 `logs/<name>-$(date +%Y%m%d).log`, 每行带 `[时间戳]`
- **报警时**: 末尾打印**编号恢复路径**, 照做即可
- **兼容性**: Linux (云 server) + Windows Git Bash (本地 PC) — `stat -c`/`stat -f` 双回退 + tput 颜色降级 + python 执行探测 (绕开 Windows Store 假 stub)

## 验证

- `bash -n` 三脚本全部语法正确
- `DRY_RUN=1` 三脚本全部正常打印检查项
- qa-bench 脚本: 好报告 (overall 0.93 + 7 维全) → 6 PASS 0 ALERT 退出 0; 坏报告 (0.82 + 缺 5 维 + 10 题) → 4 ALERT 退出 1
- python 探测: Windows Store `python3` stub (退出码 49) 被 `python3 -c "pass"` 探测过滤, 回退真 python

## 关键实现细节

1. **VAPID 公钥基线对比**: 首次运行写 `logs/.vapid-public-key.baseline`, 后续对比。公钥优先取 endpoint (`/api/v1/push/vapid-public-key`), 回退磁盘文件。文件公钥 vs endpoint 公钥不一致也报警 (后端加载了不同 key)。
2. **qa-bench JSON 解析**: python heredoc 输出 `status\tkey\tmsg` 制表符分隔, shell `while IFS=$'\t' read` 逐行渲染。7 维容器兼容 `dimensions`/`scores`/`dimension_scores`/`radar`/顶层。overall_score 兼容 `overall_score`/`overall`/`total_score`/`score`, 缺失回退 7 维均值; `>1` 视百分制归一化。
3. **部署 5xx 比率**: 采样 N 次 `/health`, 用万分比整数运算 (`fail*10000/total`) 避免 bash 无浮点。
4. **alembic heads**: `docker exec -e SKIP_DB_SETUP=1 <app> alembic heads` → `grep -c '(head)'`, != 1 报警 (W68 第 3 批多头事故复用)。
5. **baseline**: 默认 `CHECK_BASELINE=0` (云 server 无前端 devDeps), 本地 PC 设 1 跑 `npm run lint` 校验 71 PASS + 7 SKIP。

## 5 新铁律 (监测脚本纪律)

1. **监测必自动 (DRY_RUN + cron)** — 监测脚本必须支持 `DRY_RUN=1` 安全预览 + 可挂 cron 定期化。人工记忆跑监测 = 迟早忘, 自动化才守得住。手动一次性检查不算监测。
2. **监测必日志 (带时间戳 + 按日归档)** — 每次运行 append 到 `logs/<name>-$(date +%Y%m%d).log`, 每行 `[YYYY-MM-DD HH:MM:SS]` 前缀。无日志的监测无法回溯"何时开始异常", 排障失去时间线。
3. **监测必报警 (退出码 + 明确 ALERT)** — 报警必须体现在退出码 (`1`) + 显式 `✗ ALERT` 行, 便于 `|| curl webhook` 接告警。只打印 PASS 不区分退出码 = 绿条骗人, CI/cron 无法感知失败。
4. **监测必恢复路径 (报警末尾打印编号步骤)** — 每个报警后脚本末尾打印**编号恢复步骤** (缺目录→mkdir / 多头→串单链 / gate 失败→定位失败题)。只报"有问题"不给"怎么修" = 主指挥半夜收到报警无从下手。
5. **监测必定期 (明确时机表)** — docs 必须列**必做时机表** (部署后 1h/24h / 每天 / 每周 / 季度 backup 前)。不写时机 = 脚本躺在 repo 里没人跑, 部署后才想起从没监测过。

## 跨脚本兼容性教训

- **Windows Store python3 假 stub (退出码 49)** — `command -v python3` 命中 `WindowsApps/python3` 但它是打开商店的假程序, 执行报 49。必须 `python3 -c "pass"` 探测真能执行才用, 否则 heredoc 静默不输出 (本次 debug 中真实踩到)。
- **stat 跨平台** — Linux `stat -c '%a'` / macOS/BSD `stat -f '%Lp'` / Git Bash 可能无 → 三级回退 + 无法读取时 WARN 跳过而非 FAIL。
- **bash 无浮点** — 5xx 比率用整数万分比 (`*10000/total`) 运算, 拆 `pct.frac` 显示。

---

*W68 第 11 批 D-5 · 锚点范式第 146 守恒 · 0 production code 改动铁律维持 · 主指挥 SSH 部署必用*
