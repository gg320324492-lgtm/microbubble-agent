# Claude Code 通知体系 v2 — 6 Trigger 全覆盖 (2026-07-24)

> **任务**: W68 第 12 批 B-4. 升级 W68 第 7 批 D-3 已建 voice-alert hook (Stop + UserPromptSubmit 2 trigger) 到完整通知体系 (6 trigger). 0 production code 改动铁律, 仅用户级配置 + scripts + docs + memory.

**作者**: Agent W68-12th-B-4
**基线 commit**: 7b6f0305e (W68 第 10 批 A-3 merge 基线)
**分支**: `chore/w68-12th-batch-b4-claude-notify-v2-2026-07-24`
**改动范围**: 仅 `C:/Users/pc/.claude/` + `C:/Users/pc/bin/`. `E:/microbubble-agent/` 主仓库仅 + 1 doc + 1 memory file.

---

## 1. 6 Hooks 详解

### 1.1 Hook 列表

| Hook | Trigger 时机 | Wrapper 脚本 | Mode | SAPI 兜底消息 |
|------|-------------|-------------|------|--------------|
| **Stop** | Claude 答完一个 turn 后 (用户被动观察) | `claude-voice-alert-stop.ps1` | `--mode stop` | "Claude has completed all tasks, please come back to check the results" |
| **UserPromptSubmit** | 用户提交 prompt 后 (每个 turn) | `claude-voice-alert-prompt.ps1` | `--mode prompt` | "Prompt received, Claude is processing" |
| **Notification** | 后台通知 (长任务完成等) | `claude-voice-alert-notify.ps1` | `--mode notify` | "Claude has a background notification, please check the terminal" |
| **PermissionRequest** | Claude 等待授权 (阻塞) | `claude-voice-alert-perm.ps1` | `--mode perm` | "Claude is asking for permission, please approve or deny now" |
| **SessionStart** | Session 启动 / `/resume` / `/clear` | `claude-voice-alert-session.ps1` | `--mode session` | "Claude Code session is ready" |
| **PreToolUse (Bash)** | Bash 工具调用前 | `claude-voice-alert-tool.ps1` | `--mode tool` | "Running a bash command" |

### 1.2 触发场景示例

**Stop** (W68 第 7 批 D-3 已建):
- 场景: 用户提交 prompt → Claude 答完 → 用户在另一窗口想知道答完了
- 时机: 每 turn 结束
- 频率: 高 (每 turn 1 次)

**UserPromptSubmit** (W68 第 7 批 D-3 已建):
- 场景: 用户按 Enter 提交 prompt → 切到另一窗口 → 想知道 prompt 是否送达
- 时机: 每个 turn 开始
- 频率: 高

**Notification** (本批新增):
- 场景: 长时间后台任务完成, 或 system idle 通知
- 时机: 系统级事件, 不阻塞 turn
- 频率: 中 (取决于系统行为)
- 区分: 与 Stop 不同, Notification 是后台事件 (用户没主动问); Stop 是 turn 完成 (用户主动问)

**PermissionRequest** (本批新增):
- 场景: Claude 准备跑 `rm -rf` / `git push --force` / 写文件, 等用户 approve
- 时机: **阻塞 Claude**, 用户必须 ACTION
- 频率: 低 (每次危险操作)
- 重要性: 关键 — 用户切到别的窗口时, 没有 prompt 就一直卡住

**SessionStart** (本批新增):
- 场景: `claude` 启动 / `/resume` / `/clear` 之后
- 时机: Session 边界 (cold start)
- 频率: 极低 (每次开 claude 一次)
- 区分: 与 UserPromptSubmit 不同, SessionStart 只在 session 边界触发; UserPromptSubmit 每个 turn 都触发

**PreToolUse (Bash)** (本批新增):
- 场景: Claude 准备执行 bash 命令前
- 时机: 工具调用前 (subtle cue)
- 频率: 高 (每 bash 命令 1 次) — matcher 限制为 `Bash` 而非 `*` 控制噪音
- 注意: PreToolUse 全 14 tool 默认都触发, matcher 必须设 "Bash" 否则会淹没其他 hook

### 1.3 Hook 事件时序图

```
User submits prompt        Claude thinks        Claude calls Bash     Claude finishes turn
        |                       |                      |                       |
        v                       |                      |                       |
UserPromptSubmit (prompt)      |                      |                       |
                                |                      v                       |
                                |              PreToolUse (tool, matcher=Bash)
                                |                      |                       |
                                |                      v                       |
                                |              (Claude runs Bash)             |
                                |                      |                       |
                                |                      v                       |
                                |              (Claude thinks more)            |
                                |                      |                       |
                                v                      v                       v
                                                                       Stop (stop)
```

```
Background event (NOT user turn):
                                                Notification (notify)
                                                (no Stop fires after)

Permission request:
                                                PermissionRequest (perm)
                                                **BLOCKS claude**

Session lifecycle:
SessionStart (session)
  ... many turns ...
[Ctrl+C + claude --continue]
SessionStart (session) again
```

---

## 2. 配置

### 2.1 文件位置

所有配置在用户级 (不在仓库), 用户级路径:
- Hook 配置: `C:/Users/pc/.claude/settings.json`
- Wrapper 脚本: `C:/Users/pc/bin/claude-voice-alert-{hook}.ps1` (6 个)
- Master wrapper: `C:/Users/pc/bin/claude-voice-alert.ps1` (mode-routing dispatcher)
- 项目脚本 (high-quality 路径): `e:/microbubble-agent/scripts/voice-alert.ps1` (已有, 不动)

### 2.2 `C:/Users/pc/.claude/settings.json` 注入

完整 hook 块 (`env` 块和 `model` 字段省略, 仅 hooks 部分):

```json
{
  "env": {
    "MNB_VOICE_ALERT_PROJECT_DIR": "e:\\microbubble-agent"
  },
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "powershell -ExecutionPolicy Bypass -File \"C:/Users/pc/bin/claude-voice-alert-stop.ps1\"" }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "powershell -ExecutionPolicy Bypass -File \"C:/Users/pc/bin/claude-voice-alert-prompt.ps1\"" }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "powershell -ExecutionPolicy Bypass -File \"C:/Users/pc/bin/claude-voice-alert-notify.ps1\"" }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "powershell -ExecutionPolicy Bypass -File \"C:/Users/pc/bin/claude-voice-alert-perm.ps1\"" }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "powershell -ExecutionPolicy Bypass -File \"C:/Users/pc/bin/claude-voice-alert-session.ps1\"" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "powershell -ExecutionPolicy Bypass -File \"C:/Users/pc/bin/claude-voice-alert-tool.ps1\"" }
        ]
      }
    ]
  }
}
```

**关键设置**:
- `PreToolUse` 用 `matcher: "Bash"` 限制只对 Bash 工具响应 (其他 13 tool 静默 — 频率太高)
- 其他 5 hook 都用 `matcher: "*"` (无条件触发)
- `MNB_VOICE_ALERT_PROJECT_DIR` 环境变量必须设置 — wrapper 用来发现项目脚本 (高保真 TTS 走 edge-tts / ChatTTS 而不是兜底 SAPI)

### 2.3 Wrapper 脚本模式

每个 trigger ps1 都遵循同一模板:

```powershell
# header 注释说明 trigger 时机 / 区分 / 兜底策略
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    $HookInput
)

$ErrorActionPreference = "Continue"
$Wrapper = "C:\Users\pc\bin\claude-voice-alert.ps1"
if (-not (Test-Path $Wrapper)) { exit 0 }

try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Wrapper --mode <mode> @HookInput
} catch { }

exit 0
```

**关键约束** (W68 第 12 批 B-4 发现的 PS binding 铁律):
- 用 `--mode <value>` **空格分隔**, **不能用** `--mode=<value>` 等号形式
- PowerShell 5.1+ 把 `=` 语法保留给 switch 参数, `[string]$Mode` 收到的是字面值 `"--mode=session"`, 然后 `$RestArgs` 为空
- 反过来 `--mode session` 才会正确绑定到 `$Mode = "session"`

### 2.4 Master Wrapper 模式分发

`C:/Users/pc/bin/claude-voice-alert.ps1` 是分发中枢, 接受 `--mode <X>` 选 6 种消息:

```powershell
if ($Mode -eq 'prompt') {
    $message = "Prompt received, Claude is processing"
} elseif ($Mode -eq 'stop') {
    $message = "Claude has completed all tasks, please come back to check the results"
} elseif ($Mode -eq 'notify') {
    $message = "Claude has a background notification, please check the terminal"
} elseif ($Mode -eq 'perm') {
    $message = "Claude is asking for permission, please approve or deny now"
} elseif ($Mode -eq 'session') {
    $message = "Claude Code session is ready"
} elseif ($Mode -eq 'tool') {
    $message = "Running a bash command"
} elseif ($hasTaskDone) { ... }
elseif ($hasNeedConfirm) { ... }
elseif ($hasAskQuestion) { ... }
elseif ($hasOnError) { ... }
else { $message = "Claude has completed all tasks..." }
```

然后按顺序尝试:
1. **项目脚本** (`e:/microbubble-agent/scripts/voice-alert.ps1`): 高保真 edge-tts / ChatTTS
2. **SAPI 兜底**: Microsoft Huihui Desktop 中文女声 (Win 内置, 100% 可用)

如果项目脚本拒绝 `--mode` 参数 (因项目脚本只接 `-TaskDone` 等), wrapper 收到非零 exit, 切到 SAPI fallback, 这时 mode-based message 已经选好.

---

## 3. 测试

### 3.1 单元测试 (直接调 trigger ps1)

```powershell
# 清空当日 log, 然后跑全部 6 trigger
Remove-Item "C:/Users/pc/AppData/Local/voice-alert/wrapper-$(Get-Date -Format 'yyyyMMdd').log" -ErrorAction SilentlyContinue
Remove-Item "C:/Users/pc/AppData/Local/voice-alert/global-$(Get-Date -Format 'yyyyMMdd').log" -ErrorAction SilentlyContinue

# 逐个跑 (每个隔 1s, SAPI 兜底要 ~7s)
foreach ($t in 'stop','prompt','notify','perm','session','tool') {
    powershell -ExecutionPolicy Bypass -File "C:/Users/pc/bin/claude-voice-alert-$t.ps1"
    Start-Sleep -Seconds 1
}

# 验证
Get-Content "C:/Users/pc/AppData/Local/voice-alert/wrapper-$(Get-Date -Format 'yyyyMMdd').log" `
  | Select-String '"mode"' `
  | ForEach-Object { ($_ | ConvertFrom-Json).mode } `
  | Group-Object
```

期望输出: 6 个 mode 计数都相等.

### 3.2 实操测试 (启动 claude code 听 6 trigger)

```bash
# 1. 打开终端
cd e:/microbubble-agent
claude

# 2. 听 SessionStart — 听到 "Claude Code session is ready"
# 3. 输 prompt: "hello"
# 4. 听 UserPromptSubmit — 听 prompt 收到 (微妙)
# 5. 听 Bash PreToolUse (每次 Claude 跑命令) — 听 "Running a bash command"
# 6. 切到另一窗口 (Win+D / Alt+Tab)
# 7. Claude 答完 → 听 Stop — 听 task done
# 8. 让 Claude 跑危险命令 (rm -rf ./test) → 听 PermissionRequest — 听 ask permission
# 9. (后台) Claude 跑长 celery task → 听 Notification — 听 background notification
# 10. /clear → 听 SessionStart — 听 session ready
```

### 3.3 日志位置

- `C:/Users/pc/AppData/Local/voice-alert/wrapper-YYYYMMDD.log` — wrapper 每次调的 INFO/WARN/ERROR 日志 (含 mode)
- `C:/Users/pc/AppData/Local/voice-alert/global-YYYYMMDD.log` — SAPI 兜底时的实际 message + engine
- `e:/microbubble-agent/logs/voice-alert/voice-alert-YYYYMMDD.log` — 项目脚本 (high-quality 路径) 日志 (如果有)

---

## 4. 关闭

### 4.1 关单个 trigger

注释掉 `settings.json` 里对应的 hook 块. 例如关 Notification:

```json
{
  "hooks": {
    "Stop": [...],
    "UserPromptSubmit": [...],
    // "Notification": [
    //   { "matcher": "*", "hooks": [...] }  // disabled 2026-07-24
    // ],
    "PermissionRequest": [...],
    "SessionStart": [...],
    "PreToolUse": [...]
  }
}
```

改完立即生效 (下次 claude code 启动时读 settings.json). Claude Code 不缓存 settings.json.

### 4.2 关全部 (临时)

把 hook 块全部注释掉, 或者临时改 `command` 为 `echo` / `exit 0`:

```json
"command": "echo off"   # 或 "exit 0"
```

### 4.3 关 Bash PreToolUse (噪音最大)

`PreToolUse` 的 matcher 是 `Bash` — bash 命令多时每个都触发, 太吵. 改成 matcher `"*" "(Edit|Read|Write|Glob|Grep)"` 或直接删除整个 PreToolUse 块:

```json
// "PreToolUse": [...]  // disabled - too noisy
```

### 4.4 关 SAPI 兜底 (只保留 high-quality)

编辑 wrapper, 把 SAPI fallback 段删除 (line 153-220). 但**不推荐** — 项目脚本未启动或 edge-tts/ChatTTS 全部 down 时会无声音. SAPI 是 100% 可用的兜底.

---

## 5. 升级路径

| 版本 | Trigger 数 | 改动 | 日期 |
|------|----------|------|------|
| v0 (D-3) | 2 (Stop + UserPromptSubmit) | wrapper + 2 ps1 | 2026-07-24 |
| v1 (本批 B-4) | 6 (Stop + UserPromptSubmit + Notification + PermissionRequest + SessionStart + PreToolUse) | 4 新 ps1 + wrapper 扩 4 mode + 6 hook 配置 | 2026-07-24 |

---

## 6. 关联

- D-3 调研: 锚点范式第 24 守恒 (W68 第 7 批 D-3 第一次提 voice-alert hook)
- B-4 调研: 锚点范式第 151 守恒 (本次)
- Memory: [w68-route-12-b4-claude-notify-v2-2026-07-24.md](../memory/w68-route-12-b4-claude-notify-v2-2026-07-24.md)
- Project script: `e:/microbubble-agent/scripts/voice-alert.ps1` (未改动 — W68 第 7 批 D-3 已建好)

---

**0 production code 改动铁律维持** — 本次仅:
- 用户级 `C:/Users/pc/.claude/settings.json` (4 hook 块新增)
- 用户级 `C:/Users/pc/bin/claude-voice-alert.ps1` (扩 4 mode)
- 用户级 `C:/Users/pc/bin/claude-voice-alert-{notify,perm,session,tool}.ps1` (4 新建)
- 项目 docs + memory 文件 (不属 production code, 文档沉淀)
