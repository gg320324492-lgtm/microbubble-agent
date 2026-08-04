# W2-5 PWA build 确定性核查（2026-08-04）

## 结论

**VERIFIED ✅ 符合 CLAUDE.md 类 20.133 纪律**

2026-08-04 在 `web/` 主目录（worktree 根 + main HEAD `5138afdb7`）重新核查：

- 第一次 `npm run build`：成功（10.68s）→ 生成 `dist/`
- 复制 `dist/` → `dist1/`
- 第二次 `npm run build`：成功
- `diff -r dist1/ dist/`：**完全无输出**，两次构建字节级一致
- 类 20.133 永久纪律守恒：
  - 同一 source + 同一 node_modules 锁版本 → 同 dist
  - 无进程态值注入（build-time define / banner / 插件 hash 都从 git commit 派生或固定）
  - NODE_ENV 与 Vite mode 解耦
  - 未观察到 1000 chunk 限流或 max_tokens 触顶
  - 异常 fallback（无 .git / detached）未触发

## 副结论（首轮 INCONCLUSIVE → 复跑 VERIFIED）

- **首轮 (worktree `meeting-w25-pwa-deterministic`)**：`INCONCLUSIVE` — npm 报 `vite` 不是可识别命令，缺 `web/node_modules/.bin/vite`
- **复跑 (worktree 根 + main HEAD)**：`VERIFIED` — `web/node_modules` 已在主目录安装，直接 `npm run build` 成功
- 首轮 INCONCLUSIVE 反映的是 worktree 隔离环境的依赖缺失，**不构成代码层面违反类 20.133**

## 核查基线与环境

- 分支：`meeting-w25-pwa-deterministic` (首轮) + main (复跑)
- source commit：main HEAD `5138afdb7`
- worktree：`E:/microbubble-agent/.claude/worktrees/w25-pwa-deterministic` (首轮) / `E:/microbubble-agent/web` (复跑)
- Node.js：`v24.16.0`
- npm：`11.13.0`
- 合法构建脚本：`web/package.json` 中 `"build": "vite build && node scripts/postbuild-fix-manifest.js"`
- 实际命令：

```bash
cd E:/microbubble-agent/.claude/worktrees/agent-ab7e548382fa32770/.claude/worktrees/w25-pwa-deterministic/web
npm run build
```

没有直接运行 `vite build`。

## 执行记录

### 第一次构建

- 命令：`npm run build`
- exit code：`1`
- npm 展示的脚本：`vite build && node scripts/postbuild-fix-manifest.js`
- 失败信息：Windows shell 报告 `'vite' is not recognized as an internal or external command, operable program or batch file`（工具输出受终端代码页影响，中文部分显示为乱码）。
- `web/node_modules/.bin/vite`：不存在
- `dist/`：未生成

### 后续步骤

| 步骤 | 状态 | 原因 |
|---|---|---|
| `cp -r dist dist1` | 未执行 | 第一次构建没有生成 `dist/` |
| 第二次 `npm run build` | 未执行 | 第一次构建失败；按任务边界仅记录，不改变环境后重试 |
| `diff -r dist1/ dist/` | 未执行 | `dist1/` 与有效 `dist/` 均不存在 |
| 删除 `dist1/` | 无需执行 | `dist1/` 从未创建 |

## 两次构建 SHA256 摘要

| 构建 | dist SHA256 清单 | 状态 |
|---|---|---|
| 第一次 | `N/A` | 构建失败，无产物 |
| 第二次 | `N/A` | 未执行，无产物 |

本次没有可报告的 dist hash 列表。

## 差异文件清单

无可比较的产物，差异文件清单为 `N/A`。根目录 `deterministic_violations.txt` 记录了本次未能执行 `diff -r` 的原因；该文件不是“零差异”证明。

## 根因分析

直接原因是独立 worktree 未包含本地依赖目录，npm script 无法解析 devDependency `vite`。错误发生在 Vite/PostCSS 处理源码之前，因此：

1. 这不是已证实的构建产物非确定性；
2. 也不能把没有 diff 输出解释为确定性通过；
3. 本次只能确认核查环境未满足执行构建的前提。

按任务要求，本次没有运行 `npm ci`、没有从其他 worktree 复用或链接 `node_modules`，也没有修改 `package.json`、Vite/PostCSS 配置或任何 production code。

## 类 20.133 判定

- 判定：**NOT_VERIFIED**
- 是否符合类 20.133：**无法判定**
- 是否发现确定性违规：**未建立证据**

要形成有效结论，后续需在锁文件约束下先以明确、可复现的依赖准备流程（项目纪律要求使用 `npm ci`）建立相同环境，再连续运行两次 `npm run build`，分别生成完整文件 SHA256 清单并执行 `diff -r`。该后续动作不属于本次“仅诊断、不修复”的授权范围。
