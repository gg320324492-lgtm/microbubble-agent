# W68 第 12 批 B-4: claude-code 通知体系 v2 (锚点范式第 151 守恒)

> **任务**: 升级 W68 第 7 批 D-3 已建 voice-alert hook (2 trigger) 到完整通知体系 (6 trigger). 0 production code 改动铁律.
> **锚点范式**: 第 151 守恒.
> **完成日期**: 2026-07-24.

## 任务范围

### 输入 (W68 第 7 批 D-3 后)
- 用户级 `C:/Users/pc/.claude/settings.json`: 仅 2 hook (Stop + UserPromptSubmit)
- 用户级 `C:/Users/pc/bin/claude-voice-alert-{stop,prompt}.ps1`: 2 trigger wrapper 存在
- 用户级 `C:/Users/pc/bin/claude-voice-alert.ps1`: master wrapper, 支持 mode=stop / mode=prompt
- 调研发现: 完整通知体系 6 trigger, 已实现 2, 缺 4

### 输出 (本批 B-4)
- 5 个 hook 块 (Stop/UserPromptSubmit/Notification/PermissionRequest/SessionStart/PreToolUse)
- 6 个 wrapper 脚本 (4 新 + 2 改 模式 `--mode=value` → `--mode value`)
- master wrapper 加 4 个 mode 分支

### 文件清单
1. `C:/Users/pc/.claude/settings.json` — 修改, 加 4 hook 块
2. `C:/Users/pc/bin/claude-voice-alert-{notify,perm,session,tool}.ps1` — 4 新建
3. `C:/Users/pc/bin/claude-voice-alert-{stop,prompt}.ps1` — 2 修改 (`--mode=stop` → `--mode stop`)
4. `C:/Users/pc/bin/claude-voice-alert.ps1` — 1 修改 (扩 4 mode 链 + 注释 `--name=value` 不能用)
5. `e:/microbubble-agent/docs/claude-code-notify-system-v2-2026-07-24.md` — 1 新建 (~270 行)

总: 7 个用户级文件改动 + 1 个 doc (仓库内) + 1 个 memory (本文件)

## 5 新铁律

### 铁律 1: Claude Code 通知体系完整 6 trigger

```
Stop                     (答完一个 turn)
UserPromptSubmit         (用户提交 prompt)  
Notification             (后台事件, e.g. 长任务完成)
PermissionRequest        (Claude 等授权, BLOCKS claude)
SessionStart             (Session 启动 /resume /clear 边界)
PreToolUse               (工具调用前; matcher 限定 Bash 控噪音)
```

**纪律**:
- 任何对 claude-code 体系的扩展必须覆盖这 6 trigger 中相关者, 不能漏 (特别是 PermissionRequest — 阻塞性, 缺则用户错失关键等待)
- 新 trigger 加时: (1) 新建 trigger ps1 (2) wrapper 加 mode 分支 (3) settings.json 加 hook 块 (4) 写 doc + memory
- 关闭单个 trigger: 注释 settings.json 里对应 block (不删文件, 留 audit trail)
- PreToolUse 必须 matcher 限定 (如 "Bash"), 防止 14 tool 全触发淹没其他 hook

### 铁律 2: 用户级配置铁律

- 涉及 claude-code harness 的配置**只能在用户级** (`C:/Users/pc/.claude/`) 和项目级 (`E:/microbubble-agent/.claude/`)
- **不能写到**项目代码仓 (`e:/microbubble-agent/`) 的代码路径下 (会污染 commit)
- 用户级 hooks / 项目级 hooks (`.claude/settings.local.json`) 的区别:
  - 用户级: 全 claude code 实例生效 (跨项目)
  - 项目级: 仅该 cwd 下的项目生效
  - 对全局通知 hook, 应放用户级 (避免每次新 clone 都要重配)

### 铁律 3: PowerShell 参数 binding 铁律 (`--mode value` vs `--mode=value`)

**关键发现**: PS 5.1+ 对 `[string]$Mode` 参数, **空格分隔** (`--mode value`) 正确绑定到 `$Mode`, **等号形式** (`--mode=value`) 把整个 token 塞进 `$Mode` 的字面值 (字面 `"--mode=session"`).

```powershell
# ✓ 正确: $Mode = "session", $RestArgs = []
powershell -File wrapper.ps1 --mode session

# ✗ 错误: $Mode = "--mode=session", $RestArgs = []
# PS 5.1+ reserves `=value` syntax for [switch] parameters
powershell -File wrapper.ps1 --mode=session
```

**测试验证**:
```powershell
[CmdletBinding()] param([string]$Mode, [Parameter(ValueFromRemainingArguments=$true)]$Rest)
# --mode=session → Mode:[--mode=session] RestArgs:[--mode=session]
# --mode session → Mode:[session]        RestArgs:[]
```

**纪律**:
- 所有 claude-code hook 调 wrapper 必须用 `--mode <X>` 空格分隔
- D-3 wrapper 老代码用 `--mode=stop` 也"巧合"工作的原因是: project script 拒绝该 token, wrapper fall through to SAPI fallback, SAPI fallback 默认消息也是 "task done" — 与 stop 应该播的一样. 但 mode 字段 log 中始终显示 "default" (W68 第 12 批 B-4 发现).
- 修法:**所有 6 trigger ps1 一律 `--mode <X>` 空格分隔**, 不要试图用 `=value` 然后 hack fixup (兼容性陷阱)

### 铁律 4: SAPI 兜底铁律

任何 hook / 通知系统的设计都应**最后兜底到 100% 可用的本地 TTS**:
- Win: `Add-Type -AssemblyName System.Speech` + `SpeechSynthesizer` (Microsoft Huihui Desktop 中文女声 / Zira 英文女声)
- Mac: `say` 命令
- Linux: `espeak` / `festival`

**纪律**:
- 项目脚本 (edge-tts / ChatTTS) 可能 down (网络/容器问题), 必须有 SAPI 兜底, 否则体验差
- SAPI fallback 时也要让用户知道是兜底, wrapper log 应标记 `engine=SAPI` 与高保真路径 (edge-tts) 区分
- SAPI 兜底完成时间约 7s (含延迟), 而 high-quality 路径 2s, 日志应记 `voice=Microsoft Huihui Desktop` vs `voice=zh-CN-XiaoxiaoNeural`

### 铁律 5: 跨项目 cwd 铁律

Hooks 不知道当前 cwd 是哪个项目. Wrapper 应**通过 env var 发现**项目脚本而非 hardcoded 路径:

```powershell
# ✓ 通过 env var (set in user-level settings.json env block)
$envVoiceRoot = $env:MNB_VOICE_ALERT_PROJECT_DIR
$candidate = Join-Path $envVoiceRoot "scripts\voice-alert.ps1"

# ✗ Hardcoded 路径 (仅在 e:/microbubble-agent 生效)
$candidate = "e:\microbubble-agent\scripts\voice-alert.ps1"
```

**纪律**:
- Wrapper 必须支持三层 fallback: env > 用户硬编码 > 内置默认
- env var 名应有项目前缀 (`MNB_*` = MicroBubble), 避免与其他工具冲突
- Wrapper 始终 `exit 0` — hook 报错绝不能污染 claude code 行为

## 完成度

- [x] settings.json 加 4 hook 块 (Notification / PermissionRequest / SessionStart / PreToolUse)
- [x] 4 新 trigger ps1 (notify/perm/session/tool)
- [x] wrapper 扩 4 mode 分支 (notify/perm/session/tool)
- [x] 6 模式单元测试全过 (wrapper log 验证 mode 计数正确)
- [x] docs/claude-code-notify-system-v2-2026-07-24.md
- [x] memory/w68-route-12-b4-claude-notify-v2-2026-07-24.md (本文件)
- [x] 0 production code 改动铁律 — 6/6 (仅用户级 + docs + memory)

## 验证

单元测试结果 (2026-07-24 测试):
```
=== stop ===    powershell exit 0; wrapper log mode:stop
=== prompt ===  powershell exit 0; wrapper log mode:prompt
=== notify ===  powershell exit 0; wrapper log mode:notify
=== perm ===    powershell exit 0; wrapper log mode:perm
=== session === powershell exit 0; wrapper log mode:session
=== tool ===    powershell exit 0; wrapper log mode:tool

# SAPI fallback 实际播音:
stop    → "Claude has completed all tasks, please come back to check the results"
prompt  → "Prompt received, Claude is processing"
notify  → "Claude has a background notification, please check the terminal"
perm    → "Claude is asking for permission, please approve or deny now"
session → "Claude Code session is ready"
tool    → "Running a bash command"
```

## 关联

- D-3 调研: [memory/w68-route-7-d3-claude-code-voice-alert-2026-07-24.md](w68-route-7-d3-claude-code-voice-alert-2026-07-24.md) (锚点范式第 24 守恒)
- D-2 (W68 第 9 批): 6 类文档同步规范 (本任务产出 1 doc + 1 memory 即此规范)
- Docs: [docs/claude-code-notify-system-v2-2026-07-24.md](../docs/claude-code-notify-system-v2-2026-07-24.md)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
