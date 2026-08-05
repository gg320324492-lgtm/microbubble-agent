---
name: w2-auto-recovery-self-heal-2026-08-04
description: "W2 +N 完全自动恢复 (Winlogon EventID=7002 触发, 类 20.143 新铁律)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f676532-7417-4633-a1a2-f52dfe398530
  modified: 2026-08-04T13:29:25.046Z
---

# W2 +N 完全自动恢复 (2026-08-04, 类 20.143)

## 触发链 (实测验证 2026-08-04 21:26 + 21:27)

```
Windows 启动 → Docker Desktop 启动 (WSL2 backend)
↓
用户登录桌面 → Winlogon EventID=7002
↓
schtasks DELAY 0002:00
↓
scripts/auto-recovery-eventlog.ps1 (主逻辑, 211 行)
├─ Step 1: 智能等 docker info (5 min timeout)
├─ Step 2: 检测 8000 端口 zombie bind (类 20.138)
├─ Step 3: 跑 bash scripts/restart-recovery-after-gui-restart.sh (7 步)
├─ Step 4 (失败时): GUI 自愈 (Stop-Process + Start-Process + 等 120s)
├─ Step 5: TTS 警报 "fully restored" / "recovery failed"
└─ Step 6: JSON 日志 logs/auto-recovery/auto-recovery-YYYYMMDD.log
```

**实测性能**: 11.6 秒完整恢复 (Docker daemon + recovery 7 步 + 7 端点验证)。

## 关键发现 (本次实战沉淀)

### 1. Docker Desktop 不写 EventLog

**探索结果 (2026-08-04)**:
- Application log 全部 provider: Microsoft-Windows-Security-SPP / WSL / Windows Error Reporting / SecurityCenter / VBScriptDeprecationAlert 等
- **没有任何 "Docker Desktop" provider** (Docker Desktop 通过 WSL2 backend 运行, 不写 EventLog)
- System log 只有 Service Control Manager 7045 (一次性 service 安装, 不触发)
- WSL provider 写 event 但 Message 为空 (不可用作 XPath)

**结论**: 不能用 Docker Desktop 启动事件触发自动恢复, 必须用**用户登录事件** (Winlogon EventID=7002)。

### 2. schtasks /MO XPath 解析陷阱

**错误 XPath**: `*[System[Provider[@Name='Microsoft-Windows-Winlogon'] and EventID=7002]]`
**错误信息**: `无效选项 - 'and'`
**原因**: schtasks 的 /MO 参数解析器内部对 XPath 做 token 分析时, 把 `and` 当成**自己的 switch 关键字**。

**正确 XPath**: `*[System[Provider[@Name='Microsoft-Windows-Winlogon']][EventID=7002]]`
用嵌套谓词 `[System[...]][[EventID=...]` 避免使用 `and` 关键字。

### 3. $PSScriptRoot 在 schtasks 调起时为空

**坑**: `Set-Location (Split-Path -Parent $PSScriptRoot)` 在 schtasks 启动的 PowerShell 上下文里 `$PSScriptRoot` 是 null, `Split-Path -Parent $null` 抛错。

**修复**: 多级 fallback:
```powershell
$ScriptDir = $PSCommandRoot  # PowerShell 7+
if (-not $ScriptDir) { $ScriptDir = $PSScriptRoot }  # PS 5.1
if (-not $ScriptDir) { $ScriptDir = $MyInvocation.MyCommand.Path }
if (-not $ScriptDir) { $ScriptDir = $MyInvocation.MyCommand.Definition }
if (-not $ScriptDir) { $ScriptDir = "E:\microbubble-agent\scripts" }  # hardcoded
```

### 4. PowerShell stdout 在 bash pipe 里 buffered

**坑**: `powershell -File script.ps1 2>&1 | head -30` 可能零输出 (实际脚本跑了且写完日志, 但 stdout 被 buffered 在 pipe 里)。

**验证方法**: 直接 `ls logs/` 看文件是否生成, 而不是信 stdout。

## 类 20.143 (新增, 永久铁律)

**完全自动恢复**: 电脑重启后**无需人工**, 通过 schtasks 监听 Winlogon EventID=7002 + DELAY 2 分钟, 触发 scripts/auto-recovery-eventlog.ps1 自动恢复。

**触发器命令** (参考, 在管理员 PowerShell 跑):
```powershell
schtasks /Create /TN "MicroBubble-Auto-Recovery" `
  /TR "\"E:\microbubble-agent\scripts\auto-recovery-eventlog.ps1\"" `
  /SC ONEVENT `
  /EC Application `
  /MO "*[System[Provider[@Name='Microsoft-Windows-Winlogon']][EventID=7002]]" `
  /DELAY 0002:00 `
  /RL HIGHEST `
  /F
```

**实测场景**: Windows 锁屏唤醒**不**触发 (EventID=7002 仅在用户实际登录时触发, 这是正确语义); 每次用户登录都触发 (符合预期, 即使已登录也会触发)。

## 产物清单

- `scripts/auto-recovery-eventlog.ps1` (新增, 211 行, 主逻辑)
- `scripts/_register-task.ps1` (新增, 50 行, PowerShell 注册 wrapper, 自启 elevated)
- `scripts/install-auto-recovery.bat` (新增, 60 行, schtasks 安装, 纯 ASCII 避免 CP936)
- `scripts/local-watchdog.ps1` (修改, ExpectedServices 7→13)
- `docs/w100-meeting-pipeline-restart-2026-08-04.md` (新增 §8, 50 行)
- `CLAUDE.md` (新增类 20.143 段)

## Why

W100 +N 服务器关机恢复 (类 20.138-142) 解决了**单次**恢复, 但下次电脑重启用户仍需手动跑恢复脚本。本次实现**完全自愈**: 用户开机 → 登录 → 服务自动恢复, 零人工。这是"完全自动重启"的真正实现。

## How to apply

未来任何 "Docker Desktop 不写 EventLog" 场景:
1. **不要**假设 Docker Desktop 有启动事件 (实测确认无)
2. 用 Winlogon EventID=7002 (用户登录) 或 EventLog 轮询
3. XPath 避免 `and` 关键字 (用嵌套谓词)
4. schtasks 注册必须 RunAs elevated (Start-Process -Verb RunAs + Wait, 但 Start-Process 自身不能同时 Verb RunAs + Wait)
5. PowerShell 脚本必须 robust 处理 $PSScriptRoot 为 null 的情况