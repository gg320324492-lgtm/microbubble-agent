# 工单 M8-1：Agent P0 硬化（工具输出预算 + 提交边界重试 + 循环测试解耦）

> 签发：总指挥 · 2026-09-19 ｜ **激活：2026-09-20（基线已刷新）**
> 状态：**已激活，执行中**——激活基线：**431 条测试全绿**（R-9 关闭时实测）、HEAD `71e54858e`、typecheck 0 错
> 上游：决策 D9（对标 minimax-code，计划文档 `docs/plans/2026-09-19-agent-upgrade-plan.md` §1 #1/#2/#5）
> 允许额外读取（仅这两个文件，两个路径等价任选）：`packages/agent-tools/src/desktop/output-limit.ts` 与 `packages/agent-core/src/pi-turn-runner/llm-retry.ts`（MIT，参考模式用；如借鉴其代码结构须在报告注明出处）。本地副本：`C:\Users\pc\AppData\Local\Temp\refs\minimax-code\`（原始）或 `C:\Users\pc\.agent-refs\minimax-code\`（持久镜像，同名文件）

## 你的任务背景

我们的 Agent（agent-loop.service.ts + 8 工具 + ToolRegistry）已全链路落位，但对标 minimax-code 后确认三个 P0 短板，本单一并硬化：

1. **工具输出无预算**：read_file/grep 返回大内容会直撑上下文——需要字节预算 + UTF-8 整行截断 + **结构化续读协议**（让模型知道"怎么继续读"）
2. **LLM 调用零重试**：单轮失败就并文放弃——需要**提交边界重试**（首个可见 delta 之前透明重试，之后不重试防止重复内容）+ 错误归一化（中性文案，不泄漏原始报错）+ usage 四桶记账
3. **循环与传输耦合**：ReAct 循环直接吃 SSE 解析结果，无法离线穷举测试——需要解耦为**纯数据消息流 + 可注入时序**（编排式 mock），让中止/失败/重试全部可离线断言

技术栈约束同前：主进程服务与单测绝不 import 依赖 Electron ABI 的模块；本单**零新增依赖**（重试的 sleep/now 全部注入式）。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖（重试的 sleep/now/random 全部注入式，离线可断言）
4. 门禁：`pnpm test` 全绿（**激活基线 431 条**，需新增 ≥14 条 → 共 ≥445）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. 不改既定行为：围栏/审计/确认流/桌面集成/缩放锁定/更新通道等已验收行为零回归

## ⚠ 前车之鉴五项（交付前自查）

重启 dev 实测生效（附截图）/ fake 注入符号显式导入 / 报告归属与数字如实（tag↔commit 逐行核对）/ 勿动缩放锁定与桌面集成 / 变更文件清单必填

## 交付物

### 1. 工具输出预算 + 续读协议（`src/main/agent/tools/output-limit.ts` 纯函数 + 各只读工具接入）

- 预算：read_file 24KB、grep 16KB（UTF-8 **字节**预算，逐行贪心装入，绝不在多字节字符中间切断）
- 两种策略：`prefix_lines`（read_file 用）与 `head_tail_lines`（grep 用：头 45% + 尾 55% 整行保留）
- 截断后输出附加**结构化续读提示**（写入文本尾部，模型可见）：`[已截断：原 N 字节，已返回 M 字节。用 read_file 的 offset/length 参数从第 X 行继续读取]` 之类——让模型无需人类提示就知道续读方式
- read_file 支持 offset/length 参数（若无则新增），续读协议与之闭环

### 2. LLM 提交边界重试 + 错误归一化（`src/main/agent/llm-retry.ts` 纯逻辑 + 装配——与 `agent-loop.service.ts` 同目录）

- **提交边界语义**：流事件缓冲；出现首个可见 delta（text/thinking/toolcall）= 已提交 → 之后任何失败**不重试**（并入文继续，现行为）；未提交前的错误（429/5xx/网络/空响应）→ 丢弃缓冲静默重试
- 策略：最多 5 次；1s 起步指数退避 + 抖动；单次等待 30s 封顶；总时长 120s 封顶；**尊重 Retry-After 头**
- 错误归一化：枚举分类（rate_limited/overloaded/network/empty_response/invalid_request/…）→ 每类映射**对用户安全的中性中文文案**；原始报错只进日志不进对话
- sleep/now/random 注入式（离线可断言退避序列）
- 装配：包在网关 SSE 请求函数外层（对 agent-loop 透明）

### 3. 循环与传输解耦（重构 agent-loop.service.ts 的输入源）

- 把「SSE 解析结果」抽象为**纯数据消息流接口**，循环只消费纯数据（不感知 HTTP/事件解析）
- 由此新增**编排式 mock** 测试能力：手工编排消息序列（文本/工具调用/错误/中止）离线驱动完整循环
- 用该能力补测试：工具调用循环/中止（含中止时未执行工具的收尾）/失败并文/重试路径

### 4. 测试（≥14，全部离线）

- 预算截断：UTF-8 边界（中文多字节）/ head_tail 比例 / 精确字节预算 / 续读提示字段 ≥4
- 重试：退避序列（注入 sleep 断言）/ 提交边界两侧行为 / Retry-After 尊重 / 30s 与 120s 封顶 / 错误归一化映射 ≥6
- 解耦后循环：mock 流驱动（正常/中止/失败并文/工具调用）≥4
- 现有基线零回归

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 基线 + 新增 ≥14、typecheck 0 错、build 成功
- [ ] `git status --short` 无保护路径改动
- [ ] **重启 dev 实测**：让 Agent 读一个大文件（>24KB）→ 观察截断提示 + 模型自主续读行为（截图/对话记录留证）
- [ ] 交付报告第 6 项：CHANGELOG 条目草稿
- [ ] 报告归属与数字如实；变更文件清单必填；**对标出处标注**（借鉴 minimax-code output-limit.ts / llm-retry.ts 模式）

## 交付报告格式（七项制）

1. 变更/新增文件清单（路径+行数）
2. 门禁输出尾部（注明测试条数：激活基线 → 共 N 条）
3. commit hash + 提交信息
4. 自测记录：截断字节边界用例表 + 重试时序断言表 + 编排 mock 场景表
5. 遗留问题 / 对 M8-2（上下文管理）的建议
6. **版本迭代信息（CHANGELOG 条目草稿）**
7. 对标借鉴说明（借鉴了什么模式、是否有代码级相似、MIT 归属处理）
