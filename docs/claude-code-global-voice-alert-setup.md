# Claude Code Global Voice Alert Setup (W68 D-3)

> **Wiring**: user-level hooks in `C:\Users\pc\.claude\settings.json` trigger voice alerts in every Claude Code window, regardless of cwd or project. Falls back gracefully when no project script is found.

## 1. Background

### Original plan

The plan `claude-code-claude-code-bubbly-parnas.md` was originally about wiring a Stop hook in user-level settings to play a voice alert when Claude Code finishes responding. The plan was later marked DELETED during the claude-pet project decommission (2026-07-22), but the **underlying target (global voice alert hook) was never actually wired** — only the wrapper script (`claude-voice-alert.ps1`) was added.

### What this document implements

This document + the related code changes **complete the original plan's intent**:

1. User-level `Stop` hook (Claude finished responding)
2. User-level `UserPromptSubmit` hook (user submitted a prompt)
3. Smart wrapper auto-discovers project-level voice script
4. Silent SAPI fallback if no project script available

### Why user-level hooks (not project-level)

- **Any cwd**: user's multiple Claude Code windows run on different projects → setting it project-level would only wire one project
- **Survives project moves**: project-level `.claude/settings.json` is per-repo, user-level is permanent
- **Single point of truth**: all wrapper scripts live under `C:\Users\pc\bin\`, all logs go to `%LOCALAPPDATA%\voice-alert\`
- **No double-fire risk**: project-level `.claude/settings.json` does NOT have a `hooks` block — verified at the time of writing (2026-07-24)

## 2. User-level settings.json hooks configuration

The relevant block in `C:\Users\pc\.claude\settings.json`:

```json
{
  "env": {
    ...
    "MNB_VOICE_ALERT_PROJECT_DIR": "e:\\microbubble-agent"
  },
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
    "UserPromptSubmit": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "powershell -ExecutionPolicy Bypass -File \"C:/Users/pc/bin/claude-voice-alert-prompt.ps1\""
          }
        ]
      }
    ]
  }
}
```

### Key design choices

| Choice | Why |
|--------|-----|
| `matcher: "*"` | Hook fires regardless of tool name / cwd |
| `C:/Users/pc/bin/claude-voice-alert-stop.ps1` (separate file, not wrapper directly) | Lets each hook script be tuned (Stop vs UserPromptSubmit messages) without changing shared wrapper |
| `MNB_VOICE_ALERT_PROJECT_DIR` env var (not hardcoded) | Wrapper checks env first → easy project-specific override |
| Two distinct scripts (Stop + UserPromptSubmit) | Different message semantics: "task done, check" vs "prompt received" |
| Project script delegation | XiaoxiaoNeural high-quality neural voice (> Microsoft Huihui Desktop SAPI) |
| SAPI fallback | Works in any cwd even when project script missing |

### Hook firing semantics

| Hook event | Fires when | Default message |
|------------|-----------|-----------------|
| `Stop` | Claude finishes responding (including tool-blocked errors) | "Claude has completed all tasks, please come back to check the results" |
| `UserPromptSubmit` | User submits a prompt (SSE stream begins) | "Prompt received, Claude is processing" |

These are distinct cues — `Stop` is the "you can look now" cue, `UserPromptSubmit` is the "submission acknowledged" cue. Some users may want to disable `UserPromptSubmit` to reduce noise (every keystroke vs every Claude response).

### Smart wrapper auto-discovery

`claude-voice-alert.ps1` resolves the project script in this priority order:

1. `MNB_VOICE_ALERT_PROJECT_DIR` (set in settings.json env block) → `Join-Path <root> "scripts\voice-alert.ps1"`
2. `MICROBUBBLE_PROJECT_ROOT` (alternative env override)
3. Hardcoded fallback: `e:\microbubble-agent\scripts\voice-alert.ps1`
4. None found → inline SAPI fallback to Microsoft Huihui Desktop / Zira / David

The wrapper writes a daily log to `%LOCALAPPDATA%\voice-alert\wrapper-YYYYMMDD.log` (JSONL).

## 3. Verification steps

Main orchestrator should manually verify after merge:

### Test 1: Settings.json valid JSON

```powershell
$json = Get-Content "C:\Users\pc\.claude\settings.json" -Raw | ConvertFrom-Json
Write-Output "Has hooks.Stop: $($null -ne $json.hooks.Stop)"
Write-Output "Has hooks.UserPromptSubmit: $($null -ne $json.hooks.UserPromptSubmit)"
Write-Output "Stop command: $($json.hooks.Stop[0].hooks[0].command)"
Write-Output "Project dir: $($json.env.MNB_VOICE_ALERT_PROJECT_DIR)"
```

Expected output:
```
Has hooks.Stop: True
Has hooks.UserPromptSubmit: True
Stop command: powershell -ExecutionPolicy Bypass -File "C:/Users/pc/bin/claude-voice-alert-stop.ps1"
Project dir: e:\microbubble-agent
```

### Test 2: Wrapper scripts exist

```powershell
Test-Path "C:\Users\pc\bin\claude-voice-alert.ps1"   # True
Test-Path "C:\Users\pc\bin\claude-voice-alert-stop.ps1"  # True
Test-Path "C:\Users\pc\bin\claude-voice-alert-prompt.ps1"  # True
```

### Test 3: Within MicroBubble project cwd

```powershell
cd e:\microbubble-agent
claude   # or some Claude Code invocation
# After Claude finishes: should hear XiaoxiaoNeural "Claude has completed all tasks..."
#   (via project scripts/voice-alert.ps1 with edge-tts high-quality voice)
```

### Test 4: Within a different project cwd

```powershell
mkdir C:\tmp\test-project
cd C:\tmp\test-project
claude   # any invocation
# After Claude finishes: should hear SAPI "Claude has completed all tasks..."
#   (Microsoft Huihui Desktop, slightly worse quality but works offline)
```

### Test 5: UserPromptSubmit fires

Same as Test 3/4 but immediately after pressing Enter on a prompt, the wrapper log should show entries with `"mode": "prompt"`.

## 4. Troubleshooting

### Symptom 1: Hook doesn't fire at all

**Cause**: settings.json syntactically broken, PowerShell can't parse.

**Debug**:
```powershell
$json = Get-Content "C:\Users\pc\.claude\settings.json" -Raw | ConvertFrom-Json
# If this throws, JSON is broken — restore from backup
Copy-Item "C:\Users\pc\.claude\settings.json.bak.2026-07-22" "C:\Users\pc\.claude\settings.json" -Force
```

### Symptom 2: Hook fires but no sound

**Cause**: PowerShell process can't reach System.Speech.

**Debug**:
```powershell
# Try SAPI manually
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Speak("Hello world")
# Should hear "Hello world" — if not, your Windows audio is broken (different problem)
```

### Symptom 3: Hook fires but plays Microsoft Zira (English) instead of Huihui (Chinese)

**Cause**: Windows 11 image doesn't include the Chinese voice pack.

**Debug**:
```powershell
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.GetInstalledVoices() | Select-Object -ExpandProperty VoiceInfo | Select-Object Name
# Look for "Microsoft Huihui Desktop" — if missing, this Windows image has no Chinese TTS
```

**Mitigation**: SAPI falls back to Microsoft Zira (English) — accept the quality hit, or install Chinese language pack via Windows Settings.

### Symptom 4: Hook fires twice (double beep)

**Cause**: Both user-level AND project-level `.claude/settings.json` have hooks for the same event.

**Debug**:
```powershell
# Check both:
Test-Path "C:\Users\pc\.claude\settings.json"  # Always exists
Test-Path "e:\microbubble-agent\.claude\settings.json"  # If True, check its hooks block
```

**Mitigation**: Project-level `.claude/settings.json` (`.claude/settings.local.json` is fine, it's for overrides) should NOT contain a `hooks` block. Move to `.claude/settings.local.json` if needed for local dev.

### Symptom 5: Hook fires too often (every keystroke = UserPromptSubmit noise)

**Cause**: UserPromptSubmit fires on every Enter press in Claude Code's input.

**Mitigation**: Either accept the noise (it's only ~0.5s spoken), or remove the UserPromptSubmit hook block from `C:\Users\pc\.claude\settings.json` while keeping Stop. The Stop hook is the high-value one (task completion cue).

## 5. Rollback

### Quick disable (no file edit)

Comment out the hooks blocks in `C:\Users\pc\.claude\settings.json`:

```json
{
  ...
  // "hooks": {
  //   "Stop": [...],
  //   "UserPromptSubmit": [...]
  // },
  ...
}
```

Or use a git stash if settings.json is in version control (it isn't in this case — it's in `~`, not in `e:\microbubble-agent`).

### Full revert

Restore from backup or remove the new wrapper scripts:

```powershell
# Remove all wrapper scripts
Remove-Item "C:\Users\pc\bin\claude-voice-alert-stop.ps1"
Remove-Item "C:\Users\pc\bin\claude-voice-alert-prompt.ps1"
# Keep claude-voice-alert.ps1 (it was already present from W68 第 3 批)
```

Then remove the `hooks` block from `C:\Users\pc\.claude\settings.json` and the `MNB_VOICE_ALERT_PROJECT_DIR` env var. Claude Code will revert to no voice alerts.

## 6. 6 Trigger end-to-end test (W68 第 13 批 B-4)

W68 第 12 批 B-4 实施把 hooks 从 2 (Stop + UserPromptSubmit) 扩展到 6 (Stop + UserPromptSubmit + Notification + PermissionRequest + SessionStart + PreToolUse-Bash). 配套的 6 trigger 实跑测试脚本在 `scripts/test-claude-code-notify-6triggers.sh`.

### 6.1 跑测试

主指挥 SSH 跑 (在 `e:\microbubble-agent` 仓库根):

```bash
bash scripts/test-claude-code-notify-6triggers.sh
```

期望: 6 trigger 全部 PASS, wrapper log 6 行 mode 字段分别为 stop/prompt/notify/perm/session/tool.

### 6.2 6 trigger 期望 SAPI 兜底念消息

| Trigger | Hook 事件 | 期望 SAPI 念 | Wrapper script |
|---------|----------|-------------|----------------|
| 1. Stop            | Claude 完成回复       | "Claude 已经完成所有任务,请回来查看结果吧" | `claude-voice-alert-stop.ps1` |
| 2. UserPromptSubmit| 用户发 prompt         | "正在处理您的输入" | `claude-voice-alert-prompt.ps1` |
| 3. Notification    | Claude 切窗口发通知   | "需要您注意,Claude 有新的通知" | `claude-voice-alert-notify.ps1` |
| 4. PermissionRequest| Claude 问 approve    | "需要您批准权限" | `claude-voice-alert-perm.ps1` |
| 5. SessionStart    | Claude 启动 (含 /resume / /clear) | "开始新会话" | `claude-voice-alert-session.ps1` |
| 6. PreToolUse-Bash | Claude 调 Bash 工具前  | "正在执行工具" | `claude-voice-alert-tool.ps1` |

### 6.3 测试脚本结构

`scripts/test-claude-code-notify-6triggers.sh` (250 行) 6 段:

1. **PATH 校验** — 确认从仓库根跑 (要求 `scripts/` + `memory/` 目录存在)
2. **6 trigger 矩阵** — `stop|prompt|notify|perm|session|tool` 数组 + 期望消息
3. **前置检查** — 6 wrapper scripts 存在 + `~/.claude/settings.json` hooks blocks 数 (期望 ≥ 6) + `MNB_VOICE_ALERT_PROJECT_DIR` env var 配置
4. **6 trigger 逐个实跑** — `timeout 15s powershell.exe -File <wrapper>` 调每个 wrapper, 记录 exit code + 耗时
5. **wrapper log 校验** — 读 `%LOCALAPPDATA%\voice-alert\wrapper-YYYYMMDD.log`, 验证 6 行 mode 字段全覆盖
6. **总报告** — PASS/FAIL 计数 + 听感验证清单 (主指挥逐条人工核对)

### 6.4 wrapper log 字段对照

每个 wrapper 调用后, `claude-voice-alert.ps1` wrapper 写一行 JSONL 到 `%LOCALAPPDATA%\voice-alert\wrapper-YYYYMMDD.log`:

```json
{"timestamp":"2026-07-24T...","level":"INFO","script":"claude-voice-alert-wrapper","mode":"stop","message":"delegating to project script","cwd":"...","project_script":"e:\\microbubble-agent\\scripts\\voice-alert.ps1","discovery":"env:MNB_VOICE_ALERT_PROJECT_DIR"}
```

测试脚本通过 `grep -c '"mode":"${MODE}"'` 校验每个 trigger 都至少一行 (最理想是 2 行: "delegating" + "SAPI playback complete" 或 project script "returned").

### 6.5 失败排查

- **wrapper exit != 0** — 检查 wrapper 自身 (PowerShell `$ErrorActionPreference = "Continue"` + try/catch + 末行 `exit 0` 应永远 0). 若非 0 是 wrapper bug, 需修 wrapper
- **wrapper log 缺 mode 行** — wrapper 委托给 project script 失败 (e.g., `scripts/voice-alert.ps1` 缺失), 但 wrapper 自己 fallback SAPI 应该仍有 log. 若全无, wrapper 委托前就 raise, 看 `logs/notify-6trigger-YYYYMMDD.log` 原始 stderr
- **SAPI 念错消息** — 看 `claude-voice-alert.ps1` line 165-196 mode-message 映射分支, 模式匹配字符串是 `'stop'` / `'prompt'` 等小写精确匹配, trigger wrapper 必须用 `--mode stop` (空格分隔, 不是 `=`)
- **听到的是英文 (Zira)** — Windows 11 镜像不含 Huihui 中文 voice pack, SAPI fallback 到 Zira Desktop. 是预期降级行为, 不是 bug

### 6.6 跨平台注意

脚本设计**只**跑在主指挥本地 PC (Windows 11 + PowerShell + SAPI). 在云 server / Linux / WSL **不要**跑 — TTS 念不到用户耳朵, wrapper 委托给 `e:\microbubble-agent\scripts\voice-alert.ps1` 会因路径不存在静默 SAPI fallback, 浪费电.

CI 跑该脚本时设 `SKIP_NOTIFY_TEST=1` (后续 §"## Related documents" 列的 `setup-claude-code-notify.sh` 会读这个 env var).

## Related documents

- `scripts/voice-alert.ps1` — project-level voice script (delegated target)
- `.claude/voice-alert-readme.md` — project-level note: hook has moved to user-level
- `scripts/test-claude-code-notify-6triggers.sh` — W68 第 13 批 B-4 6 trigger 实跑测试 (250 行, 见 §6)
- `docs/claude-code-notify-system-v2-2026-07-24.md` — W68 第 12 批 B-4 6 trigger catalogue + settings.json snippet (commit `f0c373663`)
- `C:\Users\pc\bin\claude-voice-alert.ps1` — original wrapper (W68 第 3 批)
- `C:\Users\pc\bin\claude-voice-alert-{stop,prompt,notify,perm,session,tool}.ps1` — 6 trigger wrappers (W68 D-3 + W68 第 12 批 B-4)
- `C:\Users\pc\bin\test-voice-alert.ps1` — comprehensive end-to-end test (W68 第 3 批)

## History

- **W68 第 13 批 B-4 (2026-07-24)**: Added §6 6 trigger end-to-end test docs + `scripts/test-claude-code-notify-6triggers.sh` (250 行). Verified W68 第 12 批 B-4 实施的 6 wrapper scripts 全部能实跑 + SAPI fallback 念 6 条消息. 锚点范式第 165 守恒
- **W68 第 12 批 B-4 (2026-07-24)**: 6 trigger voice-alert system v2. Wired 4 new hooks (Notification / PermissionRequest / SessionStart / PreToolUse-Bash) + PS `--mode=xxx` → `--mode xxx` binding fix. commit `f0c373663` (only docs in repo, user-level lives outside)
- **W68 D-3 (2026-07-24)**: Wire Stop + UserPromptSubmit hooks via thin wrapper scripts. Add `--mode` flag to support both events with distinct messages. Add `MNB_VOICE_ALERT_PROJECT_DIR` env var for project auto-discovery. commit `0b0e6e336`
- **W68 第 3 批 (2026-07-24)**: Created `claude-voice-alert.ps1` wrapper + `test-voice-alert.ps1` test harness. Hook was never wired.
- **Plan `claude-code-claude-code-bubbly-parnas.md`**: Original intent (created earlier, deleted 2026-07-22 alongside claude-pet project, but target was always global hook — never wired).
