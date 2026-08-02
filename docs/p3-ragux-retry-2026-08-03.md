# P3-RAGUX retry: KnowledgeRefBlock 4 段增强

日期：2026-08-03

分支：`chore/p3-ragux-retry`

锚点：`W100 +33`（re-pushed）

## 1. 结果

重派任务已在当前 main 基线重新完成。启动调研确认：

- retry worktree 初始为 clean，HEAD 与 `origin/main` 同为 `8e54d538d`。
- 旧目录 `E:/agent-p3-ragux` 已不存在。
- 旧 commit `b63d96ddeab5430ce8781f481eb2e953c2553b64` object 仍可读，但 `git branch --all --contains` 无输出，说明无 ref 保护。
- 本轮不直接恢复旧 commit；将旧 spec/实现与 W101 a11y main 基线合并后重新提交并推送，remote ref 保留到主拍确认。

## 2. 四段增强

### 2.1 相关度和类别

- score ≥ 80%：绿色 evidence rail 与绿色 badge。
- 60% ≤ score < 80%：黄色 rail 与 badge。
- score < 60%：灰色 rail 与 badge。
- 缺失 score：neutral 灰色，不显示错误数字。
- `research`、`experiment`、`review`、`paper`、`thesis` 映射五种图标；未知类别回退文件夹图标。

### 2.2 排序

- 顶部下拉包含 `score_desc`、`date_desc`、`category`。
- 默认按相关度降序。
- 类别相同时按相关度降序作为稳定次序。
- 使用 `localStorage` 键 `kb_ref_sort` 持久化；非法值回退默认值；存储不可用时 best-effort 降级。

### 2.3 详情交互

- 桌面端 `mouseenter` 后 300ms 显示右侧详情面板。
- 离开引用块会取消待执行 timer 并关闭面板；组件卸载时清理 timer。
- 详情包含摘要、关键实体、关联知识、收录时间。
- 移动端 tap 使用 `ElMessageBox` modal；确认主动作后进入知识详情，关闭则留在对话。
- `prefers-reduced-motion` 下禁用入场动画和 transition。

### 2.4 标准路由

桌面、移动、鼠标和键盘入口全部统一到：

```text
/knowledge/:id
```

ID 通过 `encodeURIComponent` 编码。旧实现中的移动端 `/knowledge?tab=detail&id=...` 不再使用。

## 3. 兼容边界

保留以下已有能力：

- `citations` prop 与 W99-RAG-2 `char_range` 高亮。
- snippet tooltip。
- `role=list`、`role=listitem`、`tabindex=0`、Enter/Space 激活。
- heading role 与 `aria-level=3`。
- 现有暖橙珊瑚 token、dark mode token、focus token。

未修改后端、API、数据库、alembic、RichContent 折叠逻辑或块注册表。

严格按 W67 的定义，`web/src` 属于 production code；因此本轮不能声称字面意义上的“0 production code”。据实口径是：仅修改 1 个任务授权的前端 production component，0 个后端或老核心文件，另新增 1 个专项测试。该授权例外不外扩。

## 4. 验证

| 项目 | 实测 |
|---|---|
| P3-RAGUX 专项 | 30/30 PASS |
| W101 a11y 回归 | 6/6 PASS |
| 合并执行 | 36/36 PASS |
| stylelint（目标组件） | PASS，0 error |
| `npm run build` | PASS，Vite 8.42s |
| postbuild | PASS，PWA disabled 分支完成 |
| Alembic | 单 head：`096_add_rag_multimodal_metrics` |
| `git diff --check` | PASS |

构建仅作验证。由于 `web/dist` 旧快照受版本控制、而新 hash 文件被 ignore，本轮构建后恢复了 HEAD 的 tracked dist，避免把无关 bundle 删除和 hash churn 带进 feature commit。

## 5. 五件套

1. Alembic：1 head，PASS。
2. 测试：30/30 专项 + 6/6 兼容，PASS。
3. 前端 build：`npm run build` 与 postbuild，PASS。
4. 边界：1 个授权前端组件 + 1 个专项测试；0 后端、0 migration、0 RichContent/registry 改动。
5. 锚点：单 commit，`W100 +33`，re-pushed。

## 6. 类 20.137-140 账本冲突

旧提交 memory 曾把本任务四条经验编号为类 20.137-140，但当前 `origin/main` 已由 W101 P3-A11Y 正式占用同一编号。为避免覆盖主线账本，本 runbook 采用双重记录：

- main 权威含义保持不变：类 20.137-140 仍指 W101 a11y 调研、focus token、skip-link 和 list/listitem 纪律。
- P3 旧 memory 的四条证据作为“旧孤儿提交中的同号记录”保留引用，不宣称重新分配编号。
- 本轮新增事实：孤儿 commit object 可读不代表可 merge；重派必须重新落 ref，并在 push 后保留 remote branch 到主拍确认。

## 7. 文件

- `web/src/components/chat/blocks/KnowledgeRefBlock.vue`
- `web/src/components/chat/blocks/__tests__/KnowledgeRefBlock.p3-ragux.test.js`
- `memory/p3-ragux-retry-2026-08-03.md`
- `docs/p3-ragux-retry-2026-08-03.md`

## 8. 合并与清理

本 agent 只推送 `origin/chore/p3-ragux-retry`。不删除 remote ref，不清理 worktree。主拍合并 main、执行内部 build 并确认 GitHub 后，才能另行清理。
