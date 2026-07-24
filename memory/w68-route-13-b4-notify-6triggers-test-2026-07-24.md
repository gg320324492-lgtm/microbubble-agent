# W68 第 13 批 B-4: claude-code 6 trigger 实跑测试脚本 + docs §6 + memory 沉淀

> **锚点范式第 165 守恒** (W68 第 13 批 B-4, 2026-07-24). 主指挥协调范式第 41 次派工. 5 新铁律. 0 production code 改动铁律维持 (测试脚本 + docs + memory 范畴).

## 1. 背景

W68 第 12 批 B-4 (commit `f0c373663`) 在用户级 `C:\Users\pc\.claude\settings.json` 实施 claude-code 通知 v2 6 trigger (Stop / UserPromptSubmit / Notification / PermissionRequest / SessionStart / PreToolUse-Bash) + 配套 6 wrapper scripts (`C:\Users\pc\bin\claude-voice-alert-{stop,prompt,notify,perm,session,tool}.ps1`). 同时修复 PS 5.1+ `--mode=value` → `--mode value` 参数绑定 bug.

B-4 实施完毕但**未做实跑测试**:
- 6 wrapper scripts 编译过 + 单元测试 PASS (mode 字段 log 验证)
- 但 6 trigger 在真实 hooks 事件中能否跑通 wrapper 委派 → project script → SAPI fallback 全链路, **未验证**
- 主指挥听到的是 SAPI 兜底念 6 消息, 还是 wrapper 静默退出, **未验证**

W68 第 13 批 B-4 (本次) 目标: 写 `scripts/test-claude-code-notify-6triggers.sh` 实跑脚本 (主指挥 SSH 跑), 验证 6 trigger 全部能触发 wrapper + 念对应消息 + wrapper log 6 行 mode 字段全覆盖.

## 2. 交付物 (3 文件)

### 2.1 新建 `scripts/test-claude-code-notify-6triggers.sh` (250 行)

脚本设计 6 段:

1. **PATH 校验** — 确认从仓库根跑 (要求 `scripts/` + `memory/` 目录存在, 不存在立即 exit 2)
2. **6 trigger 矩阵** — bash 关联数组 `stop|prompt|notify|perm|session|tool` + 期望 SAPI 消息
3. **前置检查** — 6 wrapper scripts 存在 (stat size) + `~/.claude/settings.json` hooks blocks 数 (期望 ≥ 6) + `MNB_VOICE_ALERT_PROJECT_DIR` env var 配置
4. **6 trigger 逐个实跑** — `timeout 15s powershell.exe -File <wrapper>` 调每个 wrapper, 记录 exit code + 耗时 + tee 日志
5. **wrapper log 校验** — 读 `%LOCALAPPDATA%\voice-alert\wrapper-YYYYMMDD.log`, `grep -c '"mode":"${MODE}"'` 验证 6 行全覆盖
6. **总报告** — PASS/FAIL 计数 + 听感验证清单 (主指挥逐条人工核对 SAPI 念 6 中文消息)

`logs/notify-6trigger-$(date +%Y%m%d).log` 自动按日落盘.

### 2.2 改 `docs/claude-code-global-voice-alert-setup.md`

W68 第 13 批 B-1 设想的 `docs/claude-code-notify-system-setup-guide-2026-07-24.md` 在本次 commit 时**尚未合并** (B-1 branch `chore/w68-13th-batch-b1-claude-notify-repo-2026-07-24` 还停在 main HEAD `243937b7f` 之前). 已存在的最近文档是 W68 D-3 wire 文档 `docs/claude-code-global-voice-alert-setup.md`, 选为 §6 追加目标 (避免凭空新建文档).

追加 §6 "6 Trigger end-to-end test (W68 第 13 批 B-4)" 7 段:
- 6.1 跑测试 (`bash scripts/test-claude-code-notify-6triggers.sh`)
- 6.2 6 trigger 期望 SAPI 兜底念消息 (含表格)
- 6.3 测试脚本结构 (6 段对应说明)
- 6.4 wrapper log 字段对照 (JSONL 解析示例)
- 6.5 失败排查 (wrapper exit != 0 / log 缺 mode / 念错消息 / 英文 fallback)
- 6.6 跨平台注意 (本地 PC only, CI 跑设 `SKIP_NOTIFY_TEST=1`)
- History + Related documents 加 W68 第 13 批 B-4 记录 + 引用 6 wrapper scripts

### 2.3 新建 `memory/w68-route-13-b4-notify-6triggers-test-2026-07-24.md` (本文)

锚点范式第 165 守恒 + 5 新铁律沉淀 (见 §6).

## 3. 6 trigger 实跑矩阵

| # | Trigger | Hook 事件 | Wrapper script | 期望 SAPI 念 | Wrapper log mode |
|---|---------|----------|----------------|-------------|------------------|
| 1 | Stop | Claude 完成回复 | `claude-voice-alert-stop.ps1` | "Claude 已经完成所有任务,请回来查看结果吧" | `stop` |
| 2 | UserPromptSubmit | 用户发 prompt | `claude-voice-alert-prompt.ps1` | "正在处理您的输入" | `prompt` |
| 3 | Notification | Claude 切窗口发通知 | `claude-voice-alert-notify.ps1` | "需要您注意,Claude 有新的通知" | `notify` |
| 4 | PermissionRequest | Claude 问 approve | `claude-voice-alert-perm.ps1` | "需要您批准权限" | `perm` |
| 5 | SessionStart | Claude 启动 (含 /resume / /clear) | `claude-voice-alert-session.ps1` | "开始新会话" | `session` |
| 6 | PreToolUse-Bash | Claude 调 Bash 工具前 | `claude-voice-alert-tool.ps1` | "正在执行工具" | `tool` |

**关键设计**: 测试脚本调 wrapper 时**不**传任何 `RestArgs` (走 mode-based default message 分支), 不模拟 Claude Code 真实 hook 事件 stdin. 这是 2 步取舍:

- **简化**: 不依赖 Claude Code 真实事件流, 测试脚本可独立跑 / CI 跑 / 反复跑
- **代价**: 仅验证 wrapper → master wrapper → SAPI fallback 全链路, 不验证 Claude Code 真实触发 wrapper (那个需主指挥手动跑 claude + 切窗口 + 听)

实际生产中 Claude Code 触发 hook 是 stdin 传 JSON (HookInput), wrapper 透传给 master wrapper + project script, 真实消息文本由 project script 决定. 测试脚本不传 HookInput → wrapper 仍能跑 (master wrapper 的 `$RestArgs` 参数允许空), 但念的是 fallback 默认消息.

## 4. 实跑流程

主指挥在 `e:\microbubble-agent` 仓库根跑:

```bash
bash scripts/test-claude-code-notify-6triggers.sh
```

期望输出:

```
==========================================
Claude-Code 6 Trigger 实跑测试 (W68 第 13 批 B-4)
Repo root: /e/microbubble-agent
Time:      2026-07-24T...
==========================================

[前置检查] 6 trigger wrapper scripts 存在?
----------------------------------------
  [OK] claude-voice-alert-stop.ps1 (2107 bytes)
  [OK] claude-voice-alert-prompt.ps1 (1595 bytes)
  [OK] claude-voice-alert-notify.ps1 (1404 bytes)
  [OK] claude-voice-alert-perm.ps1 (1491 bytes)
  [OK] claude-voice-alert-session.ps1 (1580 bytes)
  [OK] claude-voice-alert-tool.ps1 (1817 bytes)

[6 Trigger 实跑]
----------------------------------------
[Test 1/6] Trigger: stop (claude-voice-alert-stop.ps1)
         Expected: Claude 已经完成所有任务,请回来查看结果吧
         [PASS] exit=0, 3s

... (5 more)

[wrapper log 校验]
----------------------------------------
  [OK] log: mode=stop (2 entries)
  [OK] log: mode=prompt (2 entries)
  [OK] log: mode=notify (2 entries)
  [OK] log: mode=perm (2 entries)
  [OK] log: mode=session (2 entries)
  [OK] log: mode=tool (2 entries)

==========================================
总报告: PASS=6 / 6, FAIL=0 / 6
==========================================
```

## 5. 跨 PR 协调

### 5.1 与 W68 第 13 批 B-1 (claude-notify-repo-template) 关系

B-1 计划实现 `scripts/setup-claude-code-notify.sh` (一键 setup 6 wrapper + settings.json) + `docs/claude-code-notify-system-setup-guide-2026-07-24.md` (仓库模板). 截至本次 commit, B-1 还在 main HEAD `243937b7f` 之前的 branch 上**未合并**.

本次 B-4 不依赖 B-1 合并:
- 6 wrapper scripts 早已存在于 `C:\Users\pc\bin\` (W68 第 12 批 B-4 已实装, user-level 不在 repo)
- 测试脚本只看 scripts 存在 + settings.json 有 hooks block, 不关心 setup 流程
- docs §6 追加到 D-3 已有的 setup 文档, 避免新建 B-1 文档冲突

### 5.2 与 W68 第 12 批 B-4 (commit `f0c373663`) 关系

B-4 是**实施** (commit `f0c373663` 的 `docs/claude-code-notify-system-v2-2026-07-24.md` 是 catalogue + 设计, user-level wrapper/settings 改动在用户级 `C:\Users\pc\` 不在 repo), 本次 W68 第 13 批 B-4 是**实跑验证** (写测试脚本跑 + docs §6 + memory).

两层 B-4 命名冲突但内容清晰:
- **W68 第 12 批 B-4**: claude-code 通知 v2 实施 (user-level)
- **W68 第 13 批 B-4**: claude-code 6 trigger 实跑测试 (repo-level)

### 5.3 与 W68 D-3 hook wire 关系

W68 D-3 (commit `0b0e6e336`) 是 Stop + UserPromptSubmit 2 trigger wire. W68 第 12 批 B-4 扩到 6 trigger. 本次 §6 docs 实质是 D-3 setup 文档的 6 trigger 化扩写.

## 6. 5 新铁律

### 铁律 1: 6 trigger 实跑必 SAPI 兜底

每个 wrapper 设计 "Always exit 0" + SAPI fallback 兜底 (即使 project script 失败 / 不存在). 实跑测试**不依赖** project script (`scripts/voice-alert.ps1`) 存在, 必须能独立验证 wrapper → master wrapper → SAPI fallback 全链路.

- 反模式: 测试脚本先 assert project script 存在, 再跑 wrapper → 任何 project script bug 都污染 wrapper 验证
- 正模式: 直接跑 wrapper, 让 SAPI fallback (Microsoft Huihui Desktop / Zira) 念 fallback 消息, 验证 wrapper 自身行为 + log 写入

### 铁律 2: 测试脚本 setup.sh 跑 (未来 B-1)

W68 第 13 批 B-1 (未合并) 计划写 `scripts/setup-claude-code-notify.sh`, 主指挥跑一次 setup, 6 wrapper + settings.json 全部就位. B-1 的 setup 脚本必须**支持被测试脚本反查**: 测试脚本前置检查阶段查 `~/.claude/settings.json` 包含 ≥ 6 hooks blocks (Stop+UserPromptSubmit+Notification+PermissionRequest+SessionStart+PreToolUse).

- 现状: 测试脚本独立跑, 不强制依赖 B-1 setup 脚本 (若 B-1 已实施就直接 verify)
- 未来: B-1 merge 后, 主指挥 SSH 跑流程变为 `bash scripts/setup-claude-code-notify.sh && bash scripts/test-claude-code-notify-6triggers.sh`

### 铁律 3: logs/ 必按日

测试脚本写日志到 `logs/notify-6trigger-$(date +%Y%m%d).log` (按日), **不**写单一 `notify-test.log` (会无限增长, 几天就几百 KB).

- 反模式: 单一 `notify-test.log` (append mode), 一周后 10MB, 后续 git grep 卡
- 正模式: 按日分文件 + `git log --follow -- logs/notify-6trigger-20260724.log` 单独追溯
- 跨平台兼容: Git Bash + Linux + macOS 都能解析 `$(date +%Y%m%d)`, 无需外部依赖

### 铁律 4: 触发模拟必真实环境

测试脚本**只**在主指挥本地 PC (Windows 11 + PowerShell + SAPI + 6 wrapper scripts) 跑. 在云 server / Linux / WSL 跑是**预期失败** (TTS 念不到用户耳朵, wrapper 委托给 `e:\microbubble-agent\scripts\voice-alert.ps1` 会因路径不存在静默 SAPI fallback, 浪费电).

- 跨平台注意在 §6.6 docs 明确写出
- CI 跑该脚本设 `SKIP_NOTIFY_TEST=1` (后续 B-1 setup 脚本会读这个 env var)
- 当前脚本**未**内置 `SKIP_NOTIFY_TEST` 检查, 是设计取舍: 主指挥首次跑就该听, 不要 CI 自动跑绕开

### 铁律 5: 跨平台兼容

测试脚本设计为 Git Bash on Windows 主跑, 同时兼容 Linux/macOS (CI 后续集成). 关键兼容点:

- **路径转换**: `WIN_REPO_ROOT="$(cd "${REPO_ROOT}" && pwd -W 2>/dev/null || echo "${REPO_ROOT}")"` — Git Bash 才有 `pwd -W`, Linux/macOS fallback 原路径
- **wrapper 路径**: `/c/Users/pc/bin/...` Git Bash 风格, 直接传给 `powershell.exe -File`. Linux/macOS 没有 `powershell.exe`, 跑会失败 (设计意图)
- **stat size**: `stat -c%s` Linux + `stat -f%z` macOS 二选一, 兼容写法
- **date format**: `date -Iseconds` (Linux) `date` (macOS) 二选一, ISO 8601 输出

## 7. 文件清单 (本次 commit)

- 新建 `scripts/test-claude-code-notify-6triggers.sh` (250 行)
- 修改 `docs/claude-code-global-voice-alert-setup.md` (追加 §6 6 trigger end-to-end test + History + Related documents)
- 新建 `memory/w68-route-13-b4-notify-6triggers-test-2026-07-24.md` (本文, ~150 行)

总 3 文件, 0 production code 改动, 锚点范式第 165 守恒.

## 8. 后续

- 主指挥合并本次分支 + W68 第 13 批 B-1 后, 跑 `bash scripts/setup-claude-code-notify.sh && bash scripts/test-claude-code-notify-6triggers.sh` 完整流程
- 若测试 fail, 主指挥听感 + log 排查 (参考 §6.5 docs 失败排查段)
- 验证通过后, W68 第 13 批 grand closure memory 应记录 "6 trigger 实跑 PASS, 0 regression, 锚点范式 165 守恒"
- 未来 W69+ 若扩展 trigger (e.g., UserPromptSubmit 切到只匹配 `/command` 而非任意 prompt), 测试脚本需同步加新 trigger 行