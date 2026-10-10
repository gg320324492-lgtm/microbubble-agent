# 工单 R-1：v0.1.0-alpha 发布（打磨五项 + 打包 + GitHub Release + CHANGELOG 定稿）

> 签发：总指挥 · 2026-09-17
> 上游：C-1 / C-2 / C-3 全部验收通过，**M1-C 闭环**；测试基线 **100** 条全绿
> 决策依据：R1（GitHub 发布 + 每版记录迭代信息，用户拍板）/ R2（首版节点 = M1-C 完成后）
> 发布目标仓库：父仓库 origin = `github.com:gg320324492-lgtm/microbubble-agent`（桌面端代码在 `apps/desktop`）

## 你的任务背景

「小气 · 科研工作台」桌面端完成第一个可用里程碑闭环：本地账号 + 三栏工作台 + 模型网关（MiMo Anthropic 协议）+ Agent 工作区读写全链路（围栏/只读工具/ReAct 循环/Diff 确认/备份回滚/审计）。本工单把它变成**第一个可安装、可发布的 alpha 版本**。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖（electron-builder 打包链 M0 已就绪；若发现缺失/损坏，**停下报告**，不得擅自加依赖）
4. 完成门禁：`pnpm test` 全绿（当前基线 **100** 条，需新增 ≥8 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. **发布动作边界（重要）**：tag 可推送；GitHub Release 只建 **draft 不 publish**——正式发布由总指挥真机验收后亲自执行（外发动作留人）

## 交付物

### 0. 先落盘真机验收 hotfix（独立 commit，先做）

父仓库工作树有一处未提交改动：`apps/desktop/src/renderer/src/components/chat/ToolCard.vue`——C-3 真机验收发现回滚按钮不显示，修复为 props 补声明 `interactive?: boolean` 并把回滚条件从 `live` 改为 `interactive`。
- 先跑 `pnpm test`：若既有「回滚按钮可见性」用例按旧 `live` 语义挂载，把该用例改为 `interactive` 语义后修正断言
- 单独提交：`fix(desktop): ToolCard 声明 interactive prop — 真机验收修复回滚按钮不显示`

### 1. 打磨五项（产品池转正，均为小改）

1. **Key 失效引导重填**：模型服务卡片增加「Key 失效」状态与一键重填入口（触发源：网关报 key 解密失败——真机已实际发生过，用户只会看到一句报错，无处重填）
2. **清除工作区按钮**：设置页工作区区块增加「清除」，回到未设置态，顶栏降级徽标联动恢复
3. **轮次进度呈现**：循环进行中显示「第 N/15 轮」轻量进度（live round 事件与 meta.rounds 数据均已存在）
4. **确认倒计时**：工具卡片确认态显示 5 分钟倒计时（纯展示；超时自动按拒绝的语义已有）
5. **回滚二次确认**：点击「回滚此写入」弹确认文案，提示将覆盖文件当前内容（Element Plus MessageBox 即可）

打磨项要求：每项有对应组件/服务测试；不引入新 IPC 通道（① ② 走现有 settings/provider 通道扩展即可，如需新通道则三处白名单同步）。

### 2. 版本号与 CHANGELOG 定稿

- `apps/desktop/package.json` version → **`0.1.0-alpha`**
- 新建 `apps/desktop/CHANGELOG.md`，以以下为底稿、补充「打磨五项」与发布条目（今后每版在此累积）：

```markdown
# CHANGELOG — 小气 · 科研工作台 桌面端

## v0.1.0-alpha（2026-09-17）

### Agent 工作区读写全链路（首个 alpha）
- **[C-3] Agent 写能力：Diff 确认 + 备份回滚**（`84ba0be4c`）
  新功能：`write_file` / `delete_file` / `mkdir` 三个写工具；写操作前行级 Diff 确认面板
  （新增绿/删除红，200 行截断）；覆写自动备份 `.agent-backups/` + 卡片一键回滚；
  删除移入系统回收站（绝不物理删除）；拒绝意见回喂模型以便改道；写操作全程审计留痕
  已知问题：确认面板 5 分钟无响应自动按拒绝；目录级删除暂不支持；回滚依赖本机备份
- **[C-2] ReAct Agent 循环：原生工具调用 + 思维链展示**（`08184aa0f`）
  新功能：多轮「思考→调工具→看结果→再回答」（上限 15 轮）；工具卡片状态流转可展开；
  思考过程折叠面板；工具调用与思维链随会话持久化还原；设置页近 20 条审计
  修复：真实模型流式回复无法逐字上屏的消息事件匹配缺陷
  已知问题：未设工作区时工具不可用（有降级提示）；OpenAI 协议暂不支持工具调用
- **[C-1] 工作区地基：围栏 + 只读工具 + 审计**（`220f624e8`）
  新功能：工作区（GitHub 仓库根）设置与围栏保护（.git 禁区/符号链接逃逸防护）；
  `list_dir` / `read_file` / `glob` / `grep` 只读工具；设置页工作区区块与审计
- **打磨**：Key 失效引导重填 / 清除工作区 / 轮次进度 / 确认倒计时 / 回滚二次确认
- **基础**（M0/M1-A/M1-B）：无边框窗口 + 本地账号（scrypt/safeStorage）+ 三栏工作台 +
  会话本地持久化 + OpenAI/Anthropic 双协议流式网关 + Provider 管理
- **已知问题（总）**：未签名安装包（SmartScreen 会警告）；更新通道未接入（M6）
```

### 3. 打包

- electron-builder：NSIS 安装包（`oneClick: false`，安全基线），未签名可接受
- 产出三件套：`.exe` + `latest.yml` + `.blockmap`（同版本一致），记录产物路径与大小
- 打包冒烟：启动安装后的应用，确认进入「创建管理员账号」首启页（打包版 userData 全新，**不复用 dev 库数据属正常首启体验**）；随后卸载清理本机安装

### 4. 发布准备（draft，不 publish）

- `git tag v0.1.0-alpha` 并推送 tag
- 用 `gh` 创建 draft release：`gh release create v0.1.0-alpha --draft --title "v0.1.0-alpha" --notes "<CHANGELOG 本版内容>"`，上传三件套
- `gh` 不可用则把 release 标题/正文/产物路径整理进交付报告，由总指挥手动发

## 定义完成（全部满足才算完）

- [ ] hotfix 已单独提交；工作树干净（`git status --short` 自证无保护路径改动）
- [ ] 门禁全过：test 100 + 新增 ≥8、typecheck 0 错、build 成功、electron-builder 产出 exe
- [ ] 打磨五项完成且各有测试
- [ ] CHANGELOG.md 定稿；tag 已推送；draft release 已建（或 gh 不可用已报告）
- [ ] 交付报告附「总指挥真机验收清单」

## 交付报告格式

1. 变更/新增文件清单（路径+行数）
2. 门禁输出尾部（含打包产物路径与大小）
3. commit hash 列表（hotfix + 主提交）+ tag 名
4. 打磨五项自测记录表
5. draft release 链接与正文、上传产物清单
6. 遗留问题 / 对 M2 的建议
7. CHANGELOG v0.1.0-alpha 最终文本
