# W71 第 1 批 C-3 — claude-code notify v2 仓库模板回测

**锚点范式**: W68 第 14 批 175 → **W71 第 1 批 176 守恒预测** (实际收束待主拍 verify).

**作者**: Agent W71-1st-C-3
**commit**: `1fbdb5405` (chore/w71st-batch-c3-notify-regress-2026-07-24, 2026-07-24)
**report**: [docs/claude-code-notify-v2-regression-test-2026-07-24.md](../../.worktrees/agent-w71st-c3-notify-regress/docs/claude-code-notify-v2-regression-test-2026-07-24.md) (296 行, 6 段)
**worktree**: `E:/microbubble-agent/.worktrees/agent-w71st-c3-notify-regress`

## 派工

- **plan**: `C:/Users/pc/.claude/plans/claude-code-notify-system-2026-07-24.md` (W68 第 11 批 plans 闭环创)
- **W68 第 13 批 B-1**: 仓库模板实施 `c6932a946` (6 ps1 + settings.json.template + setup.sh)
- **W68 第 14 批 B-4**: 验证文档 `f0c373663` (`docs/claude-code-notify-system-v2-2026-07-24.md`)
- **W71 第 1 批 C-3 (派生)**: 真跑 `--dry-run` + 6 trigger 静态回测, 给主拍信心数据

## 6 Trigger 全部 6/6 PASS

| Trigger | Mode | Wrapper | Matcher |
|---------|------|---------|---------|
| Stop | --mode stop | stop.ps1 | * |
| UserPromptSubmit | --mode prompt | prompt.ps1 | * |
| Notification | --mode notify | notify.ps1 | * |
| PermissionRequest | --mode perm | perm.ps1 | * |
| SessionStart | --mode session | session.ps1 | * |
| PreToolUse | --mode tool | tool.ps1 | Bash (仅 Bash) |

## 核心发现

1. **PS 5.1 参数风格铁律复用** — 6 wrapper 全部 `--mode <name>` 空格分隔, 不用 `--mode=stop` (CLAUDE.md commit `79305b7` + W68 第 12 批 B-4 历史教训沉淀)
2. **错误防御铁律** — 6 wrapper 全部 `exit 0` + `$ErrorActionPreference = "Continue"`, hook 失败不污染 Claude Code 行为
3. **mismatch 风险点** — PreToolUse matcher=`Bash` 仅匹配 Bash, 其他工具不触发 (避免噪音), 与其他 5 trigger matcher=`*` 区分
4. **env 透传** — `MNB_VOICE_ALERT_PROJECT_DIR` env 透传给 wrapper, 项目脚本优先 (XiaoxiaoNeural 高质量) → SAPI 降级兜底

## setup.sh 4 模式

| Mode | 行为 | 退出码 |
|------|------|--------|
| --dry-run (默认) | 模拟不改系统 | 0 |
| --apply | 复制 6 wrapper + 合并 hooks 块 (备份 settings.json) | 0 |
| --verify | 检查 6 wrapper + 6 hooks 现状 | 0 |
| --rollback | 恢复 backup + 删 6 wrapper + 清 state file | 0 |

其他退出码: 1=invalid args / 2=missing template / 3=jq missing / 4=user declined.

## 限制

- 本回测仅 --dry-run 真跑, --apply / --verify / --rollback 未实跑 (以免污染生产 settings.json)
- 6 trigger 运行时真触发未验证 (需 test sandbox 启动 Claude Code session)
- 跨平台未验证 (仅 Git Bash)

## 推荐后续 (主拍决策)

- **W71 C-4** (建议): test sandbox 真跑 --apply + 实测 6 trigger 真触发
- **W72** (建议): 跨平台验证 (Linux / WSL / Windows native cmd)

## 派工 v6 铁律守恒

1. partial diff 已 commit (本任务派工前 working tree 干净, 无须 commit)
2. 不动 v1-v6 历史约束
3. 0 production code 改动铁律 (纯 docs 新增)
4. 6/6 PASS 必含 (派工 v4 铁律 5)
5. 1 commit + defer message
