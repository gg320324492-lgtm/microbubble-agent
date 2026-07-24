# W68 第 12 批 C-1：MobileFileCommentsView tabsWithCounts 修复

> 日期：2026-07-24
> 路线：Mobile UX v3.2 续
> 锚点范式：第 152 守恒
> 范围：移动端组件修复、构建回归测试、计划状态收口

## TL;DR

W68 第 11 批 B-2 报告 `npm run build` 被
`web/src/views/mobile/MobileFileCommentsView.vue` 中重复声明的
`tabsWithCounts` 阻塞。W68 第 12 批 C-1 在独立分支中复核了完整源码，确认同一
`<script setup>` 作用域内存在两个完全相同的 `computed` 声明，而不是一个
composable import 与一个局部变量之间的命名冲突。

修复保留多行格式的唯一 `const tabsWithCounts`，删除重复的一行格式声明。
同时新增 `web/tests/e2e/mobile_build_validation.spec.js`，把项目规定的唯一生产
构建命令 `npm run build` 纳入 Vitest 回归门禁。计划文件的 Status 段在提交完成后
写入真实 commit hash。

## 事故表现

1. Vite 解析移动端评论页的 `<script setup>`。
2. 编译器在相同作用域发现第二个 `const tabsWithCounts`。
3. 构建阶段报 `Identifier 'tabsWithCounts' has already been declared`。
4. `web/tests/e2e/mobile_drive_comments.spec.js` 的组件测试并不能替代完整生产构建。
5. 因为生产构建失败，移动端 v3.2 相关改动无法进入部署验证链。

## 根因核验

本次没有根据 B-2 报告中的“大概率 import 冲突”直接猜修，而是执行了完整核验：

- `grep` 搜索 `web/src/` 中所有 `tabsWithCounts` 声明与使用。
- 发现移动端文件第 225 行和第 227 行各有一个 `const` 声明。
- 第 225 行是一行式 `computed`。
- 第 227-229 行是同一逻辑的多行式 `computed`。
- 两个声明都引用同一个 `tabs`、同一个 `tabBadgeCounts`，逻辑和作用域完全重叠。
- `git blame` 显示两个声明由同一历史提交 `0774809553` 一起引入。
- 因此真实根因是旧提交内同段重复，而不是导入来源不明。

最终 `grep -rn` 结果只保留：

```text
web/src/views/mobile/MobileFileCommentsView.vue:225:const tabsWithCounts = computed(...)
web/src/views/desktop/DesktopFileCommentsView.vue:231:const tabsWithCounts = computed(...)
```

桌面端声明属于另一个组件作用域，不是重复声明，也没有修改。

## 实施内容

### 1. 组件修复

文件：`web/src/views/mobile/MobileFileCommentsView.vue`

保留的实现采用多行格式，便于后续审查：

```js
const tabsWithCounts = computed(() =>
  tabs.map((t) => ({ ...t, count: tabBadgeCounts.value[t.name] || 0 })),
)
```

删除了同一段之前的一行式重复实现。没有改动 `tabs`、badge 计数逻辑、tab 切换
行为或任何桌面端路径。

### 2. 构建回归测试

文件：`web/tests/e2e/mobile_build_validation.spec.js`

测试从 Vitest 的 `web/` 工作目录运行 `npm run build`，并断言：

- 没有 spawn error。
- 没有被 signal 中断。
- 进程退出状态为 0。
- 失败时保留 stdout/stderr，便于 CI 直接定位构建错误。
- Windows 使用 `npm.cmd`，Unix 使用 `npm`；若存在 `npm_execpath` 则复用当前 Node CLI。
- 构建超时设为 240 秒，测试超时额外保留 10 秒诊断窗口。

测试使用 `process.cwd()` 作为 `web/` 根目录。最初尝试从 `import.meta.url`
推导路径时，Vitest/jsdom 将 URL 转换为非 `file:` scheme，导致测试套件在收集
阶段失败；该测试基础设施问题已修正，不涉及生产代码。

## 验证记录

### 重复声明搜索

- 修复前：移动端组件 2 个 `const tabsWithCounts`。
- 修复后：移动端组件 1 个 `const tabsWithCounts`。
- 桌面端组件：独立保留 1 个同名局部 computed，属于不同文件/作用域。

### 生产构建

执行：

```bash
cd web
npm run build
```

结果：通过，exit code 0。

构建输出中仅有既有依赖/样式警告，例如 Sass `@import` 弃用、组件名称冲突和
Lightning CSS 对历史 `:deep` 写法的提示；没有 Vue 编译错误，没有重复声明错误，
postbuild manifest 健全性检查也通过。

隔离 worktree 初始没有 `node_modules`，首次直接执行构建时得到 `vite` 不存在。
按 `web/package-lock.json` 执行 `npm ci` 后重跑，构建成功。依赖安装产生的
`node_modules` 未纳入提交。

### 新增回归测试

执行：

```bash
cd web
npx vitest run tests/e2e/mobile_build_validation.spec.js
```

结果：`Test Files 1 passed`，`Tests 1 passed`。

该测试实际再次执行生产构建，因此不仅检查静态文本，也覆盖 Vite/Rollup 完整模块图
和 postbuild manifest 流程。

## 三条新铁律

### 铁律 1：重复声明必 grep

任何 agent 修改 Vue `<script setup>` 后，提交前必须对目标目录执行声明搜索，至少
覆盖 `const`、`let`、`var` 和 import/export 同名项。不能只看 diff 的新增行，必须
查看完整文件和同名跨文件结果。重复声明优先确认真实作用域和历史来源，再决定删除
或改名。

### 铁律 2：build 必过

组件单测通过不等于生产构建通过。任何影响 `web/src/` 的前端分支，在提交前必须
执行仓库规定的 `npm run build`，不能用 `vite build` 替代，因为 postbuild manifest
处理是生产链的一部分。构建失败时不得提交 dist 作为“验证通过”的替代品。

### 铁律 3：跨 agent 派工前提必核老路径

并行 agent 派工前，主指挥和 agent 都必须核验当前 main/基线中的老路径状态，尤其是
前一 agent 报告中的阻塞文件。派工描述不能默认“新增功能无旧问题”；应先使用
`git status`、目标文件全文、`grep` 和必要的 `git blame/log` 建立基线。后续 agent
必须把基线问题与自身交付分开，避免把已有重复声明误归因到另一 agent 或混入无关
分支。

## 变更边界

- 仅修改一个移动端生产组件中的重复声明。
- 新增一个构建回归测试文件。
- 更新仓库外计划文件 Status 段。
- 新增本 memory 沉淀。
- 未修改后端、数据库迁移、桌面端组件或安全基础设施。
- 未合并分支；由主指挥负责后续 merge。

## 交接检查

主指挥 merge 前应确认：

1. 分支名称为 `fix/w68-12th-batch-c1-tabsWithCounts-2026-07-24`。
2. 提交消息末尾包含 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。
3. `git diff --check` 无空白错误。
4. 计划 Status 段引用真实 commit hash，而非同 wave 其他任务 hash。
5. merge 后再次运行 `grep` 和 `npm run build`。
6. 不要提交本地 `node_modules` 或构建过程产生的 dist 漂移。

## 结论

C-1 的阻塞根因已闭环：同一文件同一作用域中的重复 `tabsWithCounts` 已降为单一
声明，生产构建与专门回归测试均通过。此修复保持 Mobile UX v3.2 行为不变，并将
“声明核验 + 生产构建 + 跨 agent 基线核对”固化为后续移动端派工的前置门禁。
