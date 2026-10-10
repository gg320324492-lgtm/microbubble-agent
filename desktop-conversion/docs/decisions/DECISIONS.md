# 桌面端建设 · 决策记录（只增不改）

> 每条决策带日期与来源。新决策追加在文件末尾，编号递增。

## D1-D7（2026-09-13，骨架设计定稿）

| # | 决策 | 结论 |
|---|------|------|
| D1 | 技术栈 | Electron + electron-vite + Vue3 + TS + Pinia + Element Plus + better-sqlite3 |
| D2 | 定位 | 真桌面原生软件，不加载 web/dist，断网核心功能可用 |
| D3 | 一致性 | 共享包策略（design-tokens 已抽包） |
| D4 | 账号 | 本地账号注册/登录 + 可选绑定网页端账号 |
| D5 | 数据 | 能本地尽本地；验收不过的功能从桌面删除、保留网页端（淘汰制） |
| D6 | 分发 | GitHub 存源码 + 阿里云 OSS/CDN 国内分发 + electron-updater |
| D7 | 旧实现 | 全删，归档 tag `archive/desktop-before-redo-20260913` 可查 |

## W 系列工作区决策（2026-09-14，总指挥对话）

- **W1 工作区位置**：Agent 工作区 = `E:\microbubble-agent\desktop-conversion\`（本文件夹，独立 git 仓库，计划托管 GitHub）；顶级目录即仓库根，子目录在其中开设
- **W2 代码隔离（分阶段）**：`apps/desktop` 应用代码现阶段暂留上层 monorepo（workspace 依赖零迁移成本）；文档/工单/Agent 工作区先隔离到本仓库；应用成熟后再评估独立建仓
- **W3 与父仓库隔离机制**：父仓库 `.gitignore` 整体忽略 `desktop-conversion/`，两侧互不引用、互不提交
- **W4 Agent 行为边界**：`.git/` 读写禁区；Agent 不执行 git 命令；删除走回收站；覆写前备份到 `.agent-backups/`（已 gitignore）；`AGENT.md` 为工作区守则，已存在则不覆盖

## M 系列里程碑决策（详见骨架设计文档）

- M0 骨架+账号 ✅（2026-09-14 落地）/ M1-A 三栏工作台+会话 ✅ / M1-B 模型网关 ✅（MiMo Anthropic 协议实测通，原生 tool_use 探针通过）
- 进行中：M1-C Agent 工具循环（工单 C-1 → C-2 → C-3）
- **2026-09-17 状态更新**：M1-C 闭环 ✅（C-1 `220f624e8` / C-2 `08184aa0f` / C-3 `84ba0be4c` 全部验收通过）；**R-1 发布 ✅——v0.1.0-alpha 已上线 GitHub Release**（`b10888b15`，Pre-release，含安装包三件套与中文发布说明）；进行中：M2 本地知识库+会议档案（M2-1 知识库核心 → M2-2 会议档案 → M2-3 网页端导入向导）
- **2026-09-17 裁决：M2-3 后移，M3 提前**（总指挥建议，用户授权模式「直接执行」下落定，可否决翻转）：M2-3（网页端导入向导）依赖云端绑定 + API 客户端两块基建（约两单体量），且 alpha 单机用户暂无网页端数据可导——后移至「有真实导入需求或 M4 后」按需拆单（M2-3a 云端绑定基建 + M2-3b 导入向导）。当前进行 **M3-1 ELN 本地核心**。R2 发布节奏相应调整：R-2（v0.1.1-alpha）候选内容 = 知识库 + 会议档案 + 缩放加固 + ELN，发布节点随 M3-1 验收收尾或用户指定

## P 系列总指挥流程决策（2026-09-16，总指挥接任会话）

- **P1 运转模式**：总指挥不写业务代码、不代为执行；每轮只产出「执行指令」交给用户，用户转交执行 agent；交付报告贴回后总指挥逐项验收（结论落盘 docs/acceptance/），再适应性签发下一张（一次只签发一张），直至桌面端产品成熟完全完成
- **P2 执行指令格式**：每份执行指令必须附带进度状态段——已完成（含 commit）/ 正在做 / 剩余 / 进度粗估——与指令正文一起给出，供执行 agent 与用户同步全局上下文

## R 系列发布决策（2026-09-17，总指挥对话）

- **R1 发布要求（用户拍板）**：在合适节点构建应用并发布到 GitHub（Release）；每个发布版本必须记录版本迭代信息（CHANGELOG：新功能 / 修复 / 已知问题）
- **R2 发布节奏（总指挥建议）**：首个发布节点 = M1-C 完成（C-3 验收后）出 **v0.1.0-alpha**（electron-builder 打包 + GitHub Release + CHANGELOG.md，专门工单 R-1 承接）；此后每个里程碑收尾出一版；M6 再补齐 electron-updater + 阿里云 OSS/CDN 国内分发通道（D6）。自 C-3 起，交付报告增加「版本迭代信息（CHANGELOG 条目草稿）」一项，发布时汇总成文

## U 系列 UI 决策（2026-09-18，总指挥对话）

- **U1 UI 彻底换新增设（用户拍板）**：当前各模块视觉仍以 Element Plus 默认风格为主，收官阶段须对 UI 彻底换新。定位：新增 **M7「UI 彻底换新」**收官里程碑，排期在 M5 同步引擎 / M6 发布通道完整版之后、v1.0 正式版之前；M4/M5 期间各模块只保持内部一致性，不提前美化（避免换新前返工）
- **U2 设计方向待选（用户拍板）**：**暖珊瑚风格不作为默认方向**（用户明确否定）。总指挥产出四套 UI 风格设计提案（`docs/design/ui-style-proposals.html`，同界面骨架 × 四套设计语言，可切换预览）：A 宣纸暖白（学院）/ B 石墨冷灰（专业）/ C 深夜控制台（暗色）/ D 晨白现代（SaaS）。**由用户选定后作为 M7 设计基准**；选定前 M7 不启动，选定后出完整设计令牌与 Element Plus 主题定制方案
- **U3 设计方向选定（用户拍板，2026-09-18）**：四方案中用户选定 **A · 宣纸暖白（学院）**——米色纸感底（#f3eddf 系）+ 靛墨蓝主色（#3e5c76 系）+ 衬线标题 + 中等信息密度。M7 换新以此为唯一基准。**与被否定的暖珊瑚区分**：宣纸方案是低饱和纸感中性色 + 墨蓝点缀，不是珊瑚橙高饱和暖色；M7 设计与实施中不得回退到珊瑚色调。设计令牌与组件规范在 M7 启动时以 `docs/design/ui-style-proposals.html` 的 paper 主题为源头展开
- **U4 M7 范围与顺序确认（用户拍板，2026-09-19）**：①设计令牌层一次成型（宣纸基准展开全令牌表 + Element Plus 主题覆盖，全组件自动换肤）；②换新范围 = 全局令牌 + EP 主题 + 通用组件 + 六模块微调；③暗色模式本期不做（v1.0 后评估）；④一单到底（M7）分阶段交付报告，随车必办：设置页滚动缺陷修复 + CI 可运行性门禁（M6-2 转办）+ 全模块滚动自查；⑤随车发布 v0.1.6-alpha（走流水线 + CI 门禁首用）；⑥核心视觉变化：主色由珊瑚橙系切换为靛墨蓝系 + 标题衬线化（登录页一并换新）
- **U5 M7 工单签发（2026-09-19）**：`docs/workorders/M7-ui-refresh.md`（含设计基准源文件读取授权：ui-style-proposals.html 为第二个可读文件）；珊瑚橙残留全仓清零为硬验收项；v0.1.6-alpha 随车发布，CI 可运行性门禁首次真实使用

## D10 v1.0 收官裁决（2026-09-19，用户拍板）

- **MiMo Key 轮换取消（用户拍板）**：不再轮换、**此后任何会话/工单/报告不得再提及该事项**——撤销总指挥此前挂起的轮换建议
- **网页端不做改动（用户拍板）**：`packages/design-tokens` 维持珊瑚色系现状（web 端仍依赖），桌面端覆盖层方案**长期化**；v1.0 不做双端联动换新
- **v1.0 范围（按总指挥推荐确认）**：①CI smoke 门禁增加主题令牌断言（`--el-color-primary` 必须等于品牌色）；②用量记账最小实现（SSE usage 四桶归一化 + 会话累计 + 设置页展示，不做费用换算）；③ **v1.0.0 正式版发布**——版本 1.0.0（脱离 alpha）、`prerelease=false`、**test tag 首航（v1.0.0-ci.1）+ 产物可运行性验证通过后推正式 tag（v1.0 起正式 tag 不可变）**、CHANGELOG「首个正式版」全量总结、发布审计清单模板落盘
- **P2 池（v1.0 后按需评估）**：goal 长任务锚 / 子代理三角色 / MCP 检索披露 / 凭据 lease broker / browser-core / 沙箱原则 / 暗色模式 / 全纸面 chrome 裁决 / 费用换算

## D8 更新策略与 M6 拆单（2026-09-18，用户拍板按总指挥推荐）

- **更新 UX：提示式更新**——启动 5s 后后台检查（不阻塞启动）+ 设置页手动「检查更新」；发现新版 → 系统通知 + 设置页展示版本与进度 → **用户确认后**下载并安装重启。不做静默强更
- **更新组件：electron-updater（D6 指定官方组件）——「禁止新增 npm 依赖」红线的唯一例外**，锁最新稳定版并声明于 dependencies；其余依赖禁令不变
- **更新源（M6-1 alpha 阶段）：GitHub Releases provider**（allowPrerelease 必须为 true——全部版本均为 prerelease，默认会被忽略，经典坑）；国内 OSS/CDN feed 迁移列入 M6-2 及之后（D6 完整目标）
- **M6 拆单**：M6-1 自动更新通道（含 v0.1.5-alpha 发布，走既定流水线）→ M6-2 CI/CD（GitHub Actions tag 构建发布）+ 打包优化清账（latest.yml 自动化、托盘 .ico 资源化、backup.exitPassword 迁移 safeStorage、listObjects 分页、out/ 分批清理等积累项）
- **验证方案**：真机全链路 = 本地静态服务伪造更高版本 feed → 检测/下载/安装提示全链路（无需真发布两个版本）；v0.1.5 发布后下一版起进入真实更新循环
- 威胁模型备注（M5-2 复测确认）：`backup.exitPassword` 明文落 settings 边际风险≈0（本地攻击者本可直读活库），加密主防对象是云端泄露；M6-2 迁移 safeStorage 属加固非堵漏

## D9 Agent 能力升级（2026-09-19，用户指示对标开源 + 总指挥出计划）

- **背景**：用户指示对标 MiniMax 开源的 minimax-code（终端编码 agent，MIT），「能应用的提升点全部应用，规范化，列入后续升级阶段」
- **分析**：分析 agent 深挖仓库（pnpm monorepo，pi-mono vendored 底座 + MiniMax 自研编排层），产出 12 维度提升点清单与 Top5 借鉴项，全文见 `docs/plans/2026-09-19-agent-upgrade-plan.md`
- **裁决（采纳总指挥计划）**：新增 **M8「Agent 能力升级」阶段**，拆三单：M8-1 P0 硬化（工具输出字节预算+续读协议 / LLM 提交边界重试+错误归一化 / 循环与 SSE 解耦的编排式测试基建）→ M8-2 上下文管理（估算器+触发线+保留近端+工具组原子裁切，LLM 摘要随车）→ M8-3 权限三值+作用域梯度+证据链（随车：runaway guard/steering/AGENTS.md 注入/AbortSource/todowrite）；P2 池（goal/子代理/MCP 检索/lease broker/browser）v1.0 后按需
- **排期**：M6-2 → M8-1 → M8-2 → M8-3 → M7 UI 换新（宣纸暖白）→ v1.0（Agent 硬化先于 UI 换新）
- **协议合规**：借鉴模式无风险；逐字复制代码须保留 MIT（pi-mono/自研层）与 Apache-2.0（sandbox-runtime，本阶段不触碰）归属；对标参考副本在 %TEMP%（临时）

## S 系列同步决策（2026-09-18，总指挥对话）

- **S1 M5 同步引擎架构（用户拍板：推荐组合）**：**①A 阿里云 OSS 直连**（绕开父项目约束，OSS 签名用 node:crypto 手写，不加依赖）+ **②A 快照备份式**（SQLite 全量 + files 目录打包按时间戳版本化，恢复选快照还原，无冲突问题；本地是主库，云端只是加密备份副本）+ **③AES-256-GCM 加密**（登录密码 scrypt 派生密钥，模型 Key 不入备份）+ **④触发**：设置页手动 + 可选退出时自动（默认关），每日定时入产品池
- **S2 M5 拆单**：M5-1 备份核心（容器格式/加密/VACUUM INTO 快照/files 打包/恢复安全网/设置页区块，纯本地全离线可测）→ M5-2 OSS 通道（手写签名/上传下载列表/退出自动备份，单元测试注入假 HTTP；真机联调需用户提供 OSS bucket + 子账号 AK/SK）。设计文档：`docs/plans/2026-09-18-sync-engine-design.md`

## D11 HTTPS 分发域名与证书事务（2026-09-20，用户拍板 Let's Encrypt 路线 + 总指挥指挥执行）

- **裁决**：为分发子域 `releases.mnb-lab.cn` 签发 Let's Encrypt 证书并托管至 OSS（用户「现在做」）；工具选 acme.sh（ECS 新装，`dns_ali` DNS-01）与存量 certbot（HTTP-01，三域）并存互不接管
- **诊断学记录**：TXT 添加失败三连 → `--debug 2` 取证 = 阿里云 DNS API `Forbidden.RAM`/`ImplicitDeny`（缺 `alidns:DescribeDomainRecords`），属主 UID 比对锁定 workbench-backup → 根因是**该 RAM 用户只授过 OSS、DNS 权限从未落上**，补授 `AliyunDNSFullAccess` 即通。教训：RAM 类故障先用 debug 输出的 AuthAction/AuthPrincipalDisplayName 定位，不盲猜密钥抄写
- **密钥纪律（本次重点）**：证书私钥两度随终端粘贴进入对话 → 以 `--force --always-force-new-domain-key` 连续换钥，**线上证书对应第 3 把钥、从未进入对话**；私钥交接改为「终端→CAS 表单直达、对话只回『配好了』」协议。OSS AK Secret 亦两度进对话 → **轮换仪式列必办待办**（RAM 禁旧建新 + 更新 GitHub Secrets 与应用 OSS 配置，全程 Secret 零接触对话）
- **托管架构**：新版 OSS 证书托管面板的公钥/私钥框为只读展示，自传证书正路 = 数字证书管理服务（CAS）「上传证书」（证书文件=叶子块 / 证书链=中间块 / 私钥）→ OSS 域名管理选该证书
- **终验全绿（04:22-04:24 CST）**：TLS 链有效（YE2 中级，至 2026-12-18）；`https://releases.mnb-lab.cn/releases/latest.yml` 匿名 200；安装包 200 且字节数与 feed 清单一致。证据与指纹留档 `docs/acceptance/2026-09-20-R-8-https-pass.md`
- **遗留**：①`UPDATE_FEED_HOST` 切 `https://releases.mnb-lab.cn`（constants.ts 注释预留行）随下一发布列车；②OSS AK 轮换仪式；③acme.sh ARI 自动续期已排（2026-11-19），无需人工
- **追加（2026-09-20，用户拍板）**：OSS AK **轮换取消——不创建新 key**（与 D10 MiMo Key 同类裁决）；原「轮换仪式」待办作废，改为三处使用点统一到现役对（应用设置页 OSS 配置 / GitHub Secrets `OSS_UPLOAD_AK`·`OSS_UPLOAD_SK` / ECS `~/.acme.sh/account.conf`），总指挥已交付统一步骤，由用户自行执行

## D12 抢救：`.workbuddy-ai/memory` 实战记忆迁移（2026-09-30，阶段收尾 S2.2）

> 来源：`desktop-conversion/.workbuddy-ai/memory/MEMORY.md`（该目录规划废弃，此为**唯一副本**，
> session-log 里没有这些内容）。以下为原文核心，一字未删减语义。

**域名与部署事实（★ 极易踩坑，已实测）**

- API 主机 = `https://agent.mnb-lab.cn`（`/health` 200；`/api/v1/auth/me` 401 JSON）
- `https://mnb-lab.cn` 是网页端 SPA，**不是 API**：`/api/v1/*` 会被 nginx `try_files` 回退成 HTML（GET 200 text/html、POST 405）。
  **判断手法**：GET 一个需鉴权的 API 路径——**返回 HTML 就是 SPA 回退，返回 401/JSON 才是真 API**。
- 更新源/下载 feed：`https://releases.mnb-lab.cn/releases/`（`latest.yml` 匿名 200）；OSS 桶 `mnb-workbench-releases`（`oss-cn-beijing`），落地页对象 `download-page.html`。
- 父级错误体形状：`{"error":{"code":"AUTH_ERROR","message":"..."}}`（**不是**扁平 `{detail:...}`）；登录限流 5 分钟 5 次、429 带 `Retry-After`。

**桌面端（apps/desktop）架构要点**

- 主进程与单测**零 Electron ABI 依赖**；外部能力（HTTP/OSS/safeStorage）一律**注入式**，单测不触网。
- 网关：`src/main/services/model-gateway.service.ts`——双协议（anthropic / openai）；Anthropic 走 `content_block_start/delta`（`signature_delta` 需安全忽略）；`assemble()` 只收 `type==='text'` 的块拼正文。
- Agent 循环：`src/main/agent/agent-loop.service.ts`（`MAX_AGENT_ROUNDS=15`）；工具注册表 `ToolRegistry(workspace, audit)`（**构造签名两参，漏传 workspace 会让围栏失效**）。
- 权限：`agent/permissions/policy.ts` 三值(allow/ask/deny) × 三作用域(session>workspace>global)；**deny 是不可被更近 allow 覆盖的否决权**。
- 上下文：默认 131072 窗口 / 0.70 触发 / 0.50 目标 / 近端 3 轮。
- 桌面端自有钱包：settings 键（`cloud.tokens` / `cloud.binding` / `agent.context.config` / `agent.permissions.global`）+ safeStorage 加密器（加密不可用时 encrypt 返回空串）。

**发布流程（顺序铁律，走通过 R-10）**

1. 版本两处同步（`package.json` version + `src/shared/constants.ts` APP_VERSION）→ CHANGELOG 定稿 → **提交（早于 tag）**
2. 打包 + 真机首启（改过 `ipc.ts` 装配必测 TDZ）
3. test tag `vX.Y.Z-ci.N` 首航 → CI 全绿含 OSS 镜像 → `gh release delete --cleanup-tag` 删净 → 才推正式 tag
4. 发布后四连测：双源 sha256 逐字一致 / feed 200+version / 直链 200 / Release draft=false+pre=false
5. 落地页用 **CI 产物**的 sha256（NSIS 构建不可复现）；发布前先取 feed 基线做前后对比

**工程纪律（本仓库特有）**

- **改仓库文件优先用 Edit 工具**：部分文件是 CRLF，Python 文本重写会转成 LF → 整文件假 diff（R-10-B1 实证）。
- **历史/推送类 git 操作一律用 `git ls-remote` 取到的显式 SHA**（本地 `origin/main` 可能过期，会 `reset --soft` 退多）。
- 门禁基线（截至 2026-09-21）：`pnpm test` **604 条**全绿 / typecheck 0 / build 成功。
- 保护路径（只读，写零容忍）：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/`。
