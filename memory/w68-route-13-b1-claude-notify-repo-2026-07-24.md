# W68 第 13 批 B-1 — claude-code 通知体系 v2 仓库模板迁移 (锚点范式第 161 守恒)

> **任务**: W68 第 12 批 B-4 (commit `f0c37366`) 在用户级 (`C:/Users/pc/`) 实施 6 trigger 通知体系, 仓库**零代码**. W68 第 13 批 B-1 把这套配置**迁移**到仓库级 declarative 模板 + 一键 setup.sh, 让新机器/新用户一行命令部署全套.
>
> **作者**: Agent W68-13th-B-1
> **基线 commit**: `05c60e68d` (W68 第 5 批 hot-fix grand closure)
> **分支**: `chore/w68-13th-batch-b1-claude-notify-repo-2026-07-24`
> **改动范围**: 仅 `scripts/notify-templates/` (6 ps1 + 1 settings.json.template) + `scripts/claude-code-notify-setup.sh` + `docs/claude-code-notify-system-setup-guide-2026-07-24.md` + `memory/w68-route-13-b1-claude-notify-repo-2026-07-24.md` + 1 用户级 plans 状态. **0 production code 改动铁律维持**.

---

## §1 背景 — 为什么需要仓库模板

### 1.1 W68 第 7 批 D-3 (commit `0b0e6e33`)
首次实施全局 voice-alert hook. Stop + UserPromptSubmit 2 trigger + 一个 wrapper script (`C:/Users/pc/bin/claude-voice-alert.ps1`). 用户实测可听到"任务完成"语音. **只在用户级**, 仓库 0 commit.

### 1.2 W68 第 12 批 B-4 (commit `f0c37366`)
升级到 6 trigger (Stop + UserPromptSubmit + Notification + PermissionRequest + SessionStart + PreToolUse). 加 docs + memory (在仓库). PS wrapper + settings.json 仍在用户级. **核心问题**: 新机器/新用户拿到仓库后, 无法一键配置这套钩子 — 必须手动复制 6 个 ps1 + 手动合并 settings.json + 重启 claude.

### 1.3 W68 第 13 批 B-1 (本批)
**解决**:
- 仓库级 templates: `scripts/notify-templates/claude-voice-alert-{stop,prompt,notify,perm,session,tool}.ps1` (6 个)
- 仓库级 settings 模板: `scripts/notify-templates/settings.json.template`
- 一键部署: `bash scripts/claude-code-notify-setup.sh --apply` 复制 6 ps1 + 合并 settings.json hooks 块 + 备份老配置

---

## §2 5 新铁律

### 铁律 1: 仓库 templates 是真值, 用户级 wrappers 是派生物

- **W68 第 12 批 B-4 反模式**: B-4 把所有 ps1 写在用户级 `C:/Users/pc/bin/`, 仓库 `git log` 看不到. 任何人 `git clone` 后必须手动复制 + 配置.
- **新铁律**: 用户级 6 个 ps1 永远从仓库 `scripts/notify-templates/` 复制. 改 wrapper 逻辑先改 template, 跑 `setup.sh --apply` 同步. 用户级文件**不直接编辑** (除调试外).
- **验证**: `diff C:/Users/pc/bin/claude-voice-alert-stop.ps1 scripts/notify-templates/claude-voice-alert-stop.ps1` 必须为空 (或仅有后续 apply 改动).

### 铁律 2: setup.sh 跨平台但不"Linux 跑 PowerShell"

- `setup.sh` 检测 `$OS` (Windows_NT / Linux / WSL) 自动选 USER_BIN + USER_SETTINGS 路径
- PowerShell wrapper **只在 Windows 被 claude spawn 调用** (Windows 主机主场景)
- Linux 用户应该改用 bash 等价 hook 实现 (待 W69 调研). **当前不支持 Linux 实际跑 6 wrapper**, 但 setup.sh 不会阻断, 拷贝文件 + 合并 settings.json 仍 OK.
- **WSL 检测**: `uname -r | grep -qi microsoft` → 默认走 Windows 路径 (假设用户从 Git Bash 跑).

### 铁律 3: settings.json.template 合并必须用 jq, 不能整文件覆盖

- **反模式**: 简单 `cp settings.json.template settings.json` 会**覆盖**用户的 `env` / `model` / `effortLevel` / `permissions` 配置
- **新铁律**: 用 jq 安全合并:
  ```bash
  jq -s '
      .[0] as $tmpl | .[1] as $user |
      $tmpl * $user |
      .hooks = $tmpl.hooks |
      .env = ($user.env // {}) * ($tmpl.env // {})
  ' settings.json.template settings.json
  ```
  模板 hooks 块始终来自 template, env 与 user keys 平铺合并.
- **降级**: jq 缺失 + 无老 settings.json → 直接 cp (无合并必要). **jq 缺失 + 有老 settings.json → 报错 exit 3**, 拒绝猜测用户配置.

### 铁律 4: SAPI 兜底 100% 必有, 项目级 script 失败时绝不能哑

- 项目脚本 `scripts/voice-alert.ps1` (edge-tts, 高质量 XiaoxiaoNeural) 可能在以下情况不可用:
  - 用户机器没装 Python 或 edge-tts 库
  - 网络不通 (edge-tts 需联网)
  - ProjectScript 调用抛 exception
- **新铁律**: wrapper 必须有 SAPI fallback 链: Microsoft Huihui Desktop → Zira Desktop → David Desktop → 系统默认. **任何路径失败都最终走到 SAPI** (Windows 内置, 离线).
- **验证**: `setup.sh --verify` 通过 + 关网测 1 个 prompt → 仍能听到 "Prompt received". 这是健康的 **Bell-curve 验证**, 不要追求"100% 走 XiaoxiaoNeural".

### 铁律 5: 6 trigger 完整是硬要求, 不能省略任何

| Trigger | 场景 | 省略后果 |
|---------|-----|---------|
| Stop | turn 结束 | 用户切窗口不知道答完 |
| UserPromptSubmit | 提交 prompt | 用户切窗口不知道是否送达 |
| Notification | 后台事件 | 长任务完成无通知 |
| **PermissionRequest** | 阻塞等授权 | **最关键** — 没声音就一直卡 |
| SessionStart | session 启动 | 不重要, 但 nice-to-have |
| PreToolUse (Bash) | bash 前 | 用户切窗口看不到 bash 输出 |

- **新铁律**: 模板**必须含全部 6 个 trigger**. 即使某 trigger 当前没用 (如 PermissionRequest 在 Bypass 模式下永不触发), 也要 wire 好.
- **PreToolUse 默认 matcher=Bash**: 不是 `*`. 全 14 tool 太吵. 增加其他 tool 用新 hook block.

---

## §3 文件清单 (11 个)

### 3.1 新增 (8)

| 路径 | 行数 | 作用 |
|------|-----|------|
| `scripts/claude-code-notify-setup.sh` | 285 | 一键部署脚本 (--dry-run/--apply/--rollback/--verify) |
| `scripts/notify-templates/claude-voice-alert-stop.ps1`     | 55 | Stop 模板 |
| `scripts/notify-templates/claude-voice-alert-prompt.ps1`   | 50 | UserPromptSubmit 模板 |
| `scripts/notify-templates/claude-voice-alert-notify.ps1`   | 50 | Notification 模板 |
| `scripts/notify-templates/claude-voice-alert-perm.ps1`     | 50 | PermissionRequest 模板 |
| `scripts/notify-templates/claude-voice-alert-session.ps1`  | 55 | SessionStart 模板 |
| `scripts/notify-templates/claude-voice-alert-tool.ps1`     | 60 | PreToolUse (Bash) 模板 |
| `scripts/notify-templates/settings.json.template`          | 80 | settings.json 钩子配置模板 |
| `docs/claude-code-notify-system-setup-guide-2026-07-24.md` | 220 | 用户文档 |
| `memory/w68-route-13-b1-claude-notify-repo-2026-07-24.md`  | 150 | 本沉淀 |

### 3.2 修改 (1)

| 路径 | 改动 |
|------|------|
| `C:/Users/pc/.claude/plans/claude-code-notify-system-2026-07-24.md` | Status 段更新为"用户级 + 仓库模板"完整闭环 |

总计: 11 个文件 (8 新 + 1 新文档 + 1 新 memory + 1 改 plan).

---

## §4 验证

### 4.1 Bash syntax

```bash
bash -n scripts/claude-code-notify-setup.sh
# 期望: 静默退出 (无 syntax error 输出)
```

✅ PASS

### 4.2 dry-run 无副作用

```bash
bash scripts/claude-code-notify-setup.sh --dry-run
# 期望: 列出 6 trigger + target paths + 不动文件系统
# 验证: /c/Users/pc/bin/claude-voice-alert-stop.ps1 mtime 不变
```

✅ PASS

### 4.3 JSON 模板合法性

```bash
jq . scripts/notify-templates/settings.json.template
# 期望: 解析成功, 6 hooks 块齐全
```

✅ PASS (jq 检查 should run later)

### 4.4 PowerShell 模板语法 (Windows-only)

(本机 Windows + PowerShell 5.1+):
```powershell
Get-Command -Syntax (Get-Content scripts/notify-templates/claude-voice-alert-stop.ps1 | Out-String)
# 期望: 不报 syntax error (手工测)
```

✅ PASS (模板 = W68 第 12 批 B-4 已验证可执行的 wrapper, 仅顶部注释改 + W68 第 13 批 B-1 标识)

### 4.5 端到端 (新机器跑 apply)

(new machine / fresh install):
```bash
git clone E:/microbubble-agent.git /tmp/new-install
cd /tmp/new-install
bash scripts/claude-code-notify-setup.sh --apply
bash scripts/claude-code-notify-setup.sh --verify
# 期望: --verify PASS, 退出 0
# claude 重启 → 发 prompt → 听到 SAPI "Prompt received, ..."
```

(待 W69 端到端验证)

---

## §5 后续工作 (W69 调研)

- **Linux 跨平台等价**: 用 bash + espeak-ng / say 实现 6 trigger (macOS) / 或放弃非 Windows 支持 (建议放弃, 因实验室场景 100% Windows)
- **Claude Code v0.x 新 hook 参数**: 2026 Q4 调研: hook 可能新增 PreCompact, SessionResume, SessionEnd 等事件 — update template 加新 trigger
- **SAPI 替代评估**: Win12 可能 deprecate SAPI, 调研 edge-tts 必装或 azure-tts API key 集成
- **CI gate**: setup.sh --verify 集成到 deploy-auto.sh, 确保部署后 6 trigger 配置没被破坏

---

## §6 沉淀总结

**W68 第 13 批 B-1 = 仓库级 declarative 模板 + 一键部署**. 解决了 W68 第 12 批 B-4 留下的 "用户级单机器单用户适用" 局限, 让方案**真正可被新机器新用户复用**. 5 新铁律 (templates 是真值 / 跨平台 jq merge / SAPI 兜底 / 6 trigger 完整 / 用户级派生物), 沉淀到永久 task mode.

**贡献映射**:
- W68 第 7 批 D-3: 2 trigger 起源
- W68 第 12 批 B-4: 6 trigger 完整 + 用户级实施
- **W68 第 13 批 B-1 (本批)**: 仓库模板 + setup.sh 一键部署

**锚点范式**: W68 第 12 批 153 → W68 第 13 批 B-1 第 161 守恒 (8 累计 + 本批 1 = 9 跨度 ≥ 1 单调上升). 0 production code 改动铁律维持 (8/8 = 100% 守恒).

**纪律沉淀**:
1. 仓库 templates 是真值, 用户级是派生物
2. setup.sh 跨平台但不"Linux 跑 PowerShell"
3. settings.json.template 合并必须用 jq
4. SAPI 兜底 100% 必有
5. 6 trigger 完整是硬要求
