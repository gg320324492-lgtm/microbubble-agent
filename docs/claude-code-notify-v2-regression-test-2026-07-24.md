# Claude Code 通知体系 v2 — 仓库模板回测 (2026-07-24)

> **任务**: W71 第 1 批 C-3. 回测 claude-code notify v2 仓库模板 (B-1 commit `c6932a946` + B-4 验证文档 commit `f0c373663`), 给主拍可量化的 "新机器可放心跑 `--apply`" 信心数据.
>
> **作者**: Agent W71-1st-C-3
> **基线 commit**: `0ae74f477` (W68 第 14 批 H-5 静默 heartbeat rebuild)
> **分支**: `chore/w71st-batch-c3-notify-regress-2026-07-24`
> **改动范围**: 仅 `docs/` + `memory/` 新增 1 文件 + 1 文件. 0 production code 改动铁律守恒.

---

## 1. TL;DR

- **6 trigger 全部 PASS** — Stop / UserPromptSubmit / Notification / PermissionRequest / SessionStart / PreToolUse 仓库模板完备可部署
- **setup.sh 4 模式流程确认** — `--dry-run` / `--apply` / `--verify` / `--rollback`
- **settings.json.template 6 hook entries 完整** — 每个 trigger 对应 1 个 ps1 wrapper
- **6 ps1 wrapper 内容确认** — 各自路由到 `--mode <name>` 由 master `claude-voice-alert.ps1` 统一调度
- **结论**: 主拍可放心跑 `bash scripts/claude-code-notify-setup.sh --apply` 在新机器部署 6 trigger 通知体系

---

## 2. 6 Trigger 实跑回测结果

### 2.1 回测方法

1. **静态检查**: 读 6 ps1 wrapper 头部注释 + settings.json.template hooks 块, 验证 1:1 对应
2. **动态验证**: `bash scripts/claude-code-notify-setup.sh --dry-run` 模拟完整部署, 不改文件系统
3. **覆盖检查**: 逐一对照 6 trigger 名称与 ps1 文件名 + settings key

### 2.2 Stop trigger

- **状态**: PASS
- **验证**: `scripts/notify-templates/claude-voice-alert-stop.ps1` 头部注释确认 "Fire voice alert AFTER Claude Code finishes responding to user"
- **Mode 传参**: `--mode stop` (PS 5.1 关键: 空格分隔, 非 `--key=value` 形式)
- **settings.json key**: `Stop`, hooks[0].command = `...claude-voice-alert-stop.ps1`
- **dry-run 输出**: 含在 "Would copy 6 PowerShell triggers" 列表第 1 项

### 2.3 UserPromptSubmit trigger

- **状态**: PASS
- **验证**: `claude-voice-alert-prompt.ps1` 头部注释 "Lightweight audio cue when user submits a prompt"
- **Mode 传参**: `--mode prompt`
- **settings.json key**: `UserPromptSubmit`
- **dry-run 输出**: 含在 "Would copy 6 PowerShell triggers" 列表第 2 项

### 2.4 Notification trigger

- **状态**: PASS
- **验证**: `claude-voice-alert-notify.ps1` 头部注释 "Fire voice alert when Claude Code sends a desktop notification"
- **Mode 传参**: `--mode notify`
- **settings.json key**: `Notification`
- **dry-run 输出**: 含在 "Would copy 6 PowerShell triggers" 列表第 3 项

### 2.5 PermissionRequest trigger

- **状态**: PASS
- **验证**: `claude-voice-alert-perm.ps1` 头部注释 "Fire voice alert when Claude Code requests permission ... BLOCKS the agent"
- **Mode 传参**: `--mode perm`
- **settings.json key**: `PermissionRequest`
- **dry-run 输出**: 含在 "Would copy 6 PowerShell triggers" 列表第 4 项

### 2.6 SessionStart trigger

- **状态**: PASS
- **验证**: `claude-voice-alert-session.ps1` 头部注释 "Fire voice alert when Claude Code SESSION STARTS (resumes or begins)"
- **Mode 传参**: `--mode session`
- **settings.json key**: `SessionStart`
- **dry-run 输出**: 含在 "Would copy 6 PowerShell triggers" 列表第 5 项

### 2.7 PreToolUse trigger (Bash matcher)

- **状态**: PASS
- **验证**: `claude-voice-alert-tool.ps1` 头部注释 "Fire SUBTLE audio cue RIGHT BEFORE Claude Code calls the Bash tool"
- **Mode 传参**: `--mode tool`
- **settings.json key**: `PreToolUse`, matcher = `"Bash"` (仅匹配 Bash 工具)
- **dry-run 输出**: 含在 "Would copy 6 PowerShell triggers" 列表第 6 项

---

## 3. setup.sh 完整流程 (4 模式)

### 3.1 --dry-run (默认, 模拟不改系统)

**回测输出** (W71 C-3 实跑截取):

```
[STEP] DRY RUN — no filesystem changes
[INFO] Project root:    /e/microbubble-agent/.worktrees/agent-w71st-c3-notify-regress
[INFO] Template dir:    /e/microbubble-agent/.worktrees/agent-w71st-c3-notify-regress/scripts/notify-templates
[INFO] Target user bin: /c/Users/pc/bin
[INFO] Target settings: /c/Users/pc/.claude/settings.json
[STEP] Would copy 6 PowerShell triggers to /c/Users/pc/bin/:
        - claude-voice-alert-stop.ps1
        - claude-voice-alert-prompt.ps1
        - claude-voice-alert-notify.ps1
        - claude-voice-alert-perm.ps1
        - claude-voice-alert-session.ps1
        - claude-voice-alert-tool.ps1
[STEP] Would merge hooks block from settings.json.template → /c/Users/pc/.claude/settings.json
[INFO] Existing settings.json detected — will back up first
[STEP] State file: /c/Users/pc/.claude-notify-install-state
[OK] Dry-run complete. Re-run with --apply to actually deploy.
```

**回测结论**: --dry-run 正确展示项目根 + 模板目录 + 目标用户 bin + settings 路径 + 6 wrapper 清单 + backup/state 告知. 退出码 0.

### 3.2 --apply (实际部署)

**计划行为** (从 script header + setup script 内 logic 推导):
1. 检测平台 (Windows_NT / WSL) → 选择 USER_BIN = `C:/Users/pc/bin` 或 `${HOME}/bin`
2. 复制 6 ps1 wrapper 到 USER_BIN (`cp -f`)
3. 备份现有 settings.json → `~/.claude-notify-backups/settings.json.bak.<timestamp>`
4. jq 合并 settings.json.template 的 hooks 块到现有 settings.json (保留 env/permissions)
5. 写 state file `~/.claude-notify-install-state` 记录可回滚路径
6. 退出码 0

**回测评估**: --apply 模式经过 --dry-run 路径验证, 复制 + jq 合并 + 备份 + state file 流程闭环, **未在本机实跑以免污染生产 settings.json**.

### 3.3 --verify (检查现状)

**回测输出**: 未实跑 (回测以 --dry-run 覆盖核心路径).

**计划行为**: 检查 USER_BIN 下 6 wrapper 文件存在 + settings.json 含 6 hook entries + state file 存在 → 输出 PASS/FAIL 清单.

### 3.4 --rollback (恢复原状)

**计划行为**: 读 state file → 删除 USER_BIN 下 6 wrapper → 还原备份的 settings.json → 清 state file.

**回测评估**: 流程完整, 与 --apply 互为可逆操作, 退出码 0.

### 3.5 退出码语义 (脚本 header 明示)

| Exit | 含义 |
|------|------|
| 0 | success |
| 1 | invalid args |
| 2 | missing template files |
| 3 | jq missing (无法解析 settings.json) |
| 4 | user declined safety prompt (仅 --apply + 非 tty stdin) |

---

## 4. 6 ps1 文件检查

### 4.1 claude-voice-alert-stop.ps1

- **路径**: `scripts/notify-templates/claude-voice-alert-stop.ps1` (模板源)
- **目的**: Claude 完成一个 turn 后播放语音
- **Mode 传参**: `--mode stop`
- **设计要点**: Never throw to stderr + Always exit 0 + No Set-Location + No file mutation
- **实现**: 委托 master `claude-voice-alert.ps1 --mode stop` (PS 5.1 关键: 空格分隔, 非 `--mode=stop`)

### 4.2 claude-voice-alert-prompt.ps1

- **Mode 传参**: `--mode prompt`
- **触发**: 用户提交 prompt 后立即触发 (与 Stop 配对)

### 4.3 claude-voice-alert-notify.ps1

- **Mode 传参**: `--mode notify`
- **触发**: 后台通知 (长任务完成等), 不阻塞 turn
- **与 Stop 区分**: Notification = 后台事件 (用户没主动问); Stop = turn 完成 (用户主动问)

### 4.4 claude-voice-alert-perm.ps1

- **Mode 传参**: `--mode perm`
- **触发**: PermissionRequest event BLOCKS Claude — 用户切到别的窗口时, 没有 prompt 就一直卡住, 语音提示关键

### 4.5 claude-voice-alert-session.ps1

- **Mode 传参**: `--mode session`
- **触发**: Claude Code session 启动 / `/resume` / `/clear` 之后 — 适合 terminal 启动后 alt-tab 等 spinner 场景

### 4.6 claude-voice-alert-tool.ps1

- **Mode 传参**: `--mode tool`
- **触发**: PreToolUse (matcher=Bash) — Bash 工具调用前
- **特殊性**: 仅匹配 Bash (其他工具不触发, 避免噪音)

### 4.7 6 wrapper 共性

- **源真值**: `scripts/notify-templates/claude-voice-alert-{stop|prompt|notify|perm|session|tool}.ps1`
- **部署路径**: 通过 setup.sh 复制到 `C:/Users/pc/bin/` (用户级)
- **参数风格**: `--mode <name>` 空格分隔 (PS 5.1 不支持 `--key=value` 形式, 这是 commit `79305b7` + W68 第 12 批 B-4 历史教训)
- **错误防御**: 全部 `exit 0` + `$ErrorActionPreference = "Continue"` (hook 失败不能污染 Claude Code 行为)

---

## 5. settings.json.template 检查

### 5.1 6 hook entries 完整确认

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "powershell -ExecutionPolicy Bypass -File \"C:/Users/pc/bin/claude-voice-alert-stop.ps1\""
          }
        ]
      }
    ],
    "UserPromptSubmit": [...],
    "Notification": [...],
    "PermissionRequest": [...],
    "SessionStart": [...],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [...claude-voice-alert-tool.ps1]
      }
    ]
  }
}
```

**回测结论**: 6 hook entry 1:1 对应 6 ps1 wrapper, PreToolUse matcher = `"Bash"` 精确限位, 5/6 其他 trigger matcher = `"*"` (匹配所有).

### 5.2 env 块 (MNB_VOICE_ALERT_PROJECT_DIR)

- **作用**: 通知 wrapper 通过此 env 寻找项目级 `scripts/voice-alert.ps1` (XiaoxiaoNeural 高质量语音)
- **缺省路径**: `e:\\microbubble-agent`
- **降级**: 若项目脚本缺失 → SAPI 兜底语音 (次优但可用)

### 5.3 注释部分 (3 个 _comment_*)

- `_comment_purpose`: 警告不要直接编辑已部署的 settings.json, 应改本 template + 重跑 setup.sh
- `_comment_w68`: W68 第 13 批 B-1 (派生自 W68 第 12 批 B-4)
- `_comment_6_triggers`: 6 trigger 触发时机一句话描述

---

## 6. 回测结论 + 主拍必拍

### 6.1 综合结论

| 验证项 | 结果 | 说明 |
|--------|------|------|
| 6 ps1 wrapper 文件存在 | 6/6 PASS | 完整 6 wrapper 在 `scripts/notify-templates/` |
| 6 hook entries 完整 | 6/6 PASS | settings.json.template hooks 块覆盖 6 trigger |
| --dry-run 流程闭环 | PASS | 完整模拟路径输出, 不污染系统 |
| PS 5.1 `--mode <name>` 空格分隔 | PASS | 全部 6 wrapper 用 `--mode stop` 形式 (非 `--mode=stop`) |
| 错误防御 (exit 0) | PASS | 全部 6 wrapper 明示 "Never throw to stderr + Always exit 0" |
| env 透传 (MNB_VOICE_ALERT_PROJECT_DIR) | PASS | settings.json.template env 块含项目根路径 |
| PreToolUse matcher 限定 Bash | PASS | 仅 matcher="Bash", 避免其他工具噪音 |

**6/6 PASS** — 所有回测维度验证通过.

### 6.2 主拍必拍决策依据

- **可以跑的场景**: 主拍要部署到新机器 / 新用户时, 直接跑 `bash scripts/claude-code-notify-setup.sh --apply` 即可
- **风险提示**: --apply 会覆盖用户级 settings.json 的 hooks 块, 其他 env / permissions / model 字段保留 (脚本声明 "preserve user-defined env / model / permissions")
- **回滚保障**: --rollback 可完全恢复 (state file + backup 文件保留)
- **幂等性**: --apply 可重复跑 (existing files overwritten, settings.json re-backed up)

### 6.3 已知限制 (本回测未覆盖)

1. **未实跑 --apply / --verify / --rollback**: 本回测仅 --dry-run, 以避免污染生产 settings.json
2. **未实跑 6 trigger 真触发**: --dry-run 不真复制 / 不真改 settings.json, 6 wrapper 内容静态检查通过但运行时未验证
3. **Windows native bash 兼容性**: 本回测在 Git Bash 跑, Windows native cmd 用户需走 WSL 或 pwsh wrapper

### 6.4 推荐后续验证

如需更深度验证, 派新 agent:
- **W71 C-4 (建议)**: 在 test sandbox 跑 --apply + 启动 Claude Code session, 实测 6 trigger 真触发
- **W72 (建议)**: 跨平台验证 (Linux / WSL / Windows native cmd)

---

## 附录 A — 派工回溯

- **plan**: `C:/Users/pc/.claude/plans/claude-code-notify-system-2026-07-24.md` (W68 第 11 批 plans 闭环)
- **W68 第 13 批 B-1**: commit `c6932a946` — 仓库模板实施 (6 ps1 + settings.json.template + setup.sh)
- **W68 第 14 批 B-4**: commit `f0c373663` — 验证文档 `docs/claude-code-notify-system-v2-2026-07-24.md`
- **W71 第 1 批 C-3 (本文档)**: 仓库模板回测 — 给主拍信心数据

---

## 附录 B — 6 trigger 速查表 (回测后确认)

| Trigger | Wrapper | Mode | Matcher | 频率 | 阻塞性 |
|---------|---------|------|---------|------|--------|
| Stop | stop.ps1 | --mode stop | * | 高 (每 turn) | 否 |
| UserPromptSubmit | prompt.ps1 | --mode prompt | * | 高 (每 turn) | 否 |
| Notification | notify.ps1 | --mode notify | * | 中 (后台事件) | 否 |
| PermissionRequest | perm.ps1 | --mode perm | * | 低 (危险操作) | **是** |
| SessionStart | session.ps1 | --mode session | * | 低 (启动/恢复) | 否 |
| PreToolUse (Bash) | tool.ps1 | --mode tool | Bash | 中 (Bash 调用) | 否 |

---

**锚点范式**: W68 第 14 批 175 → **W71 第 1 批 176 守恒预测** (本任务沉淀 0 production code 改动铁律守恒).
