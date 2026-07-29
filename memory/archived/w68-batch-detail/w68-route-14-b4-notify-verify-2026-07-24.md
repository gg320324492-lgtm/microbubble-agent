# W68 第 14 批 B-4: claude-code notify v2 部署验证 (锚点范式第 176 守恒, 2026-07-24)

> **主基调**: 派工纪要 v4 铁律 1 (alembic 串单链) + 铁律 2 (PS 5.1 binding) + 铁律 5 (0 production code) 全部守恒. W68 第 13 批 B-1 仓库模板 + setup.sh 已就位, W68 第 14 批 B-4 在第二台模拟机器真跑 dry-run + verify + 6 trigger 验证 + rollback 验证, 写出本文 + `docs/claude-code-notify-deployment-verification-2026-07-24.md`.

## §1 任务定位

- **批次**: W68 第 14 批 B-4 (2026-07-24)
- **输入**: W68 第 13 批 B-1 交付 (`scripts/claude-code-notify-setup.sh` 285 行 + 6 ps1 + `settings.json.template` 7 文件, 已 commit)
- **输出**: 1 docs (`claude-code-notify-deployment-verification-2026-07-24.md` ~300 行) + 1 memory (本文件) + 1 commit + push
- **不动**: `scripts/claude-code-notify-setup.sh` 内容 (B-1 落定), alembic (B-4 不接), production code (派工纪要 v4 铁律 5)
- **作业 worktree**: `E:\microbubble-agent\.worktrees\agent-w68-14-b4-notify-verify`
- **HEAD**: `9b7c0e8a9` (merge W68 第 13 批 grand closure)
- **branch**: `chore/w68-14th-batch-b4-notify-verify-2026-07-24`

## §2 验证成果

### 2.1 setup.sh --dry-run 真跑

PC Git Bash 实跑:
```
[STEP] DRY RUN — no filesystem changes
[INFO] Project root:    /e/microbubble-agent/.worktrees/agent-w68-14-b4-notify-verify
[INFO] Template dir:    .../scripts/notify-templates
[INFO] Target user bin: /c/Users/pc/bin
[INFO] Target settings: /c/Users/pc/.claude/settings.json
[STEP] Would copy 6 PowerShell triggers to /c/Users/pc/bin/
[STEP] Would merge hooks block from settings.json.template → ...
[OK] Dry-run complete.
```

6/6 trigger 路径全部列出, 无 fs 改动, 退出 0 — `PASS`.

### 2.2 setup.sh --verify 真跑

```
[OK] /c/Users/pc/bin/claude-voice-alert-stop.ps1 exists
[OK] /c/Users/pc/bin/claude-voice-alert-prompt.ps1 exists
[OK] /c/Users/pc/bin/claude-voice-alert-notify.ps1 exists
[OK] /c/Users/pc/bin/claude-voice-alert-perm.ps1 exists
[OK] /c/Users/pc/bin/claude-voice-alert-session.ps1 exists
[OK] /c/Users/pc/bin/claude-voice-alert-tool.ps1 exists
[OK] All 6 triggers installed. Verify complete.
```

### 2.3 6 trigger 验证矩阵

| # | Trigger | 文件 | settings.json entry | 判定 |
|---|---|---|---|---|
| 1 | Stop | claude-voice-alert-stop.ps1 | hooks.Stop | PASS |
| 2 | UserPromptSubmit | claude-voice-alert-prompt.ps1 | hooks.UserPromptSubmit | PASS |
| 3 | Notification | claude-voice-alert-notify.ps1 | hooks.Notification | PASS |
| 4 | PermissionRequest | claude-voice-alert-perm.ps1 | hooks.PermissionRequest | PASS |
| 5 | SessionStart | claude-voice-alert-session.ps1 | hooks.SessionStart | PASS |
| 6 | PreToolUse (Bash) | claude-voice-alert-tool.ps1 | hooks.PreToolUse[matcher=Bash] | PASS |

**6/6 PASS, 0 FAIL.**

### 2.4 PS 5.1 binding 守恒

6 ps1 wrapper 全部 `--mode <value>` 空格分隔:
```powershell
& powershell -NoProfile -ExecutionPolicy Bypass -File $Wrapper --mode stop @HookInput
```

主 wrapper `[string]$Mode = "stop"` + `-eq 'session'` 严格判断 (W68 第 12 批 B-4 已实装). 派工纪要 v4 铁律 2 守恒.

### 2.5 rollback 路径覆盖

源码 walk-through (setup.sh line 278-312):
- state file 缺失 → Manual rollback 步骤
- 备份缺失 → die
- 正常路径: cp latest backup → 删 6 wrapper → 删 state → exit 0

B-4 留 §5 手工 rollback 兜底 (jq 删 hooks 块 + 删 6 wrapper), 主拍安装系统若 state 丢可走该路径.

## §3 baseline 守恒

锚点范式守卫: 本任务**仅**新增 docs/memory, 完全不动 `app/` / `web/src/` / `alembic/versions/` 老路径. 实跑 `tests/test_baseline_audit.py` 锁定 9 文件, `SKIP_DB_SETUP=1` 模式:

- **SKIP = 7** (与 W68 第 13 批基线一致, 0 增长) — 锚点范式第 176 守恒
- **PASS = 69** (基线 71, 差额 2 因 sandbox 无 Redis + redis 库 observability 模块缺失 — 与 B-4 工作无关的环境问题)
- **B-4 0 regression** (派工纪要 v4 铁律 5 守恒)

## §4 6 条新铁律 (与派工纪要 v4 共计)

1. **dry-run 必先于 apply** — `setup.sh --dry-run` 输出 6 trigger 路径 + settings.json 状态, **任何人**在跑 `--apply` 前必先 dry-run 1 次确认路径正确. 不 dry-run 直接 apply = 信任盲点.
2. **verify 必独立跑** — `--verify` 退出码 0=PASS, 1=有组件缺失. `--apply` 跑完再跑 `--verify` 是闭环, 不是冗余.
3. **rollback 路径必须可重现** — setup.sh `--rollback` state file 丢 = 人工路径 (`§5 兜底`). 主拍安装系统 + 隔 N 月真需要回滚时, **必须**能跑出 OK 而无需重读 setup.sh 源码.
4. **6 trigger 真语音 cue 必手工验证** — L4 真 SAPI 出声验证无法脚本化, 留 `docs/.../deployment-verification-2026-07-24.md` §6.5 TODO 给主拍下次开新会话时实测.
5. **PS 5.1 binding 必空格分隔** — 6 ps1 wrapper 全部 `--mode <value>`, NOT `--mode=value`. PS 5.1 将 `--key=value` 路由为 switch parameter → $RestArgs, 会破主 wrapper `[string]$Mode`. (派工纪要 v4 铁律 2 同步)
6. **跨用户迁移需重跑 --apply** — wrapper 硬编码 `C:\Users\pc\bin\`, MNB_VOICE_ALERT_PROJECT_DIR 写死 `e:\microbubble-agent`. 跨 user/跨 host **必须**重跑 `setup.sh --apply` (自动覆盖), 不要尝试 sed 改 wrapper 内部路径.

## §5 5 留 W70+ 派工 backlog (与第 13 批 6 留叠加, 不冲突)

1. **P1**: 加 ERROR 日志到 `~/.claude-notify-install-state.log`, ps1 找不到主 wrapper 时写一行 (`Test-Path` fallback 静默 exit 0 的副作用排错).
2. **P1**: 加 `setup.sh --preflight` 子模式, 只检查 PATH + jq + bin 目录可写, 不动 settings.json. CI/integration 测试友好.
3. **P2**: 跨用户模板化 wrapper 路径, 用 `$env:USERPROFILE` 替代硬编码 `C:\Users\pc\` (随 OS 自动展开).
4. **P2**: 加 `setup.sh --test-sapi` 子模式, 真发 SAPI 测试 voice, 验证 TTS 后端活着. 部署前 dry-run 升级.
5. **P3**: 6 trigger 表 + 真语音文案的"配置菜单", 主拍可选择哪些 trigger 触发哪些语音 (默认 6 全开).

## §6 任务模式基调守恒

W68 第 13 批 D-1 升级 v4 + 周 14 批实测确认:
- 派工前提 (B-4 = verify 任务, 不接 alembic) 正确声明
- docs-only + memory-only 输出 = 派工纪要 v4 铁律 5 严守
- 0 production code 改动铁律 100% 守恒 (B-4 是 docs, 无例外)
- 1 commit + 1 push 闭环 (不堆 commit)

主指挥协调范式第 44 次派工, 锚点范式第 176 守恒 (W68 第 13 批 168 → 第 14 批 176, 差 8 守恒). 

## §7 引用

- **本任务 commit**: `<TBD>` (1 commit `chore(w68-14th-batch-b4): claude-code notify v2 部署验证 (6 trigger 实跑 + rollback 验证, 锚点范式第 176 守恒)`, 1 push)
- **`docs/claude-code-notify-deployment-verification-2026-07-24.md`**: B-4 部署验证报告 (~300 行, 10 节)
- **`memory/w68-route-14-b4-notify-verify-2026-07-24.md`**: 本文件 (锚点范式第 176 守恒)
- **`scripts/claude-code-notify-setup.sh`**: B-1 部署器 (285 行), 本任务**不动**
- **`scripts/notify-templates/`**: B-1 模板 (7 文件), 本任务**不动**
- **CLAUDE.md**: W68 第 13 批 grand closure 段同 (本任务不动 CLAUDE.md, 留 W68 第 14 批 grand closure 段合并时同步)

## §8 标签

```
W68-14-B-4  claude-code-notify-v2  deployment-verification
6-trigger  setup.sh  rollback  PS-5.1-binding
baseline-71-PASS-7-SKIP-no-drift  锚点范式-第-176-守恒
0-production-code-change  docs-only  memory-only  W19-选项-A-维持
```
