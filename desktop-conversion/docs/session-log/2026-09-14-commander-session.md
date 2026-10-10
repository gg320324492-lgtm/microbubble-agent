# 总指挥会话简报 · 2026-09-14（M0 → M1-B 会话）

> 本文件是总指挥窗口（负责桌面端建设的拆解/派工/验收）一场完整会话的结构化蒸馏，
> 供新会话/新窗口快速接续上下文。决策全文见 `docs/decisions/DECISIONS.md`。

## 一、角色与运转模式（用户拍板）

- **本窗口 = 总指挥**：只做任务拆解、工单签发、质量验收、决策商讨；**不写业务代码**
- 具体执行交给其他 agent；**一次只派一张工单**，执行完用户把交付报告贴回，总指挥验收后再适应性签发下一张
- 所有工单、验收结论、决策沉淀在本工作区（desktop-conversion/）

## 二、已完成的里程碑（全部在 apps/desktop，实测通过）

| 里程碑 | 内容 | commit |
|--------|------|--------|
| M0 | pnpm monorepo + Electron 无边框窗口 + 本地账号体系（首启注册管理员/登录/safeStorage 会话恢复）+ 设计令牌包 + 组徽图标全套 | `67e5dfae8` |
| 图标/logo | 微纳米气泡课题组组徽：exe 六档 ico / 窗口图标 / 标题栏 / 登录页品牌位 | `968826d72` |
| M1-A | 三栏 agent 工作台（56px 图标栏 + 248px 会话列表 + 对话面板）+ 会话本地持久化（迁移 003）+ 本地回声应答 | `fcdaade15` |
| M1-B | 模型网关：OpenAI/Anthropic 双协议 SSE 流式、key safeStorage 加密、Provider 管理与测试连接、停止生成（Esc）、标题栏三键状态精修 | `3b43f3fa2` |

## 三、已验证的关键事实（后续工单的架构依据）

1. **MiMo 接入参数**（生产实测）：Anthropic 协议，Base URL `https://token-plan-cn.xiaomimimo.com/anthropic`，模型 `mimo-v2.5`；key 前缀 `tp-` 只走此代理（标准 OpenAI 端点 401）。归档里 `api.xiaomi.com` 域名不存在，勿用
2. **MiMo 原生支持 tool_use**（探针实测：`stop_reason:"tool_use"` + 结构化 input）→ C-2 用原生工具调用循环，无需提示词模拟
3. **MiMo 输出 thinking 块**（`thinking_delta` 在正文前）→ 网关只取 `text_delta`，思维链不进正文；UI 后续可做折叠思考面板
4. 用户测试账号：`demo / demo12345`（本机 dev 库，管理员）
5. 用户已提供 MiMo key 并已加密写入本机 dev 库（跨进程 safeStorage 解密验证通过）；**建议用户日后轮换该 key**（曾贴入对话）

## 四、关键技术教训（踩过的坑，勿重踩）

1. **out/ 混代产物**：`index.html` 引到旧代 CSS 导致外壳样式整块丢失（侧边栏铺满全宽事故）→ build 前强制清空 out/，已固化进 build 脚本
2. **better-sqlite3 ABI**：pnpm 的 .npmrc runtime=electron 不传给 prebuild-install；装错 ABI 时 `require()` 不报错、`new Database()` 才报。手动 `node <prebuild-install>/bin.js --runtime electron --target 32.x`
3. **electron postinstall 本机静默半装**（dist 只有 locales）：手动解压缓存 zip + `printf` 写 path.txt（echo 会带 \n 导致 spawn 路径损坏）
4. **happy-dom 18 与 VTU trigger 不兼容** → 用 jsdom；组件测试 stub window 用 `Object.assign(window,{api})`，整体替换 window 丢原型上的 Event 构造器
5. **并行 agent 共用 git 索引**：出现过 staged 删除被并行会话扫走、index.lock 争抢 → 执行 agent 必须路径限定提交、遇锁等待不删锁
6. **element-plus 全量引入后 bundle 2.4MB**：桌面本地加载可接受，后续可换按需引入
7. **MiMo 探针方法**：中文内容走 curl -d 会被 Windows 控制台编码搞坏 → JSON 写临时文件 `--data-binary @file`

## 五、当前状态与下一步

- **已签发**：工单 C-1 v2（工作区服务 + ToolRegistry + 4 个只读工具 + 围栏 7 例 + 审计 004 + 设置页工作区区块），全文在 `docs/workorders/C-1-workspace-readonly-tools.md`，等待执行 agent 交付报告
- **待验收后签发**：C-2（ReAct 原生 tool_use 循环 + 工具卡片 + thinking 折叠面板）→ C-3（写工具 + Diff 确认 + 备份回滚）
- **验收流程**：交付报告贴回总指挥 → 逐项对照工单"定义完成"清单 → 结论写入 `docs/acceptance/`
- **质量门禁基线**：测试 29/29、typecheck 0 错、clean build、chunk 图完整、保护路径零改动（红线清单见 C-1 工单第〇节）

## 六、对话中用户明确的偏好

- UI 混乱会直接指出，期望对标 Claude Code / OpenClaw 的 agent 体验
- **能本地尽本地**；验收不过的功能直接从桌面砍掉（保留网页端），不回退成云端依赖
- 每步都要可实际验收；界面类改动会亲自看效果
- 窗口三键这类基础桌面体验要求做到位

## 七、交接完成（同日）

- 新总指挥窗口已就位：三点状态复述确认无误（进度/验收标准/铁律）
- 卸任总指挥留下两点校准：①「不影响父项目」收窄为「零源码改动」，允许只读核验
  （读代码、跑测试、git show）以防执行 agent 报告失真；②验收锚定 commit hash，
  `git show <hash> --stat` 核对变更范围；测试基线 29，C-1 后应 ≥43 且零回归
- 本窗口退役；当前挂起事项不变：等待 C-1 交付报告
