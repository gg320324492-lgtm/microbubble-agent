# DL-6 执行报告：发送 UX 乐观上屏 + 下架实验 ELN/稿件（2026-09-29）

## 结论

Part A 三件套单测 + 真实渲染瞬间态截图验收通过；Part B 用户可见面全删、DB 零改动、兜底扫描清零（保留项逐处说明）。`pnpm gate` **72 文件 760/760 全绿**（typecheck 0 / build 0）。待总指挥复核。

## 基本信息

- **实际 HEAD**：接单时 `76382ddaf`（工单基线 v1.3.0 74140c7bb 之后总指挥轨推进）；执行中途基线被并行会话推进到 `7515f0991`（安全加固,与本单无文件交集）；**交付 commit `28ac6ed1b`**（post-commit hook 已推 origin）+ CHANGELOG 草稿 `3156f310d`
- **测试计数**：788 → **760**（−32 = 删 experiment.service.test 16 + manuscript.service.test 16；+4 = 新增 dl6-send-ux.test 三件套+场景 2）
- **改动规模**：23 文件 +197/−2900

## Part A：发送 UX 乐观上屏

改动（渲染层最小修复,IPC 契约零变化,`sending` 门控/滚动跟随 JS 零改动）：

1. `ChatPanel.vue onSend`：校验通过**即** `draft.value = ''`（原在 `await store.send` 之后——CHAT_SEND 悬置数秒~分钟,草稿滞留到生成结束）；catch 仅当输入框仍为空才回填 `text`
2. `stores/chat.ts send()`：await 前乐观上屏临时用户消息（`temp-` 前缀,与主进程 `m-` 前缀不冲突,类型按 `ChatMessage`）；成功按引用 `indexOf` 原位替换为 `result.userMessage` 再追加 assistant；失败移除临时条目再抛错,无 temp 残留

验收（单测 `tests/unit/dl6-send-ux.test.ts` 4 用例 + 真实 Electron 渲染,截图 `assets/2026-09-29-DL6/`）：

- `a-sending-instant.png`：主进程侧 `removeHandler('chat:send')` 后注册 8s 延迟伪造响应（模拟真实模型悬置）,发送「你好」1.5s 时截图——**草稿已空、用户气泡已上屏、按钮「发送中…」**,数值断言 draftValue=""/msgCount=1/msg-user
- `a-after-replace.png` + 数值：悬置结束后 msgCount=2（真实 user 消息替换 + AI 回复追加）
- 失败路径由单测覆盖（挂起后 reject：临时条目移除 + 草稿回填；期间新输入不被覆盖）

测试备注：场景 2「生成期间新输入保护」中,生成期间 textarea 处于 disabled（现状门控,本单不改）,jsdom 下 test-utils setValue 的 input 事件到不了 v-model,测试改用手动 `dispatchEvent` 模拟；真实浏览器中 disabled 输入框本无法打字,该守卫为纵深防御（工单明示要求）。

## Part B：下架两模块（逐处摘除清单）

**渲染层**：router 2 条路由；SideNav 2 项 + flask/doc 两个死图标分支（仅两模块使用）；App.vue 命令面板 4 条（nav-eln/nav-manuscripts/new-experiment/new-manuscript）；`views/ExperimentView.vue`、`views/ManuscriptsView.vue` 整删（grep 反向依赖确认自包含、无独占组件）；app.css M7 注释枚举同步摘除两模块名

**主进程**：`ipc.ts` 服务装配 2 块 + handler 块 222 行（EXPERIMENTS_* 9 + MANUSCRIPTS_* 10 通道）+ 4 处 import；`services/experiment/`、`services/manuscript/` 目录删除；`cloud-identity.ts` CLAIMABLE_TABLES 摘 `{manuscripts,稿件}`、`{experiments,实验}` 两行——**摘除点仅此清单尾部两行,planClaim/claimSummary/beforeClaim 认领前备份安全网全部未动**（摘除语义：下架模块的历史行不再参与认领,数据原地冻结,无 UI 可读,风险为零）

**shared/preload**：ipc-channels 19 通道常量；preload-api imports 13 类型 + manuscripts/experiments 两个 API 块；types.ts 两大类型区块（Experiment* 7 + Manuscript* 8）；preload/index.ts imports + 2 个实现块

**数据库（红线遵守）**：`db/migrations.ts` 迁移 8（experiment-notebook）/9（manuscript-library）**原样保留**,零 schema 改动。保留的表：`experiments`、`experiment_files`、`experiments_fts`、`eln_counters`、`manuscripts`、`manuscript_files`、`manuscripts_fts`——历史数据原样在库,日后恢复随时可行

**测试**：整删 2 文件（16+16 用例）；layout-scroll 摘两被删视图行（测试标题改中性表述「在役列表型模块」）；command-palette.dom 与 desktop-command-registry 的 fixture 由 `nav-eln/实验 ELN` 换为 `nav-drive/网盘`（机制断言意图不变,拼音首字母过滤用例 'sy'→'wp' 同构替换）；theme-regression SideNav 断言 7→5 随实际（describe 标题同步）。与两模块无关的断言零触碰

## 兜底扫描结论（保留项逐处理由）

`grep -rn "experiment|Experiment|manuscript|Manuscript|实验|稿件" src/ tests/` 清零后余以下命中,全部有意保留：

1. `db/migrations.ts` ×13：迁移定义,红线禁止动
2. `backup.service.ts FILES_SUBDIRS = ['knowledge','meetings','experiments']`：**保留 'experiments'**——三个消费循环均有 `existsSync→continue` 容错,保留使历史实验附件继续随备份打包/恢复,摘除反而是数据丢失向量,违背「数据零破坏」
3. `backup-core.test.ts` / `zb-cloud-attachments.test.ts` 的 experiments 命中：即第 2 条保留行为的测试载体,行为未变故断言不动
4. `knowledge.service.test.ts` / ChatPanel 建议语 / LoginView / SetupView / cloud/drive.ts 注释等中文「实验/稿件」：自然语言,非模块引用
5. `workspace.service.ts:30`「实验数据只增不改」：Agent 系统提示词通用数据安全规则,红线明确不动
6. `ComingSoonView.vue` 头注释提及 ELN/稿件：该组件为**既有无引用孤儿**（本单前路由已不指向它）,与本两模块无代码关联——不顺手扩删,报备总指挥另行处置

## 透明度说明

1. **执行事故**：首轮全部改动完成、gate 通过后、截图前,父仓库被并行会话推进（`7515f0991` 安全加固）且工作树未提交改动被清空。全部改动按记录重做,并吸取教训：**gate 通过后立即提交**（修复 commit `28ac6ed1b` 先于截图落库）。重做后 gate 与验收全部独立复跑通过
2. **SideNav flask/doc 图标分支**：工单清单未点名,但两模块下架后即成死代码（无任何 item 使用）,属「仅被两视图/模块引用」范畴,已随导航项一并摘除
3. **ui13-chat-follow.test.ts 未动**：其断言（三行网格/仅主体可滚）与 Part A 改动正交
4. **ipc-consistency.test.ts**：通道/类型/preload 三方一致性守卫,随摘除自动通过,零修改

## 验收证据索引（assets/2026-09-29-DL6/）

- `a-sending-instant.png`：发送后瞬间态（Part A 核心证据）
- `a-after-replace.png`：悬置结束后替换+追加完成态
- `b-sidebar-5items.png`：侧栏五项（AI 助手/知识库/网盘/会议/设置,数值断言 `navItems` 一致）
- `b-palette.png`：Ctrl+K 命令面板 7 条,零两模块条目;「实验」过滤为空（数值断言 `paletteFilterShiyan: []`）
- `report.json`：全部数值断言;`dl6-e2e-driver.mjs`：验收驱动脚本（可独立复跑）
