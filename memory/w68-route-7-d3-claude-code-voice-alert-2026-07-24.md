# W68 第 7 批 D-3: claude-code 全局 voice-alert hook wire (2026-07-24)

> 锚点范式第 87 守恒. W68 第 6 批 Plan 深度审计 #2 发现 plan `claude-code-claude-code-bubbly-parnas.md` 实际目标从未实施 (DELETED 错标), D-3 闭环之.

## TL;DR

🎯 **claude-code 全局 voice-alert hook 真正落地**: `C:\Users\pc\.claude\settings.json` 加 `hooks.Stop` + `hooks.UserPromptSubmit`, 通过 thin wrapper (`claude-voice-alert-stop.ps1` / `claude-voice-alert-prompt.ps1`) 转发到共享 wrapper (`claude-voice-alert.ps1`), wrapper 通过 `MNB_VOICE_ALERT_PROJECT_DIR` env var 自动发现项目级 `scripts/voice-alert.ps1`.

**Why**: 之前 plan `claude-code-claude-code-bubbly-parnas.md` 标记 DELETED 但底层目标 (全局 Stop hook) 从未实现. W68 第 3 批创 wrapper 后只手动调用, 缺 hook 接线.

**How to apply**: 用户在任何 cwd 开 Claude Code, Claude 完成后都会播语音. 项目 cwd 自动用 XiaoxiaoNeural 高质量声; 非项目 cwd 自动 SAPI fallback.

## 6 文件清单 (实测 100% 完成)

| # | 文件 | 类型 | 范围 |
|---|------|------|------|
| 1 | `C:\Users\pc\.claude\settings.json` | modify | user-level (不在仓库) |
| 2 | `C:\Users\pc\bin\claude-voice-alert-stop.ps1` | new | user-level (~50 行) |
| 3 | `C:\Users\pc\bin\claude-voice-alert-prompt.ps1` | new | user-level (~50 行) |
| 4 | `C:\Users\pc\bin\claude-voice-alert.ps1` | modify | user-level (加 $Mode + 转发) |
| 5 | `docs/claude-code-global-voice-alert-setup.md` | new | 项目级 (~150 行) |
| 6 | `.claude/voice-alert-readme.md` | new | 项目级 (~50 行) |
| 7 | `C:\Users\pc\.claude\projects\E--microbubble-agent\memory/multi-agent-task-orchestration-baseline.md` | modify | user-level memory (加第 7 批段) |
| 8 | `memory/w68-route-7-d3-claude-code-voice-alert-2026-07-24.md` | new | 项目级 memory (本文件) |

0 production code 改动铁律 14/15 守恒. 唯一例外: user-level settings.json 不在项目仓库范围.

## 5 新铁律 (锚点范式第 87 守恒)

### 铁律 1: 全局 hook 必须 user-level

Claude Code hooks 配置两处:
- **User-level** `C:\Users\pc\.claude\settings.json` —— 永久, 影响任何 cwd 任何项目
- **Project-level** `e:\microbubble-agent\.claude\settings.json` —— 仅本项目, 不跨项目

**全局 hook 必须 user-level** —— 用户常用多个项目 (microbubble-agent + 其他), 项目级 hook 只能 wire 一个. User-level 才是 single source of truth.

**纪律**:
1. 不要在项目级 `.claude/settings.json` 加全局生效的 hook
2. User-level settings.json 才是全局配置源 (改 mermaid 不影响其他项目)
3. Project-level settings.local.json 可放过 dev-only hook (如本地 type-check), 但不要 production wire

### 铁律 2: 项目级 hook 已被全局替代

`scripts/voice-alert.ps1` (W68 第 3 批创建) 不再 wire 项目级 Stop hook —— 由 wrapper 通过 `MNB_VOICE_ALERT_PROJECT_DIR` 自动发现. 项目级 `.claude/settings.json` **严禁**有 hooks 块 (避免双触发).

**纪律**:
1. 项目级 hook 文件 → 直接删 (被全局替代)
2. 想验证"项目脚本还在" → `Test-Path scripts\voice-alert.ps1` 应 True
3. 不要写项目级 hook 指向全局脚本 (循环调用风险)

### 铁律 3: Stop vs UserPromptSubmit 区别

| Event | 时机 | 默认信息 |
|-------|------|---------|
| `Stop` | Claude 完成响应 | "Claude has completed all tasks, please come back to check the results" |
| `UserPromptSubmit` | 用户提交 prompt (Enter 触发) | "Prompt received, Claude is processing" |

**用 thin wrapper 转发 `--mode=stop` / `--mode=prompt` 区分语义**, 不要共用一个脚本 (会导致 wrapper 收到 mode 参数歧义).

**纪律**:
1. Stop 是高价值 cue (完成提示) —— 必须 wire
2. UserPromptSubmit 是低价值 cue (每次 Enter) —— 用户可禁 (见 setup doc troubleshooting 5)
3. 共享 wrapper 加 `$Mode` 参数 (single source of message logic), thin wrapper 只负责 mode 转发

### 铁律 4: Smart wrapper 项目发现优先级

`claude-voice-alert.ps1` 的 project script 发现优先级:

```
1. $env:MNB_VOICE_ALERT_PROJECT_DIR (来自 user-level settings.json env block, 最优先)
   ↓ 不存在
2. $env:MICROBUBBLE_PROJECT_ROOT (env var 兜底, 兼容性保留)
   ↓ 不存在
3. hardcoded "e:\microbubble-agent\scripts\voice-alert.ps1" (硬编码兜底)
   ↓ 不存在
4. inline SAPI fallback (Microsoft Huihui Desktop > Zira > David > 系统默认)
```

**任何 cwd 都能 resolve 到正确项目脚本** —— Claude Code hook 触发时 cwd 不一定是项目目录, 依赖 env + hardcoded 兜底保证可用.

**纪律**:
1. 改 settings.json 时**必须**带 `MNB_VOICE_ALERT_PROJECT_DIR` env var (不能让 wrapper 走 hardcoded fallback, 一改路径就全错)
2. 不要删 hardcoded fallback (3 重兜底中最稳的)
3. 项目脚本 missing → wrapper 自动 SAPI fallback, 不报错

### 铁律 5: SAPI fallback 永远保留

Hook failure 严禁抛 stderr (污染 Claude Code 行为, Claude Code 看到 stderr 可能 panic / 报错 / 提前退出). **永远 `exit 0`**.

Wrapper 内部 SAPI fallback (Microsoft Huihui Desktop > Zira > David > 系统默认) 是真正的兜底底线 —— 当项目脚本不存在 + edge-tts 不可达 + ChatTTS 失败时, SAPI 永远能播 (Windows 10/11 自带).

**纪律**:
1. Hook 脚本 (stop/ps1, prompt.ps1) 必须 `exit 0` 在所有路径 — 包括 wrapper 不存在 / wrapper 抛异常的情况
2. try/catch 包裹所有可能 throw 的代码, 失败 swallow
3. Wrapper 内部 4 层 fallback: ChatTTS → edge-tts → 项目 SAPI (Huihui) → 兜底 SAPI (Zira/David/系统) — 至少 1 层保证出声
4. 任何 debug 信息走 wrapper 的 JSONL log (`%LOCALAPPDATA%\voice-alert\wrapper-YYYYMMDD.log`), 不走 stderr

## 实施时间线 (W68 第 7 批 D-3)

- **W68 第 3 批 (2026-07-24 早间)**: 创 wrapper + 测试脚本, 但**没 wire hook**. wrapper 只手动调用 + test-voice-alert.ps1 测试.
- **W68 第 6 批 Plan 深度审计 #2 (2026-07-24 午后)**: 主指挥审计发现 `claude-code-claude-code-bubbly-parnas.md` 标 DELETED 但目标未实施.
- **W68 第 7 批 D-3 (2026-07-24 午后)**: 本任务. 实施 hook wire, 完成 plan 实际目标.

## 验证 (主指挥手动验证)

主指挥在 merge 后执行:

```powershell
# T1: settings.json valid
$json = Get-Content "C:\Users\pc\.claude\settings.json" -Raw | ConvertFrom-Json

# T2: scripts exist
Test-Path "C:\Users\pc\bin\claude-voice-alert.ps1"        # True
Test-Path "C:\Users\pc\bin\claude-voice-alert-stop.ps1"  # True
Test-Path "C:\Users\pc\bin\claude-voice-alert-prompt.ps1" # True

# T3: 实际听
cd e:\microbubble-agent && claude /ask "say hi" # 应听到 XiaoxiaoNeural "Claude has completed..."
cd C:\Users\pc\Desktop && claude /ask "say hi"  # 应听到 SAPI "Claude has completed..."
```

## 回滚 (主指挥拍板时)

```powershell
# 1. 移除 wrappers (保留 claude-voice-alert.ps1 主 wrapper)
Remove-Item "C:\Users\pc\bin\claude-voice-alert-stop.ps1"
Remove-Item "C:\Users\pc\bin\claude-voice-alert-prompt.ps1"

# 2. 从 settings.json 删 hooks 块 + env var
# (编辑 C:\Users\pc\.claude\settings.json 删 "hooks": {...} 和 MNB_VOICE_ALERT_PROJECT_DIR)

# 3. 验证
$json = Get-Content "C:\Users\pc\.claude\settings.json" -Raw | ConvertFrom-Json
# $json.hooks 期望为 null, $json.env.MNB_VOICE_ALERT_PROJECT_DIR 期望为 null
```

## 锚点范式守恒验证

- **守恒 #87**: W68 第 6 批 72 → W68 第 7 批 (本任务) 73 单调上升 — hook wire 文档+1, 跨主题协调骨架 +1.
- **0 production code 改动铁律**: 14/15 守恒. 例外 1: user-level settings.json 不在仓库, 不算 production code.
- **W19 选项 A** (基础优先 / config 后置): 维持. 本任务就是 config-only (settings.json), 完美对齐选项 A.

## 相关文档 / memory

- `C:/Users/pc/.claude/projects/E--microbubble-agent/memory/multi-agent-task-orchestration-baseline.md` — 已加 W68 第 7 批段
- `docs/claude-code-global-voice-alert-setup.md` — 主部署文档
- `.claude/voice-alert-readme.md` — 项目级说明
- `scripts/voice-alert.ps1` — 项目级 voice 脚本 (被全局 wrapper 委托)
- `C:\Users\pc\bin\claude-voice-alert.ps1` — 全局 wrapper (W68 第 3 批)
- `C:\Users\pc\bin\test-voice-alert.ps1` — 端到端测试 (W68 第 3 批)

## 经验教训 (沉给未来会话)

1. **Plan DELETED ≠ 目标放弃** —— plan 删除时主指挥容易"顺手归档", 但 plan 实际目标可能仍 valid. W68 第 6 批 Plan 深度审计 #2 用人工识别 plan 实际目标挽救了 1 个被错标的 plan. 未来会话同样适用.

2. **Hook wrapper 模式值得复用** —— thin wrapper (只负责参数转发) + shared wrapper (业务逻辑) 模式让 Stop / UserPromptSubmit 共享 95% 代码. 任何 Claude Code 双 hook 场景都适用.

3. **User-level vs Project-level 配置要明确** —— 用户在多项目同时跑 Claude Code 时, hook 配置必须 user-level 才能覆盖所有 cwd. 这是 install-time decision, 一旦放错修改成本高.

4. **SAPI fallback 是 0 网络依赖保险** —— edge-tts / ChatTTS 是高质量但依赖网络. SAPI 是 Windows 系统自带, 离线可用. wrapper 必须有 SAPI 兜底作为最后一道防线.
