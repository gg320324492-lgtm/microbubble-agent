# Claude Code 通知体系 v2 — Setup Guide (W68 第 13 批 B-1, 2026-07-24)

> **Purpose**: New machine / new user onboarding for the 6-trigger voice-alert notification system (Stop + UserPromptSubmit + Notification + PermissionRequest + SessionStart + PreToolUse).
>
> **Background**: W68 第 12 批 B-4 (commit `f0c37366`) implemented the system at user-level (`C:/Users/pc/`) only — nothing in the repo. W68 第 13 批 B-1 templatizes it: `scripts/notify-templates/` + `scripts/claude-code-notify-setup.sh` let any new machine get the same setup in one command.

---

## §1 主拍跑 setup.sh (5 min first-time setup)

### 1.1 Dry-run 检查 (推荐先跑)

```bash
cd /path/to/microbubble-agent
bash scripts/claude-code-notify-setup.sh --dry-run
```

预期输出 (no-fs-changes):
```
[STEP] DRY RUN — no filesystem changes
[INFO] Project root:    /path/to/microbubble-agent
[INFO] Template dir:    /path/to/microbubble-agent/scripts/notify-templates
[INFO] Target user bin: /c/Users/<you>/bin
[INFO] Target settings: /c/Users/<you>/.claude/settings.json
[STEP] Would copy 6 PowerShell triggers to /c/Users/<you>/bin/:
          - claude-voice-alert-{stop,prompt,notify,perm,session,tool}.ps1
[STEP] Would merge hooks block from settings.json.template → settings.json
[OK] Dry-run complete. Re-run with --apply to actually deploy.
```

### 1.2 Apply 真部署 (主拍拍板后跑)

```bash
bash scripts/claude-code-notify-setup.sh --apply
```

行为:
1. **备份** `~/.claude/settings.json` → `~/.claude-notify-backups/settings.json.bak.<UTC-timestamp>`
2. **复制** 6 个 `claude-voice-alert-*.ps1` 到 `<user-bin>/`
3. **合并** `settings.json.template` 的 `hooks` 块到 `~/.claude/settings.json` (用 jq 安全合并, 保留用户定义的 `env` / `model` / `permissions` / `effortLevel`)
4. **保存** install 状态到 `~/.claude-notify-install-state`

预期输出:
```
[STEP] APPLY — installing Claude Code 6-trigger voice-alert
[INFO] Backed up → /c/Users/pc/.claude-notify-backups/settings.json.bak.20260724T094512Z
[OK]   copied: claude-voice-alert-stop.ps1
[OK]   copied: claude-voice-alert-prompt.ps1
[OK]   copied: claude-voice-alert-notify.ps1
[OK]   copied: claude-voice-alert-perm.ps1
[OK]   copied: claude-voice-alert-session.ps1
[OK]   copied: claude-voice-alert-tool.ps1
[INFO] Merging hooks block from settings.json.template → settings.json
[OK]   settings.json merged (hooks from template, env/user keys preserved)
[INFO] State saved: /c/Users/pc/.claude-notify-install-state
[OK]   Apply complete. 6 triggers installed + settings.json merged.
```

### 1.3 验收 (立即跑)

启动任意 claude session, 发个 prompt, 切到别的窗口等约 3 秒 → 应该听到 SAPI 朗读 "Prompt received, Claude is processing" / "Claude has completed all tasks, please come back to check the results". 见 §2 各 trigger 期望语音内容.

### 1.4 状态检查 (任何时候)

```bash
bash scripts/claude-code-notify-setup.sh --verify
```

输出 6 trigger wrapper 文件存在性 + settings.json hooks entry 数. 退出码: 0=PASS / 1=有组件缺失 (跑 `--apply` 修复).

### 1.5 回滚 (后悔了)

```bash
bash scripts/claude-code-notify-setup.sh --rollback
```

行为:
1. 从 `~/.claude-notify-backups/settings.json.bak.<latest>` 恢复 settings.json
2. 删除 6 个 `claude-voice-alert-*.ps1`
3. 删除 install state 文件
4. 保留 backup 文件以备二次回滚

无 backup 时手动回滚:
```bash
rm /c/Users/pc/bin/claude-voice-alert-{stop,prompt,notify,perm,session,tool}.ps1
# 编辑 ~/.claude/settings.json, 删除整个 "hooks" 块
```

### 1.6 自定义路径 (CI / 非标准布局)

```bash
bash scripts/claude-code-notify-setup.sh --apply --bin /opt/hooks --settings /opt/claude/settings.json
# 或
MNB_USER_BIN=/opt/hooks MNB_USER_SETTINGS=/opt/claude/settings.json bash scripts/claude-code-notify-setup.sh --apply
```

---

## §2 6 Hook 触发时机 + 期望语音

| Trigger | 时机 | 期望语音 | 频率 | 优先级 |
|---------|-----|---------|------|--------|
| **Stop** | Claude 答完一个 turn 后 | "Claude has completed all tasks, please come back to check the results" | 高 (每 turn) | normal |
| **UserPromptSubmit** | 用户提交 prompt 后 | "Prompt received, Claude is processing" | 高 (每 turn) | normal |
| **Notification** | 后台事件 (长任务完成等) | "Claude has a background notification, please check the terminal" | 中 (取决于事件) | low |
| **PermissionRequest** | Claude 等待授权 (**阻塞**) | "Claude is asking for permission, please approve or deny now" | 低 (危险操作) | **high** |
| **SessionStart** | Session 启动 / `/resume` / `/clear` | "Claude Code session is ready" | 极低 (每 session 1 次) | normal |
| **PreToolUse (Bash)** | Bash 工具调用前 | "Running a bash command" | 高 (每 bash 命令) | low |

### 触发场景示例

**PermissionRequest** 关键场景:
- Claude 准备跑 `rm -rf xxx` / `git push --force` / 写文件 → 必须用户确认
- 用户切到别的窗口时, 没有 prompt 通知就一直卡住
- 听觉提示是最关键的: **你应该能听到 "Claude is asking for permission"**

**PreToolUse** matcher 选择:
- 默认 PreToolUse 对所有 14 tool 都触发, 太吵
- settings.json.template 已限制 `matcher: "Bash"` 只对 Bash 触发
- 想要更多 tool (如 Write) 加新 hook block: 见 §4 自定义

**SessionStart** 触发场景:
- `claude` 启动
- `/resume` 或 `--continue`
- `/clear`
- 不在 `/compact` 时触发 (compact 用 Notification)

---

## §3 跨平台支持

### 3.1 Linux / WSL / macOS

`setup.sh` 默认在 `/c/Users/<user>/bin/` (Git Bash 风格) 或 `~/bin/` (纯 Unix).
6 PowerShell wrapper 在 Linux 上**不被执行** (claude 不调用它们). 但拷贝 + settings.json 合并仍 OK — Linux 用户应该改用 bash 等价 hook 实现, 或者删除 hooks 块.

### 3.2 Windows (主场景)

Git Bash / WSL 跑 `setup.sh`:
- USER_BIN 自动检测为 `/c/Users/<USER>/bin`
- USER_SETTINGS 自动检测为 `/c/Users/<USER>/.claude/settings.json`
- PowerShell wrapper 由 claude 直接 spawn powershell 进程触发

原生 Windows (cmd.exe):
- 直接用绝对路径, 或装 Git Bash / WSL
- 不支持: `bash scripts/claude-code-notify-setup.sh`

### 3.3 跨项目 (multi-project 切换)

`MNB_VOICE_ALERT_PROJECT_DIR` env var 让 wrapper 自动发现 `scripts/voice-alert.ps1`:
- microbubble-agent 项目根 → 默认指向 `e:\microbubble-agent`
- 切到别的项目 (claude-pet / claude-qa-bench) 时, 在 settings.json env block 改对应路径
- wrapper 找不到时自动 fallback SAPI (Microsoft Huihui Desktop 内置, 不依赖任何 backend)

---

## §4 故障排查 (SAPI 兜底 验证 + D-3 wrapper 修复历史)

### 4.1 没声音 — SAPI 兜底 兜底也失败

**症状**: 6 trigger 都触发, 但没声音.

**诊断**:
```powershell
# Windows PowerShell
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Speak("Hello")  # 应听到 "Hello"
```

听不到 → Windows SAPI 服务出问题 (罕见, Win10/11 默认好). 重启资源管理器或检查音频服务.

听得到 → wrapper 走 SAPI fallback (项目脚本失败). 检查 `~/AppData/Local/voice-alert/wrapper-<date>.log`:
- `mode: "stop"` 等是否正确
- `error: ...` 是否记录

### 4.2 wrapper 一直 silent exit

**症状**: wrapper 跑完但啥都没说.

**诊断**: 检查 wrapper log:
```bash
cat /c/Users/pc/AppData/Local/voice-alert/wrapper-20260724.log | tail -20
```

看 `reason: "no-project-script-found"` 还是 `"project-script-threw-exception"`:
- `no-project-script-found`: `MNB_VOICE_ALERT_PROJECT_DIR` 路径错或 `scripts/voice-alert.ps1` 不在
- `project-script-threw-exception`: 项目脚本本身坏了 (PS 调用失败)

### 4.3 W68 第 7 批 D-3 wrapper 修复历史

W68 第 7 批 D-3 (commit `0b0e6e33`) 首次 wire 这套 hook 时遇到 2 个 bug:

1. **PS 5.1+ `--key=value` 路由 bug**: PS 默认把 `--mode=stop` (单 token) 路由到 `$RestArgs` 而不是 `$Mode`. 修复: 改成空格分隔 `--mode stop`. **本模板已用空格分隔**, 老 wrapper 命令 `bash -File ... --mode=stop` 在 PS 5.1+ 永远走错.
2. **wrapper log 启动失败**: wrapper 在 `cwd` 找不到 voice-alert.log 时直接抛异常. 修复: 强制 `mkdir -p $WrapperLogDir` + try/catch.

如果听到声音是错的 (如 "task done" 出现两次), 99% 是 PS 把 `--mode=stop` 路由到 `$RestArgs` 导致 fallback 到 default message. 检查触发 wrapper 是不是用空格分隔.

### 4.4 settings.json hooks 块意外丢失

**症状**: `--apply` 后只看到部分 trigger 在听.

**诊断**:
```bash
bash scripts/claude-code-notify-setup.sh --verify
```

若 hooks entries = 0 → jq merge 写坏了 settings.json:
```bash
# 手动恢复
cp /c/Users/pc/.claude-notify-backups/settings.json.bak.<latest> \
   /c/Users/pc/.claude/settings.json
# 重跑 setup.sh --apply
```

### 4.5 PowerShell ExecutionPolicy 阻止

**症状**: claude log 报 "file xxx.ps1 cannot be loaded because running scripts is disabled on this system".

**修复** (本模板 hooks 命令已加 `-ExecutionPolicy Bypass`):
- 若仍报, 系统级策略拦截. 跑一次: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
- **不要**用 `Set-ExecutionPolicy Unrestricted` (安全风险)

---

## §5 与 plan / commit 链的关系

| 阶段 | Plan | Commit | 实施 |
|------|------|--------|------|
| 首次 wire | `claude-code-global-voice-alert-2026-07-24.md` | `0b0e6e33` (W68 第 7 批 D-3) | Stop + UserPromptSubmit 2 trigger + wrapper |
| 完整 6 trigger | `claude-code-notify-system-2026-07-24.md` | `f0c37366` (W68 第 12 批 B-4) | 加 Notification + PermissionRequest + SessionStart + PreToolUse-Bash |
| 仓库模板 | (本 plan) | (W68 第 13 批 B-1) | `scripts/notify-templates/` + `setup.sh` + `setup-guide` |

下一阶段 (待派):
- W69 调研: 跨平台等价 (Linux bash wrapper) / Claude Code v0.x hook 新参数 / macOS SAPI 等价 (say 命令)

---

## §6 Reference

- **Plan**: `~/.claude/plans/claude-code-notify-system-2026-07-24.md`
- **Doc v2**: `docs/claude-code-notify-system-v2-2026-07-24.md` (W68 第 12 批 B-4 写的完整 6 trigger 详解)
- **Memory**: `memory/w68-route-13-b1-claude-notify-repo-2026-07-24.md` (本批沉淀)
- **Source scripts**: `scripts/voice-alert.ps1` (项目级 voice-alert, 109 行 TTS 主脚本)
- **Backup/state**: `~/.claude-notify-backups/` + `~/.claude-notify-install-state`
- **Wrapper log**: `~/AppData/Local/voice-alert/wrapper-<date>.log`
