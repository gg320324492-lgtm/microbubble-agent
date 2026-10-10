# 第三阶段收尾规划（2026-10-02）

> **本文档的定位**：S3 阶段（2026-09-30 ~ 2026-10-02）的实质开发工作已全部落地，
> 但开发过程中识别出的遗留项散落在
> [`2026-09-30-phase-closeout-plan.md`](2026-09-30-phase-closeout-plan.md) 的执行记录里，
> 且**主文档只记了结论、没记"现在还剩什么、为什么剩、怎么解"**。
> 本文档把散落账目集中成一份可执行的收尾清单，并补上主文档缺的那层实测证据。
>
> **写作纪律**：本文每一条都标注了**复检官独立实测的复核结果与日期**，不转述他人自报。
> 凡"已修"必须有机制证据或可复现的对照实验；凡"受阻"必须写清受阻于什么、解阻条件是什么。
>
> **不属于本文档的范围**：S3 阶段已完成的工作本身（见主文档 S3.0–S3.8 表）。
> 本文只处理**账目**——欠着的、挂着的、被有意留着的。

---

## 一、一句话结论（2026-10-03 收尾后更新）

**5 笔账已清 3 笔，2 笔维持"不做 / 外部依赖"。**
`Lint CSS` / `RAG Framework CI` / `axe-core a11y` 三个门禁**现均真 CI 绿**，
且 a11y 门禁经过"故意制造违规 → 确认它真会红"的**可证伪性验证**（见 §3.7）。

五个门禁现已全绿（`Lint CSS` / `RAG Framework CI` / `axe-core a11y` /
`Server Tests Baseline` / `Playwright Tests` 整体）。

**但 S3 阶段"无可待做"不等于"路线图走完"** —— S3.6-3b 的两个热点、
视觉回归门禁的最终定位、以及两笔已知小账仍悬着，**已按"能不能开工"分组登记于 §4**。
其中 §4.1 需要你先给一个决策（CSS 改动是否接受人眼review 验收）。

> ⚠️ **本轮最大的发现不是"修好了"，而是"四个门禁其实一直没在工作"。**
> 详见 §3.7 —— 四个"看起来是门禁、通过与失败都不携带信息"的实例，
> 这是本阶段最值得沉淀的东西。

---

## 二、账目总表（2026-10-09 更新）
| # | 账目 | 原定性 | **现状** | 证据 |
|---|---|---|---|---|
| **R-1** | stylelint 296 条 + token orphan 133 条 | 真欠账 | ✅ **已清零** | `Lint CSS` run `37092817889` = success；`check-token-orphans.sh` = **0 orphans**；`npx stylelint` = exit 0 |
| **R-2** | minio 镜像 unauthorized | 外部依赖挂起 | ✅ **已绕过闭环**（2026-10-02 `fa4575788`：minio-test 默认不启动、profile 可逆，上游恢复可加回；原"仍挂起+visual cancelled"旧文被 §3.8/§4.8 取代） | 近期 Playwright（含 visual 硬门）连续 success |
| **R-3** | RAG CI 缺依赖 | 待立项 | ✅ **已清**（12 条失败 → 0） | `RAG Framework CI` = success；补 `anthropic` + `pgvector` + `sqlalchemy[asyncio]==2.0.23` |
| **R-4** | design-token drift 门职责错位 | 有意留档不做 | ✅ 维持不做 | — |
| **R-5** | `BUILD_ID` 致 dist 对不上 | 结构性，先有意留档 | ✅ **2026-10-07 已根治**（用户拍板按最彻底执行，原"不做"作废见 §3.5 注） | 源输入哈希派生 + 反循环；复检官 tip 构建逐字节收敛；§4.11 |

**另有一笔已撤销、不要重复立项**（§3.6）：~~前端全量测试 flaky~~ ——已坐实是 agent 遗留探针污染分母。

**R-1 清理中额外暴露并修掉的账**（原文档未预见）：

1. `scripts/check-token-orphans.sh:73` 每行只取首个 token（`head -1`），**同行第 2 个起全部漏检**。
   已用对照实验验证修复：造一行含 2 个 orphan 的用例，旧版只报 1 条、新版报 2 条。
2. `pulse-dot` 有 **3 份同名全局 keyframes**，而 Vue scoped CSS **不重命名 keyframes**
   → 互相级联，实际生效取决于 import 顺序。
3. `a11y-baseline` 的失败调试步骤 glob 写错（`test-results/*-actual.txt`），
   而 Playwright 实际写到 `test-results/<case-dir>/` 下 —— 实测**旧 glob 匹配 0 个文件**，
   意味着那个"红灯时打印实际快照"的步骤**从未打印过任何东西**。
4. `Upload a11y snapshots` 原上传的是 CI 自己重生成的快照（同样自证），已改为只读拷贝入库基线。

---

## 三、逐条账目

### 3.1 R-1：stylelint 296 条 —— 本阶段唯一真欠账

**复检官实测（2026-10-02，本机 `npx stylelint "src/**/*.{vue,css}"`）**：

```
✖ 296 problems (296 errors, 0 warnings)
11 errors potentially fixable with the "--fix" option.
exit=2
```

与主文档 S3.4 记录的数字**完全一致**，说明这半年没有新增也没有修复，**是静态存量**。

**按文件分布（41 个文件，前 6 名）**：

| 文件 | 条数 |
|---|---|
| `src/views/chat/ChatViewSSE.vue` | 79 |
| `src/components/drive/DriveDetailRail.vue` | 56 |
| `src/components/chat/ChatMessageRow.vue` | 15 |
| `src/components/chat/InputToolPanel.vue` | 12 |
| `src/components/ThemeToggleButton.vue` | 11 |
| `src/components/drive/FolderDeleteConfirmDialog.vue` | 8 |

**主规则是 `declaration-property-value-disallowed-list`** —— 硬编码颜色值，
项目已有 `web/src/assets/variables.css` 设计令牌但这些文件没用上。
这与 S3.3（design-tokens 收成单一可写源）**同族但不是同一件事**：
S3.3 治的是"令牌有两份副本"，本条治的是"组件没用令牌"。

**为什么一直没修**：S3.4 当初把 `Frontend unit tests` 从 stylelint 的短路下摘出来
（拆成独立 job），**有意只摘 vitest 那条、保留 stylelint 的红**——
目的是让"前端单测是否真被执行"这个问题可独立验证，与"CSS 债还清不清"解耦。
所以**这不是回归，是当时的有意选择**。代价是 `Lint CSS` workflow 长期红。

**建议拆法**（因为 79 + 56 = 135 占 45%，且这两个文件恰好是 S3.6-3b 的两个剩余热点）：

1. **先跑 `--fix`**（11 条自动可修）→ 零风险，先摘掉一小块；
2. **再定 baseline**：`Stylelint 0 errors baseline + trend` job 已在跑，
   可用它锁"不增长"，再逐步下调基线数字到 0；
3. **与 3b 合并做**：清 `ChatViewSSE` / `DriveDetailRail` 的 CSS 债时
   本来就要动这两个文件，边改边清比单独开一轮更省。

⚠️ **一条纪律**：`--fix` 会改代码，**必须先跑测试确认基线绿**再动，
且跑完测试**立刻还原 dist**（见 §4）。

---

### 3.2 R-2：minio 镜像 unauthorized —— 被迫挂起，非能力问题

**复检官实测（2026-10-02）**：读 `gh run view 37002427006 --log-failed`，
`visual regression` 与 `axe-core a11y` 两个 job 的真实报错：

```
minio-test Error unauthorized: access to the requested resource is not authorized
redis-test  Interrupted
✗ app /health never returned 200
```

**当前 `docker-compose.test.yml:60` 的状态**（已含主文档记录的警告注释）：

```yaml
image: quay.io/minio/minio:RELEASE.2024-09-13T20-26-02Z
```

**为什么挂着**：注释写明该 tag 是**复检官误写、已实测 `docker manifest inspect` exit=1**；
对照组（hello-world / redis:7-alpine / alpine:3）正常 → 非本机 registry 问题，
疑上游镜像供给停滞。**不退回无 tag 形式**（那正是要修的 bug），
**不换 S3 实现**（`app/` 与 alembic 里 `minio_object_key` 相关面 52 处，属产品决策）。

**爆炸半径已实测确认为仅 Playwright**：
`qa-bench-baseline` 用 pip 客户端库、`qa-bench-ci/smoke` 连生产 compose 的 localhost:9000，
三者都不依赖这个 `minio-test` 服务。

**解阻条件**：上游 quay.io/minio 恢复可拉取。**可做的替代动作**：
若急于恢复 Playwright，可临时把 `minio-test` 从 compose up 的服务列表里去掉
（两个 job 都不实际使用 S3），但这属于改测试环境语义，**需你决定**。

---

### 3.3 R-3：RAG CI 依赖清单缺口 —— 文档记的根因不完整

**主文档 S3.7 ⑥ 记的是**："`jieba` 修好后**新暴露** 14 条 RAG 失败，非本轮范围"。

**复检官实测发现根因比这更深一层**（`gh run view 37002426969 --log-failed`）：

```
tests/rag_framework/test_agent_retriever.py::TestRouteVector::... FAILED
E   TypeError: object of type 'NoneType' has no len()
ModuleNotFoundError: No module named 'anthropic'
```

**14 条失败的真实根因是缺 `anthropic` 模块**，而：
- `requirements.txt:23` **已声明** `anthropic>=0.39.0`
- `.github/workflows/rag-framework-ci.yml:61` 的**手写安装列表里 `anthropic` 出现 0 次**

⇒ 这**不是"jieba 修好后新暴露的业务失败"，而是与 jieba/rank-bm25 完全同型的
"手写列表漏依赖"**。S3.7 ③ 的根治方案（改回 `-r requirements.txt`）**同样能修掉这条**，
主文档里把它记成"连带装 torch 拖慢 CI，需评估"而搁置了。

**建议动作**：**先做穷尽性核对**——把 `requirements.txt` 里 CI 需要的包
与 workflow 手写列表做一次差集，确认到底漏几个（目前实测至少漏 `anthropic`）。
若差集很小（1–2 个），直接补进手写列表即可，不必承担 `-r requirements.txt`
的 torch 代价。**这个差集是本条的核心交付物，不要跳过。**

⚠️ **不要**把这 14 条当"业务回归"去 debug `test_agent_retriever.py`——
它们在缺依赖时必然失败，与被测逻辑无关。

---

### 3.4 R-4：design-token drift 门职责错位 —— 有意留档，**不做**

**事实**（主文档 S3.7 ⑧）：drift 门挂在 `frontend-unit-tests` job 上，
守的却是 `packages/design-tokens` 的副本。结果：**改一个 design-token
会触发 131 秒的前端单测**，纯效率损耗。

**为什么不做**：拆成独立 job 需要重做金丝雀（这是 S3.4 总结的教训：
改动必须有可证伪的实证），收益不抵成本。

**复检官补充一条实测**：当前 `Lint CSS` run 里
`Stylelint 0 errors baseline + trend` job 是 **success**，
红的是它旁边的裸 `Stylelint (CSS / Vue)` ——**两个 job 已完全解耦**，
与 S3.4 拆 job 的目的一致。本条不构成正确性风险。

**留档结论**：不做。若将来 CI 耗时成为真痛点，再单独立项拆 job。

---

### 3.5 R-5：`BUILD_ID` 致 dist 每次 commit 都对不上 —— 有意留档，**不做**

> **2026-10-07 更新：已根治，"不做"结论作废** —— 用户拍板按最彻底执行，
> 源输入哈希派生方案已落地并经复检官独立复验（tip 构建与入库 dist 逐字节一致），
> 全过程与两个副产物见 **§4.11**。

**机制**（`web/vite.config.js:45`，复检官实测）：

```js
const BUILD_ID = safeExec('git rev-parse --short HEAD', 'unknown-head')
```

该值注入 bundle。已入库的 bundle 内嵌 `[build] <ts> (id=<8位hash>)`。

**复检官实测的三次 build 对照**：

| 构建时机 | HEAD | 产出 entry | 内嵌 id |
|---|---|---|---|
| 入库的 dist（`f8924f1bb` 提交时） | `e4553adb6` | `index-B9JuxPd7.js` | `e4553adb6` |
| 在当前 HEAD 重建 | `8eaea56a9` | `index-BRteEaQp.js` | `8eaea56a9` |

**两个 build 都是确定性的**（连续两次 build 产出的 337 个 asset 文件名 diff = 0 行）。

**结论**：已入库 dist 与"当前源码重新构建"的结果**必然不同**，
且**这在机制上无法消除**——任何后续 commit 都会重新制造这个落差。
这不是缺陷，是该设计的正常表现。

**为什么不做**：
1. `web/dist` 入库是**部署契约**（云端 `git pull` 取的就是它），
   所以"仓库里的 dist 必须能跑"这条要求已经满足；
2. 要根治得改 `BUILD_ID` 的派生方式（如改用源码 tree hash 而非 commit hash），
   那是**架构决策**，且会让"一个 commit = 一个可追溯构建"的审计能力受损；
3. pre-commit 钩子（`check-dist-before-commit.sh`）~~已经保证了**改 src 必须同时入库匹配
   的 dist**~~ —— ⚠️ **此句为 R-5 落地前的旧教义，2026-10-08 修正**：现行纪律是
   **两段式**（先提交源 → `npm run build` → 再提交 dist，原子 src+dist 反而被禁，
   见 §4.11 遗留③闭环记录）；且旧机制是"自动补 add"（制造原子提交的机器）而非保证，
   wrapper 更因无退出码传播从未真正拦截——"保证"一词当时就不成立。

⚠️ **一条曾被误判的事实，留档警示**：复检过程中曾据"入库 dist 内嵌的 hash
不等于当前 HEAD"得出过"不存在漂移"的相反结论。**两种说法都不准确**——
准确表述是：**入库 dist 与"它构建时的那个 commit"自洽，而那个 commit 永远不是当前 HEAD。**

---

### 3.6 已撤销项（**不要重复立项**）

**~~前端全量测试 flaky~~ —— 已撤销**，主文档 S3.7 ⑩ 有完整记录。

真因：分母 `150 = 146 + 4` 个 agent 遗留的 `web/.s38scratch/*.probe.test.js` 探针，
vitest include 规则**不排除**该目录。复检官做过对照实验（造 4 个探针 → 150；删掉 → 146）。

**沉淀的纪律仍然有效**：凡"全量基线"类结论，除连跑三次取多数外，**还须先解释分母来源**。

---

## 四、收尾时的执行纪律（从本阶段踩过的坑里来）

以下四条都是本阶段**实际踩过**的，不是假想风险。

### 4.1 跑测试 / build 后必须还原 dist

在父仓 `E:\microbubble-agent` 的 `web/` 下跑任何 vitest 或 build，
退出时会**删改 381 个 `web/dist` 文件**（190 删 + 190 增 + `index.html` 改）。

```bash
cd /e/microbubble-agent && git checkout -- web/dist && git clean -fdq web/dist
```

**本阶段复检官与执行方各踩了 3 次**。`web/dist` 入库是部署契约，
不还原就提交 = 把未经金丝雀验证的产物推进部署仓。

### 4.2 临时探针必须放在 vitest 扫不到的位置，或跑完即删

§3.6 那笔 flaky 假立项的**唯一根因**就是探针污染。
`web/` 下任何 `*.test.js` 都会被默认 glob 收集，**不要**以为放在 `.s38scratch/`
这类目录里就安全。

### 4.3 「全量基线」结论必须先解释分母

分母对不上时，先查"跑的时候工作树里有什么"，**而不是先假设"代码不稳定"**。
本阶段正是只验证了"连跑三次稳定"、没验证分母自洽，才把自造污染读成了 flaky。

### 4.4 行数一律以 `wc -l` 为准，别用 `Measure-Object -Line`

`Measure-Object -Line` 按定义跳过空行，对 5633 行的文件给 **5205**（差 428 = 真空行数）；
在 Windows PowerShell 5.1 且未加 `-Encoding` 时更会因 ANSI/gb2312 解码吞掉 622 个换行
而给出 **4588**。**同一台机器换个 shell 就换一个数，是"尺子是坏的"最标准的形态。**

⚠️ 同型陷阱（复检官本次实测）：Python 写临时文件默认带 **CRLF**，
喂给 `BUDGET_FILE=` 的 shell 脚本会让 `$'\r'` 粘进路径，
使所有条目 kind 变成乱码 → **exit 1 是"看起来对、其实错因"**。
写临时基线文件必须显式 `newline='\n'`。

---

## 五、建议的收尾顺序

按"**能立刻做 → 需决策 → 等外部**"排列，先把能摘的红摘掉：

| 序 | 动作 | 账目 | 预计影响 |
|---|---|---|---|
| 1 | R-3 穷尽核对 requirements 差集并补进 CI 安装列表 | R-3 | **直接让 `RAG Framework CI` 转绿** |
| 2 | R-1 先 `--fix` 那 11 条，再定 baseline 下调计划 | R-1 | `Lint CSS` 首批见效 |
| 3 | R-1 与 S3.6-3b 合并做（清两个热点文件的 CSS） | R-1 | 135 条（45%）一并解决 |
| 4 | 决定 R-2 是否临时移除 `minio-test` 服务 | R-2 | **直接让 Playwright 转绿** |
| 5 | R-4 / R-5 维持不做，仅留档 | — | 无 |

**顺序理由**：第 1 步是纯依赖核对、零代码风险、且能立刻摘掉一条长期红的门禁；
第 2–3 步需要动代码且要跑测试（受 4.1 约束）；第 4 步是决策而非执行。

---

## 五点五、§3.7 本轮最重要的发现：四个"假门禁"

> 本节是 2026-10-03 收尾时新增的，**内容比上面所有账目都值钱**。

S3 阶段修掉的所有红灯里，最有价值的不是"少了多少条违规"，而是**发现四个门禁从来没在工作过**。
它们的共同形态是：**通过与失败都不携带信息**。

| # | 门禁 | 真实状态 | 怎么发现的 |
|---|---|---|---|
| 1 | 前端 API 冻结断言 `?dup=` | **恒绿**：Vite 的 `?dup=` 查询串**不复制** `./constants` 的模块实例，两次加载共享同一计数器，于是 `unique===total` 与 `first>last` 恒成立，坏拆分也绿 | 实测 `?dup=` 副本产出 `s_4,s_5,s_6`（接着共享计数器继续发号） |
| 2 | 裸 `Stylelint (CSS / Vue)` job | **恒红**：296 条存量让它每次 exit 1。旁边 `Stylelint 0 errors baseline + trend`（棘轮）才是真门 | 查 per-job 结论：棘轮绿、裸 job 红 |
| 3 | alembic head 守卫 | **从未执行**：长期 `skipped`（前面的测试先失败短路 job）。修好测试后才第一次真跑，随即暴露硬编码 `091_add_kg_entity` | 查历史 run 的 step 结论全是 `skipped` |
| 4 | `axe-core a11y` | **自证**：先跑两次 `--update-snapshots` 再"验证"，拿刚重写的基线跟自己比，永远绿。实测真实违规 27 条、门禁报 success | 对照：CI artifact 27 条 vs 入库基线 10 条 vs 结论 success |

### 判据：**判断一个门禁有没有用，只看它绿不绿是不够的**

必须做**反向验证**——故意制造违规，确认它**真的会红**。本轮四次实测：

1. 把 `let _idCounter = 0` 追加进 `sections.js` → 转红，报 `['constants.js','sections.js']`
2. 追加第二份 `function _genId` → 转红
3. 把 `FIGURE_MARKER_RE` 复制进 `figures.js` → 转红，报 `FIGURE_MARKER_RE@constants.js+figures.js`
4. 给 alembic 链注入一张**从倒数第二节点分叉**的假迁移 → `FAIL: expected exactly 1 alembic head, got 2`

### 反向验证本身的三个陷阱（本轮实际踩过，值得单列）

| 陷阱 | 现象 | 正解 |
|---|---|---|
| **漏装依赖** | 忠实环境少装一个包，alembic 加载就崩，**两种场景都 rc=1** | 崩掉也是 fail，方向安全但**不构成正向证明**；必须先补齐环境 |
| **造违规的形状不对** | 让假迁移 `down_revision = 真实 head`，它成了**新的唯一 head**，链上仍只有 1 个 head，守卫 rc=0 | 双 head 必须**从倒数第二个节点分叉**，两个 head 互不为后继 |
| **CSS 断言无分号** | 按 `/flags;` 匹配，而源文件这些字面量结尾是 `/flags`（无分号），对全部 7 个文件命中 0 条 | 断言恒绿且"看起来在跑"。已加**精确计数自检**挡此类退化 |

### 一条工具陷阱（影响所有 agent 的验收）

检测 U+FFFD 替换字符时，`grep -qP '\x{FFFD}'` 在 Git Bash + 本机 locale 下**假阴性**
（对确实含替换字符的文件报"干净"）。可靠写法（用八进制转义，避免在文档里直接放替换字符）：`grep -c $'\357\277\275'` 或 Python 的 `str.count('\357\277\275')`。
**任何依赖 `grep -P` 的 U+FFFD 自查会拿到假通过。**

### 另一条：本地环境不是 CI 的忠实代理

本轮共发生**四次**"本地全绿、真 CI 仍红"。最典型一次：某 agent 用自建 axe harness
测得"light 20 cases → 0 violations"并据此报告完成，而真 CI 跑出**仍有 13 条对比度违规**。

**判据**：本地结果只能作辅助，**真 CI 是唯一判据**。且 agent 自报的本地数字本身也要复核——
本轮实测发现同一 agent 报的"3 个测试失败"实际 4 个，而连跑两次后又是 0 个（偶发超时）。

## 五点八、§3.8 `visual regression`：不是"坏掉的门禁"，是"从未运行过的门禁"

> 2026-10-03 追加。这条**推翻了本文档 §3.2 的原始诊断**，且结论比原记录严重得多。

### §3.2 的诊断已过时

§3.2 记的是"minio 上游全仓不可达导致 Playwright 长期红"。**该阻塞已由 `fa4575788` 解除**
（`minio-test` 加 `profiles: ["s3"]` 默认不启动），`Start test environment` 现在 success。
真实死因是**超时**：`timeout-minutes: 20`，实测跑 20 分 19 秒被精确杀掉。

### 三层递进的真相（每层都比上一层更严重）

1. **登录态一直是坏的**：`visual` job 仍在用 `docker exec app-test`，而 compose 未给 app-test
   声明 `container_name`，真实名是 `microbubble-agent-app-test-1` → `No such container`；
   `| tail -20` 吞掉退出码 → step 假 success → 测试用户从未创建 →
   `TOKEN_LEN=65`，写入环境变量的是 `{"error":{"code":"AUTH_ERROR"}}`。
   **同一 run 里 a11y job 是 506（真 JSON）、visual 是 65** —— a11y 早在 S3.8 用
   `docker compose exec -T` + fail-loud 修过同款 bug，**visual 没同步**。
2. **坏 token 放大成"卡"**：每个 chat spec 停在"填登录表单"后干等打满
   `test.setTimeout(240_000)`，再因 `retries: 1` 重来一遍。
3. ⚠️ **它从来没有真正执行过**：近 40 次 run = 23 `cancelled` + 17 `failure`，
   而那 **17 次 failure 全部死在 `Start test environment`**，
   `Run visual regression tests` 在 17 次里 **skipped 了 17 次**。
   **⇒ 不是"没绿"，是"从来没跑"。**

### 为什么"收敛到真视觉回归"这条路被否决

真视觉回归只有 7 文件 / 13 处 `toHaveScreenshot`。看似收敛即可，但：

- **5 个真 baseline spec 的 `-snapshots` 目录在 git 里全都不存在**
  （复检官实测：`find web/tests -type d -name "*-snapshots"` 全仓为空、`git ls-files` 零 PNG）。
  历史上有过，被 `f9495f13b 废弃 v76 视觉回归` 与 `4c97ae562 删 baseline png` 删除。
- 实测 Playwright 缺基线时**不自动写盘**，直接 `1 failed` 报 `A snapshot doesn't exist at`。
- ⇒ 收敛后 job 会从 `cancelled` 变 `failure`，但失败原因是**"没有基线可比"而非代码回归**。
  **那是一个"看起来在拦回归、实际只报缺文件"的假门禁，比现状更误导人。**

### 为什么"迁到 tests/e2e/"也被否决

原方案 C 想把被移出的 spec 显式迁到 `tests/e2e/`（号称已有独立 CI 覆盖）。**复检证伪**：

```
grep -rn "tests/e2e" .github/workflows/     → 空
grep -rn "playwright.e2e.config" .github/  → 空
```

`playwright.e2e.config.js` **自己的注释**就承认"本 config 无人引用（package.json 与所有
workflow 都没用它）"；`testMatch` 只认一个文件。另一候选 `lint-css.yml` 的
`Visual regression (已废弃)` job 是 **`if: false` 永久占位**。
⇒ **迁过去 = 彻底不跑 = 丢弃。** C 方案因此不成立。

### 结论与正确的先后顺序

**当前处置**：只做两项无争议的净收益 ——(a) 修登录态、(b) 删掉空转的第二遍
`--update-snapshots`（它重写快照却既不 commit 也不 upload，纯浪费）。
**收敛与重录基线均暂缓。**

**真正的先后顺序**（缺一不可，否则后续 CSS 改动无法验收）：

1. 先把 `ChatViewSSE` 的 CSS 抽取做完；
2. 再摘掉 `visual regression` 的 `continue-on-error: true` 转硬门；
3. 才谈重录基线。

⚠️ **重录基线这条本身也有坑**：必须在**本机真环境**录，因为 CI runner 的字体/渲染与本机不同，
本机录的基线在 CI 上必然 flaky —— 等价于用新假门禁换旧假门禁。

### 连带结论：`ChatViewSSE` 拆分暂缓

评估 agent 给出的判断（复检官复核成立）：`ChatViewSSE.vue` 的功能性引用**只有
`router/index.js:51` 一处**（"20 个文件引用"是误传，其余全是注释里提到这个词）；
但三个测试文件共 **17 处 `readFileSync` 直接读 `.vue` 源码做正则匹配**、**零行为测试**，
CSS 一搬走约 19 条必红 —— **而那 19 条恰恰是唯一的安全网**。
更关键：唯一能验收 CSS 改动的门禁是 `continue-on-error: true`，
a11y 快照扫的是 aria/对比度、**不是视觉** ⇒ **CSS 改坏了现有门禁一条都抓不住**。

⇒ **CSS 拆分的前置条件就是第 2 条**（视觉回归转硬门）。顺序不能颠倒。

## 五点九、§4 待做清单（2026-10-04 复检官实测登记）

> S3 阶段本身**已无可待做**（八项实质工作全落地、五门禁全绿）。
> 本节登记的是**仍悬着、需要决策或立项**的项，按"能不能开工"分组。

### 4.1 卡在验收标准上（唯一需要你先决策的一项）

> **2026-10-07 更新（本节大部分已被后续进展取代）**：
> ① **CSS 抽取已于 2026-10-05 完成**：2973 → **1352**（`chatview-scoped.css` 888 + `chatview-global.css` 733），
>    棘轮已固化（`frontend-size-budget.txt` 同步 4 条新 `file|`）。commit 见 `eb8c074f4` / 补记 `d9be3dae3`。
> ② 本节阻塞点引用的 §3.9「视觉回归判死」已作废（§4.6）——基线已入库，且 §4.8 后
>    `62d122d40` 已撤 `continue-on-error` **转硬门**（`playwright.yml:359` 实测）。
> ③ **剩余 = script 拆分**（`script+template 未动`），前置条件仍是先补 mount 级行为测试
>    （现存 17 处 `readFileSync` 读源码钉正则、零行为测试）。
>    **→ 2026-10-07 已闭环：三阶段全过（行为测试 613 行 24 用例 → script 拆四模块
>    1352→755 → 棘轮 13007/13007），复检官逐条复验见 §4.13。**

**L-1 `ChatViewSSE.vue` CSS 抽取**（S3.6-3b 剩余，本阶段唯一原计划内未做项）

| | 实测值（2026-10-04） |
|---|---|
| 当前行数 | **2973**（棘轮基线同为 2973） |
| 可拆规模 | `<style scoped>` 891 + `<style>` 730 = **1621 行（54%）** |
| 引用面 | **只有 `router/index.js:51` 一处**（`resolveMobileComponent('chat/ChatViewSSE', ...)`）——"20 个文件引用"是误传，其余全是注释里提到这个词 |
| 测试兜底 | 三个文件共 **17 处 `readFileSync` 直读 `.vue` 源码做正则**、**零行为测试**；CSS 搬走约 **19 条必红**，而那 19 条是**唯一**安全网 |
| **阻塞点** | **CSS 改动没有自动验收手段**——见 §3.9 视觉回归实测判死 |

⇒ **开工前必须先回答**：是否接受靠「人眼 review + a11y 门禁」验收 CSS 改动？
今天已有 17 条对比度违规是被 a11y 门禁抓出的，所以该替代方案不算太弱，
但**会漏掉"布局错位但对比度正常"那类问题**（像素比对才能抓）。

### 4.2 从未评估（无方案，需先勘察）

> **2026-10-07 更新**：CSS 抽取已于 2026-10-05 完成——2151 → **1604** + `rail.css` 546
> （`@keyframes` 定义/引用同 hash 验证通过）；**script 1010 行定为不拆**
> （5 个轮询状态机、零行为测试兜底，拆分风险 > 收益，S3 段已明确记录）。

**L-2 `DriveDetailRail.vue`**（S3.6-3b 另一个热点）

| | 实测值（2026-10-04） |
|---|---|
| 当前行数 | **2151**（棘轮基线同为 2151） |
| 测试兜底 | `web/src/components/drive/__tests__/DriveDetailRail.test.js` — **9 个用例、零 `readFileSync`，是真实行为测试** |

⚠️ **与 L-1 的关键差别**：它的兜底是**行为测试**，而 `ChatViewSSE` 全是"读源码钉死物理位置"。
⇒ **L-2 的拆分可行性显著高于 L-1**，若要开热点拆分，**建议先做 L-2**。
仍需先勘察：被谁引用、边界是否可靠。

### 4.3 需要你给最终定位的悬置项

> **2026-10-07 更新：已闭环，本节三选项不再适用**。§4.6 基线入库（§3.9 判死作废）
> → §4.8 真 CI 连续两次全绿（失败数 10→0）→ `62d122d40` 撤 `continue-on-error` **转硬门**。
> 现行状态：visual regression 是阻塞合并的硬门，判据见 `playwright.yml:359` 注释。

**L-3 `visual regression` 门禁的归宿**

实测已证明它**无法转硬门**（§3.9）：同环境连跑两次基线自己会飘，
`maxDiffPixelRatio: 0.002` 下 1% 是地板不是噪声。
当前状态：`timeout-minutes: 20` + **`continue-on-error: true`**（非阻塞），跑完但 failure（118 缺基线）。

三个选项：**正式标记废弃**（像 `lint-css.yml` 的 `visual-regression-deprecated` 那样 `if: false` + 说明）
/ 维持现状 / 统一 CI 与本机字体栈后再议。**这是门禁策略面，须你拍。**

### 4.4 已知小账（agent 发现、按纪律未擅动）

| # | 项| 实测状态 | 性质 |
|---|---|---|---|
| L-4 | `FallbackBlock.vue` 残留 `:deep()` | **实为误报** —— 复检官核实该处（L35）位于 `<style scoped>` 块内（L25-38），`:deep()` 在那里**有效**，**不是死规则** | ✅ 无需处理（前一 agent 的报告有误） |
| L-5 | `secondary-routes` 6 条 `toBeVisible()` 失败 | **✅ 2026-10-07 复核：已闭环** —— `298160077`（登记当天 23:19）修复合入，0 条真 bug。两处派单前提被实测更正：①"6 条"实为 **3 个唯一失败** × `retries:1` 翻倍；②"`07` 找不到 `.mfd-info-card`"不成立（组件一直在 `MobileFileDetailView.vue:77`，07 实际死于更早的 strict mode 断言，该行从未执行到）。真 CI：run `37478883479` visual job 8/8 secondary-routes 实跑 passed（10-05 基线入库、10-06 转硬门后连绿） | ✅ 已闭环（本行 2026-10-04 原登记已过时） |
| L-6 | 移动端 dark 对比度两项 | **✅ 2026-10-07 关闭**：4.47→**4.556** / 2.31→**4.730**（复检官独立复算逐位吻合），另修 pre/code tint 2.024→6.113；确定性计算门禁 + 双向反向验证，CI 全绿（`de0292f08`/`5c9725db9`） | ✅ 已闭环——过程中挖出 **L-7** 级联 bug（见 §4.12） |
| L-7 | `variables.css` dark 文本色被 `:root` 盖死 | **✅ 2026-10-07 当日发现当日闭环**（`b124d49fa`+`dba1465f2`）：dark computed 恢复 `#a8aab0`（7.269/5.928 ≥AA），light `#6B6E76` 不变（4.600/5.101 逐位吻合），13 断言双主题门禁+反向验证，dark 基线恰 2 张按 diff 重录、47 张 md5 不变，两 head 全 CI 绿 | ✅ 已闭环（复检官复验记录见 §4.12） |
| L-8 | image-scan 每周 trivy 门禁连红 | 09-07→10-05 **五连红**，根因 = 镜像 HIGH/CRITICAL 真漏洞命中（门禁本身工作正常） | **🔧 2026-10-07 部分闭环**（`a091b9869`）：**146 条 OS/基线类 → 0**（复扫 run 37630728965：db/web 转绿、8/8 构建成功含 commercial/voice-pipeline 首扫即 OS 0）。**残留 68 条 pip 类**：**(i) ✅ 2026-10-08 闭环**（`f9e7defff`，见下方 §4.16）；**(ii) ✅ 2026-10-09 闭环**（`7db39f2b1`，见下方 §4.18 —— ⚠️ **原记"5 pin=43 条"的前提经实测证伪**，真实是 3 个 `==` pin 命中）；**(iii) pip vendor 12 条** —— 用户拍板不做（上游阻塞，`.trivyignore` 留档） |
| L-9 | image-scan 构建失败时静默跳扫描 | `Build image` 带 `continue-on-error` + 扫描步 `if: build success` ⇒ 双层失能不自知；Dockerfile 修复后链路已重通，模式仍在 | **✅ 2026-10-07 闭环**（`4ca93a76c`）：continue-on-error 改仅 PR 生效；反向验证 run 37588257049（非法 Dockerfile → build failure → 三扫描 skip → **job failure**）；顺带揪出 commercial/voice-pipeline **既存坏构建长期被吞**（before 对照 37587898637 job=success+全 skip 实锤），已由 L-8 修复 |
| L-10 | D5 题库 intent 口径过时 | **985/1000** 为过时大写 6 值（`gen780.py` 旧 `INTENT_TYPES`），分类器已改小写 8 类、精确比较 → 结构性永远 mismatch；映射证据表已备（DATA/ACTION/EXPLAIN 1:1，DEEP 含混） | **✅ 2026-10-07 关闭（选项 D）** —— 用户拍板"直接删除测试"，迁移失去对象；解剖留档作退役依据（§4.15），题库数据保留（smoke/归档仍用） |
| L-11 | D5 80% 门禁结构性恒红 | 三层解剖（§4.15）：口径层今日上限 1.5% + 本地时长层 86 纯时长杀 + 真质量层 33；双修理论上限 48.5~66% 仍 <80%；历史从未绿 | **✅ 2026-10-07 关闭（选项 D）** —— D5 workflow 整删（`08185c3da`，620 行，含每周 cron）；smoke 同型门禁按用户选项 1 摘判红保留探针（`fa66f4f66`，首转绿 run 37581862664） |
| L-12 | token-orphan 检查自身 2m28s + 超时静默失效 | `check-token-orphans.sh` 1386 条记录×每条 4+ 子进程；钩子 `timeout 30` 被杀无 summary → **永远报 "0 真 orphan"，该检查静默失效 18 天**（pre-commit 硬化时实测发现） | **✅ 2026-10-08 闭环**（两文件同批，**必须一起合入**）：① **内建化根治** —— `check-token-orphans.sh` 把per-record×4 源文件的 `grep -qE` 循环（5544 次 spawn）换成"单趟抽已定义 token 进关联数组 + 循环内纯 shell 查表"，另把 `echo\|cut` 字段切分（≈8316 次 fork）一并换成参数展开。实测 **3m37.5s → 0.498s（~437×）**，orphan 数 0 / 白名单 64 / 退出码 0 三项与基线**逐一致**（`git stash` 对照实测，非推断）；差分验证：独立 awk 复算 379 vs 379 定义集相同、147 个被引用 token 逐个比对原 grep 判定全PASS、反向379 键全被原 grep 确认。② **fail-loud 防线** —— `check-dist-before-commit.sh`去 `\|\| true`，按退出码 `case` 分派（0 放行 / 1 原有报错文案 / **124 超时→诊断+`exit 1` 阻塞** / 2 配置错误 / 未知码一律 `exit 1`）；`-x` 改 `-f` 堵第二条静默路径（本仓 `core.fileMode=false`，丢 exec 位即整项静默跳过）；判定不再靠正则刮 stdout，`ORPHAN_COUNT` 降级为纯显示。**五条路径实测**（含真 `sleep 40` 撞满 30s 验证 `timeout` 真返回 124 后被拦下）。假绿物证：`docs/CLAUDE-history.md:4950`/`:5210` 的 `✅ 0 orphan` 即超时产物 |
| L-13 | build-image 60min timeout 冷构建取消 | L-8 base 升级后冷缓存重建撞既存 60min job timeout 被 cancelled（10-02 `e4124af26`/`99a35fa23` 同因先例），ghcr app-test 新基线未推出 | **观察项** —— 网络窗口好时可手动 dispatch 重跑（同类构建 15min）；调 timeout/cache 属 workflow 面，2026-10-08 登记 |

---

## 五点十、§3.9 视觉回归实测判死（2026-10-04）

`pathTemplate` 去掉 `{snapshotSuffix}` 后，"找不到基线"从 **118 → 0**（`1dc4bc97b`，真问题已修）。
但同一次实测证明**这道门禁无法转硬门**：

| 场景 | 结果 |
|---|---|
| Windows 录 → Linux 比 | **0/118 通过**，diff ratio **0.01–0.20**（阈值 0.002，最小值即 5 倍） |
| Linux 录 → Linux 比（第一次） | 前 118 个 0 处不符（看似完美） |
| Linux 录 → Linux 比（**第二次**） | `iphone-se-01-list` 立刻炸，1323px / ratio 0.01 |

开图确认根因：**每个文字字形都被标红**，版式/间距/颜色/布局全部对齐，`actual` 图页面完全正常。
⇒ 差异 100% 来自 Windows/Linux 的**字体栅格化与 hinting**。
⇒ **同环境连跑两次自己会飘**，说明基线自身不稳定 —— 这直接判死"改在 Linux 录"这条退路。

**推论**：L-1（`ChatViewSSE` CSS 抽取）的前置条件不成立，
因为**唯一能验收 CSS 改动的手段就是像素比对**。

### 顺带留档：人工 review 不可省

118 张基线在提交前被逐张开图看，发现：
- 大部分正常（完整渲染的评论页，非空白页）——历史那 3 张"三张字节数完全相同 = 纯白登录页"
  的问题**没有重演**，证明 review 确实拦住了问题；
- ⚠️ `iphone-12-01-list` 是**暗色/空态**（"加载失败，点击重试"），数据依赖 ⇒ 潜在 flaky 源；
- ⚠️ 同 device 内 4 个 step **字节完全相同** ⇒ 查询参数差异未反映到 UI，属**弱断言**。

### 4.5 应用代码里的**第三处墙钟源**（S3.12/13 实测发现，**2026-10-09 已闭环**）

> **✅ 2026-10-09 闭环**。用户拍板「四处全改 + 可注入参数 + 只给 `useNow` 写单测」
> （B + A + A）。commit `ff9ef524b`（源码）+ `93daa7344`（dist），
> **真CI run `37810087503` 视觉回归全绿** ⇒ 四处收敛对像素输出零影响，
> libfaketime 正交性由推断升级为实证。详见本节末「落地结果」。

#### 勘察更正的三处偏差（计划文档原描述与代码实情不符）

| # | 原描述 | 代码实际 |
|---|---|---|
| 1 | 三处墙钟源 | **四处** —— 漏了 `useRAGEval.js:34`（与 useKbMonitor 完全同构，消费于 `RAGEvalPanel.vue`） |
| 2 | `MobileDashboard` 用 `new Date()` | **用 `dayjs()`**，注入层需覆盖两条路径 |
| 3 | 消费点是 `MobileProjectStatsView.vue` / `ProjectStatsView.vue` | `MobileProjectStatsView` **不是**消费点（已核实无引用）；实际是 `ProjectStatsView.vue:362`（渲染秒级时间串）+ `KbMonitorView.vue:456`（**只作 v-if 开关，不渲染时间值**） |

**两处附带发现**：
- `useKbMonitor.test.js` 现有 3 个 `it()` 块**无一条断言碰 `lastUpdate`** ——
  引入相对时间测试是全新测试面，不是补洞
- `MobileDashboard` 有**真实 bug**：`dayjs()` 非响应式依赖，computed 求值一次后永不重算，
  greeting/日期 **latch 在首屏**，跨小时/跨午夜不更新

#### 落地结果

新增 `web/src/composables/useNow.js`（唯一入口）：
```js
export function useNow(intervalMs = 0, clock = () => new Date())
// 返回 { now: Ref<Date>, tick: () => void }
```
- **照仓库既有惯例** `web/src/utils/timeDivider.ts:14` 的 `formatTimeDivider(date, now = new Date())`
  —— 可选参数做依赖注入，缺省落回真实墙钟
- **墙钟缺省是硬约束**：`docker/visual-regression/run-visual.sh` 用容器级
  `LD_PRELOAD=libfaketime`（`VIZ_FAKETIME=2026-10-05 10:00:00`）冻结时钟。
  缺省保留墙钟 ⇒ libfaketime 与「应用代码是否经由 composable 取时」保持正交；
  **做成强制注入无缺省则会打破这条正交性**（已实测两 job 均为 `npx vite` dev server，
  全仓无 `vite preview`，从 `web/src` 出图）
- `intervalMs=0` 不起定时器；`>0` 走 `setInterval` + `onUnmounted` 自动清
- 单测 7 case 全过

**四处收敛**：

| 位置 | 改法 | tick |
|---|---|---|
| `useKbMonitor.js` | `useNow(0)` + 成功分支 `tick()` | 不起定时器 |
| `useRAGEval.js` | 同上 | 不起定时器 |
| `MainLayout.vue` | `useNow(20000)` 替换手写 `ref + setInterval` | 20s（原值） |
| `MobileDashboard.vue` | `useNow(60000)` + `dayjs(now.value)` | 60s（新增，顺修 bug） |

**最关键的正确性判断 —— `lastUpdate` 语义不能被改坏**：
`useKbMonitor`/`useRAGEval` 的 poll 是 5min，但 **`lastUpdate` 只在 poll 成功那一刻打点**。
`useNow.js` 的 `now = ref(clock())` 是**创建时刻快照**，`tick()` 每次重新赋新`Date`。所以：

- `useNow(300000)` + 直接读 `now.value` **错** → 每5min 都推进，失败轮次也推时间，
  用户看到「2 分钟前更新」实为 25 分钟前的陈旧数据
- `useNow(0)` 直接读 `now.value` **错** → 变成「页面挂载时间」，丢失新鲜度语义
- **正解**：`useNow(0)` + 成功分支先 `tick()` 再读 `now.value`

（两个执行 agent **各自独立**读源码后选了同一方案并给出同一理由。）

**渲染输出逐字未变**：`clockChip` 函数体 0 diff、greeting 阈值 `<6/<12/<18` 0 diff、
format 串 `YYYY年M月D日 dddd` 0 diff。**run `37810087503` 实测49 张基线逐字节匹配。**

**一处有意保留（非漏改）**：`MainLayout.vue` 的 `isoWeek`（档案印章 ISO 周号）是 IIFE，
壳层每次加载算一次，非响应式时钟依赖、不参与 UI 刷新逻辑。套 `useNow` 反而是
为静态值起定时器的无谓改造。

#### 建议的立项内容（本轮**未做**，超出"让门禁可判定"范围）：

`useKbMonitor.js:41` 的 `lastUpdate.value = new Date()` 渲染进
`MobileProjectStatsView.vue` / `ProjectStatsView.vue:362` 的**秒级**时间戳
（`lastUpdateStr`）。

**为什么单独立项**，尽管视觉回归门禁当前已把它冻住：

- 门禁侧已用 `libfaketime` 把容器墙钟钉在 `2026-10-05 10:00:00`，
  所以这道时间戳在基线里是稳定的 —— **门禁绿**。
- 但它是**应用代码里的独立时钟依赖**，与另两处同类问题性质不同：

  | 位置 | 性质 | 影响 |
  |---|---|---|
  | `MainLayout.vue:232-246` `.tchip` | 装饰性时钟牌 | 显示 |
  | `MobileDashboard.vue:171-181` greeting/日期 | 问候语按小时变 | 显示 |
  | **`useKbMonitor.js:41` lastUpdate** | **数据新鲜度指示** | **语义** |

- 第三处最值得单独看：前两处只是"显示"，这一处是**语义** ——
  用户靠它判断 KB 数据新不新。若将来引入任何"相对时间"渲染
  （如 `3 分钟前`），它会从"显示"升级为"逻辑"，届时任何未钉死的时钟
  都会让断言与 UI 同时漂。

**建议的立项内容**（本轮**未做**，超出"让门禁可判定"范围）：

1. 抽一个 `useNow(intervalMs)` composable，把"取当前时间"收敛成**单一入口**，
   使测试可注入固定时钟（避免每个视图各写 `new Date()`）。
2. 给它补一条单测：注入固定时刻 → 断言渲染出的时间串。
3. 明确"哪些时间必须可注入、哪些就该用真实时间" —— 如审计日志的时间戳
   **必须**是真实时间，不能冻结，否则就是伪造证据。

### 4.6 视觉回归基线已入库，§3.9 的"判死"结论作废

§3.9 记的是"视觉回归实测判死，无法转硬门"。**该结论已被 S3.12/S3.13 实测推翻**：

| §3.9 的判断 | S3.12/S3.13 实测 |
|---|---|
| 同环境连跑两次自己会飘 | 飘的量是 **2 像素、色差 1/255、ratio 0.000006**，位置在 `.mfcc-tabs` 标签栏边缘，**不是文字字形**；现有 threshold 完全吸收 |
| 差异 100% 来自字体栅格化 | 主因是**字体没锁**（不是"Windows vs Linux"）：裸 runner 上 `fc-match "Segoe UI"` → WenQuanYi Zen Hei，**装 fonts-noto-cjk 也不生效**，必须配 fontconfig `mode="assign" binding="strong"` 别名 |
| 无法转硬门 | 治因后 **46/118 字节不一致 → 3/117**；本地真实门禁入口连跑两次结论一致（`V=0, 50 passed, 3 skipped, 4 min`） |

**当前状态**：环境可判定 + 基线已入库（50 张 / 44 个不同画面）。
`continue-on-error: true` **尚未撤掉** —— 撤掉前应先让真 CI 连跑两次绿。

---

### 4.7 两笔独立小账（S3.14 真 CI 首跑带出，均**未擅动**）

#### (a) `/tasks` 路由：注释说"纯冗余"，但同一段注释又给出了保留理由

`web/src/router/index.js:55-62` 原文：

    // 批次⑩.80: 任务管理完整迁入仪表盘 (合并页), 旧地址重定向保兼容
    // 批次⑩.82: 去掉 meta.icon 删除侧栏入口 (点击本就重定向回仪表盘, 纯冗余);
    // 路由保留作 fallback — 仪表盘任务卡「任务管理 →」/ 对话深链 {name:'Tasks'} / 老书签
    path: 'tasks',
    redirect: to => ({ path: '/dashboard', query: to.query }),

⇒ **"纯冗余"只针对侧栏入口那一条**（批次⑩.82 删 `meta.icon`）；
   紧接着的第三行明确说路由**保留作 fallback**，有三重真实引用：
   仪表盘任务卡的「任务管理 →」、对话深链 `{name:'Tasks'}`、老书签。

**结论：路由本身不该删**（删了会破三个引用点）。
真正该清的是**视觉回归里那条 `04-tasks` 用例** —— 它想截的页面
（独立任务页）已不存在，保留它等于在测 router 的 redirect 而非测 UI。
S3.14 已从 `CORE_ROUTES` 移除该路由。

⇒ **账归到这里**：不是"路由冗余待删"，而是"**测试用例测了一个不存在的页面**"。
   下次若有人想删 `/tasks` 路由，**先看这三行注释**。

#### (b) `useKbMonitor.js` 见 §4.5（同一批时钟源，此处不重复）

---

### 4.8 视觉回归门禁：**已在真 CI 上连续两次全绿**（S3.17 收口）

真 CI 两次 `workflow_dispatch`（main，`visual` 的 **test step**，不是 job 结论）：

| run | 结果 | 耗时 |
|---|---|---|
| `37257035227` | **48 passed / 1 flaky / 3 skipped** → step 10 **success** | 12.3m |
| `37258549987` | **49 passed / 0 flaky / 3 skipped** → step 10 **success** | 10.7m |

其它门禁同时全绿：`axe-core a11y`（50 passed）/ `Lint CSS` / `RAG Framework CI` /
`Secret Scan`。

**环境钉死在 CI 上逐次实证**：

    ✓ 字体已锁: Segoe UI -> Noto Sans CJK SC
    ✓ 时钟已冻结: 2026-10-05 10:00:00Asia/Shanghai (monotonic 不冻结...)

### 失败数演进（每一步都是真CI 实测，不是本地推断）

| 阶段 | 真 CI |
|---|---|
| 基线未入库 | cancelled（22min 撞 25min 上限） |
| 基线入库 | 39 passed / **10 failed** |
| S3.14 预热 + 移除 `/tasks` + 重录 `03-chat` | 45 passed / **4 failed** |
| S3.15 chat-topbar 预热 | 48 passed / **1 failed** / 2 flaky |
| S3.16 修预热引入的 30s 超时 | 46 passed / **1 failed** / 2 flaky |
| **S3.17 修"先判断后等待"顺序** | **0 failed** ✅ |

### 三条根因（都不是阈值问题）

1. **vite 的 `504 (Outdated Optimize Dep)`** —— 首次请求异步 chunk 时触发依赖优化，
   对已加载模块返回 504 → 动态 import 失败 → 组件不挂载 → 纯白页。
   本机 vite 已预热**从不复现**，CI 冷启动**必然命中**。
2. **等待逻辑写成了"先判断、后等待"** —— `count()` 紧跟 `goto` 立即执行，
   下面的 `waitFor(15s)` 根本没机会跑。本机组件秒级就绪 ⇒ **本地永不复现**。
3. **`/tasks` 是无条件 redirect** —— 用例测了一个**不存在的页面**。

### ⚠️ 留给下一轮的三件事

1. **`continue-on-error: true` 仍保留**。虽然已连续两次绿，但**只有一次绿不能撤**——
   至少再连 2-3 次绿、且中间有一次真回归被抓住，才考虑撤。
   判据同今天对四道"假门禁"的做法：**先证明它会红，再让它有牙**
   （这一步已做到 —— 10 处失败时它确实报红）。
2. **1 次 flaky 尚未定位**（`37257035227` 抓到，`37258549987` 未复现）。
   `retries: 1` 目前是唯一兜底。撤 `continue-on-error` 前应先把它根因查清。
3. **`10-project-stats` 的 fixture 枚举必须照抄视图期望值** ——
   `status: 'active'` 而非 `'in_progress'`（`MobileProjectStatsView.vue:87`），
   否则 mock 静默失效、页面落空态。

### 一条方法论（今天反复栽的形态）

**"我修的"和"真凶"可能不是同一个。** S3.16 看到 `Test timeout` 就认定是预算问题，
加超时确实让那处不再超时，但**真凶是顺序写反导致等待逻辑从未生效**。

⇒ 纪律：报错信息指向的**行号**要去看，不要停在"错误类型像什么"；
   本地绿不能证明什么 —— **只有真 CI 能暴露**。

### 4.9 D5 千题首次完整跑通；三层掩盖剥到第四层：恒红门禁（2026-10-06）

**S3.22/S3.23 两个修复经真 CI 双重证实**（run `37426104585`，sha `d9ba82564`）：
- `Run qa-bench D5` 步 **success**：artifact `results.json` 实测 count=1000、
  summary.total=1000、error=0（路径修复让它真加载 1000 题）。
- summary 含 `seven_dim` 键、`report.md` 18129 行含 `## 7 维评分汇总 (v3.0)` 段
  （该段必须 `seven_dim` 存在才渲染 —— KeyError 修复生效）。
- 同链四层掩盖至此剥完：① 步骤顺序死锁 117min→22s（`296423f21`）
  ② 路径加倍 FileNotFoundError（S3.22）③ `seven_dim` KeyError（S3.23）
  ④ **401 凭据 + 恒红门禁脚本** ← 当前层。

**第四层的两个成分**：

1. **401 Invalid API Key（凭据，待用户决策 —— 不是代码问题）**：
   artifact 实测 **1000/1000 题全部含 `Error code: 401 ... Invalid API Key`**
   （每题 6 个唯一事件 × `issues[]`/`round_results[]` 双存储 = 12000 原始出现）。
   日志 `-e MIMO_API_KEY="***"` 证明 key **非空**（GitHub 只掩码非空值），
   是被 mimo 上游拒绝（过期/失效/额度）。通过率 0.0% 是这个根因的结果。
   ⚠️ 诚实边界：D5 近 400 次 run success=0，**不存在"曾经 ≥80%"的历史基线**。
   决策点：换 key、还是重新定位这道门禁。

2. **恒红门禁（"假门禁"第五型，与恒绿相对）**：
   `qa-bench-ci.yml:570-579` 第二个 heredoc 写成**带引号** `<< 'PYEOF'`，
   `${PASS_RATE}` 永不展开 → `float('${PASS_RATE}')` 必抛 `ValueError` →
   步骤在阈值检查**之前**就崩，`❌ 通过率...` 从未打印 —— **通过率 100% 这个门
   也过不去**。`qa-bench-smoke.yml:254` 同款。日志实锤 run 37426104585。
   连带发现：门禁步 `if [ -f results.json ]` 守卫在文件缺失时**静默 exit 0**
   （恒绿形态），应改 fail-loud。三处 + smoke 路径加倍已派工修复中。
   ⇒ 判据补充：**门禁红也不等于门禁在工作** —— 要看它是"按判据红"还是"崩红"。

### 工具可信度：`gh run list --branch main` 在本机不可信（2026-10-06 实测）

同一查询（`--branch main --limit 10 --json ...`）连发三次返回三个不同年代的结果
（10-06 / 09-18 / 09-17 各一批），一度造成"main 上有陌生新 commit"的误判。
原始 API `gh api "repos/<owner>/<repo>/actions/runs?per_page=N"` 三次结果一致、
时序连贯 —— **验收一律走原始 API**。另：本仓有两个 git 仓（父仓 + 嵌套
desktop-conversion），`gh` 默认解析到嵌套仓（0 runs / 404），必须显式
`-R gg320324492-lgtm/microbubble-agent`。

### 4.10 CI 链路三轮收尾 + a11y 关闭（2026-10-06/07 复检官逐笔实测）

**a11y `render-evidence` 恒定 −1 关闭（`f8ea10add`）**：
- 定案：少的 1 个元素 = `.breadcrumb-status > span.status-dot`（6px 装饰圆点，
  CSS 漏 `flex-shrink:0`，父级 flex 将其挤成 0 宽 → 不计入可见元素）。
- DOM 两侧 429=429、文本 468=468、1270px 元素集 diff 仅此一个、恰好 4 张
  （仅 `/chat` 路由有该元素 × 2 页面 × 2 桌面项目）——与 CI「4 红 / 21 绿」逐张吻合。
- 4 张基线重录**只动 `render-evidence` 一行**（`468:224→223`，复检官 diff 纯度实测：
  `violations` 等逐字节未动）；`test_authed_field.py` 仅 2 个标定值，**判据逻辑 0 改动**。
- 真 CI：Playwright 在 `f8ea10add` 与 `484632d80` **连续两次 success**
  （此前 `71e496281`/`fb7a64ad6`/`66933ec4a` 三 SHA 连红，此笔翻绿，时间线自洽）。
- 诚实边界：塌陷机制坐实；**CI 侧"变窄的触发因子"未坐实**（agent 自纠了字体假设，
  订正进 commit——不把猜测固化成结论）。

**恒红门禁修复（`71e496281` + `fb7a64ad6` + `484632d80`）**：
- 两道通过率门的带引号 heredoc 改 env 前缀传值；真 CI 实证：D5 `❌ 0.0% < 80%`
  （`ValueError '${PASS_RATE}'` 从必现→0 次）、smoke `❌ 0.0% < 80%`。
- 门禁补 fail-loud（results.json 缺失拒绝静默绿）+ 本地三情形反向验证
  （90 绿 / 70 红 / 缺失红）两门六格全过。

**smoke 从「从未跑完」到「跑到底的正常红」（三轮七笔：`f8ca10bb6` → `25bd105b7`
→ `0c1c0c7bd` → `5f21236c1` → `c3507e9ca` → `08266da1a` → `275c56f16`）**：
- 四层根因链（每层都有 CI 实证）：
  ① 本地 build 撞 10min timeout（近 10 次 run 全砍在 build）→ 改拉 GHCR 预构建
  （`build-image.yml` 路线 D5 早已迁移、smoke 从未——**路线遗留**）；
  ② 门禁读**入库的六月旧** `results/smoke/results.json`（33.3% 假数据）→
  加 runner step outcome 守卫（不删归档文件，先判 outcome 再读）；
  ③ fvD 步排在门禁后永不可达 → 移前 + timeout 10→15（逐段时间戳复算）；
  ④ 三处照抄 D5 先例：fvD `api_base` 死参接通（打 8000 挂死）、
  token 弃 `:-mock` 改 Login 真 JWT（D5 W67 第 42 步同型教训）、
  DB 换 pgvector 镜像 + CREATE EXTENSION 重试 + `set -o pipefail` 掩绿修复
  （此前 `f405` 报错被 `| tail` 掩成假 success）+ `\dt` 表数 fail-loud 断言。
- 真 CI run `37495244457`（head `275c56f16`）：**run 级 failure（不再是 cancelled）**，
  唯一红步 = 门禁 `❌ 0.0% < 80%`（本次新鲜数据）；fvD success 且 0 ConnectError；
  `Login OK token 141`；`✓ 建表验证通过: public 表数 = 61`；全程 2.78min（timeout 15 余量足）。
- **第 5 缺陷（agent 自曝、已修复 `443a1c09f`，真 CI run `37497190067` 实证）**：
  fvD 调 `score_seven_dim(result)` 老单参 → 每题 `TypeError` 被吃进 error
  （报告 30/30 错误、7 维分表全 0）。正解按复检官拍板执行：复用
  `run_single_question` 返回值自带的 `seven_dim`（`runner.py:987`），不动 runner.py。
  修后真 CI：fvD success、`完成: 30 题, 0 错误` ×3 mode、报告错误数 0/0/0、
  7 维分表真实数据 0.75/0.7/0.84（artifact 下载复核）。
  诚实边界：0.75 是降级后端（401 链路）下各维度默认满分/中性分的合法计算结果，
  **不代表答案质量**；Token 表 `0 (n=0)` 是 `run_single_question` 不返回 usage 的
  既有状态（改它需动 runner.py，未动）。
  注：该 commit 署名行误拼 `Co-authorized-By`，已按先例以空提交 `130519084` 更正。
- **方法论沉淀（本节最重要的一条）**：**门禁红 ≠ 门禁在工作**——崩红（ValueError）、
  读旧数据红（六月 33.3%）、没跑到红（cancelled）是三种不同的病；同一条 qa-bench 链
  先后掩盖五层：死锁 117min → 路径加倍 → `seven_dim` KeyError → 恒红 heredoc → 401 凭据。

### 4.11 BUILD_ID 根治（R-5 落地，2026-10-07 复检官独立复验）

**设计（实现见 `web/vite.config.js` 顶部注释，CLAUDE.md W100 已同步改写）**：
- `BUILD_ID` = 构建源输入**允许清单**（`SOURCE_INPUTS`：src/index.html/public/vite.config.js/
  package*.json/postbuild 脚本）内容 sha256 前 12 hex；`BUILD_TIMESTAMP` = 同清单的
  `git log -1 --format=%cI`（语义 = **源码最后修改时间**，非构建时刻）。
- **反循环**：允许清单从磁盘读字节，`dist` 物理进不了哈希输入 ⇒ 提交 dist/docs 不改标识。
  这是本方案的命门——曾有"用 HEAD:web 树哈希"的初案，因 web/ 树含已入库 dist 会
  **永不收敛**（每次提交 dist 都改变 ID → 又得重建），被否决。
- **fail-loud 按模式分流**：`vite build` 遇 git 不可用/浅克隆空 path-log → throw（类 20.133
  正主——保护 dist 产出）；dev/serve → 确定性降级（空 path-log→tip 时间、无 git 容器→
  固定哨兵 `no-git-dev`），dev 产物不入库。
- **入库顺序纪律（新）**：源输入改动必须**先提交、再 `npm run build`、再提 dist**——
  原子 src+dist 会让 timestamp 滞后一个源提交（`e50631024` 实战修正）。

**验收（复检官独立复做，非引用 agent 自报）**：
- tip `5c9725db9` 上亲手 `npm run build` → `git status --porcelain web/dist` = **0 行**
  （新构建与入库 dist 逐字节一致 = R-5 根治的最终形态）；
- agent 侧：两连跑同 ID、docs commit 后重建恒等（`6dff159e7`→`2a98878d4` 与
  `a116187b5`→`77accc322` 两轮 `diff -r`=0）、无 git build exit=1 / dev 正常；
- CI：`8288cd2aa` 起 Playwright 连绿（含 49 passed 实跑铁证），tip RAG/Secret 绿；
- CLAUDE.md W100 改写与代码真值逐条比对一致（防规范漂移——复检官读现行段落核对）。

**过程中挖出的两个副产物**：
1. **fail-loud 用错对象事故（当日即修）**：v1 把 git fail-loud 无差别用在 dev serve 上 →
   钉死视觉容器（无 git）配置加载即炸 → visual 门禁红。**教训：类 20.133 保护的是
   dist 产出，不产 dist 的 dev 通道要走"确定"分支，不是"响亮失败"分支。**
2. **先存死配置**：`vite.config.js` 存在重复 `build:` 键（后者覆盖前者）→
   `rollupOptions.hashCharacters:'hex'` + `manualChunks` **早已失效**（旧入库 dist
   323 个文件名含大写字母 = base64 实证）。修复会改变全部 chunk 切分 = 大 churn，
   **超本任务面未动，留档待立项**。

**遗留（待拍板）**：① `web/Dockerfile` 的 `RUN npm run build` 在无 git 容器内，下次
`web/Dockerfile` 变更触发 image-scan 时会红——修法候选 = `ARG VITE_BUILD_ID` 显式固定
输入（类 20.133 允许）；② 入库 dist 的 pre-commit 检查目前仅 advisory，硬约束需改
hook（他人面）。

> **2026-10-07 更新：两件潜伏项双双闭环（用户拍板"逐项做"）**
> - **① Dockerfile 无 git 构建 → 已修**（`092fe0531` + dist `34c08b207`）：
>   vite.config 新增**显式固定输入通道** `VITE_BUILD_ID`/`VITE_BUILD_TIMESTAMP`
>   （非空才采用、空/缺省一律回落 git 派生 fail-loud——主路径未削弱，这正是类 20.133
>   原文允许的"CI 提供固定输入"）；Dockerfile `ARG` 默认哨兵 `docker-no-git`
>   （仅存在于镜像内扫描副本，不入库不部署）。复检官**三步端到端独立实测**：
>   干净构建 `source-derived` → dist 0 脏；env 构建 `固定输入` → 哨兵真进产物；
>   恢复构建 → 0 脏。反向验证（空 build-arg）仍 fail-loud。
> - **② 重复 `build:` 键 → 已修**（`bf25c7100` + dist `2a44d64f8`）：合并为单键 =
>   当前生效块（`cssMinify:false`/`cacheDir:''`），死块 `manualChunks`/hex hash
>   **有意不启用**并留 24 行注释写明立项路径（生产 chunk 图零测试覆盖，启用=发未验证
>   产物）。复检官独立归一化多重集比对：365→365 文件 **MULTISET-IDENTICAL**、死块
>   chunk 0 个——行为保持证实。死键证据：esbuild `duplicate-object-key` + 357/365
>   文件名含大写字母（base64）。
> - **副产物发现（新登记 L-8/L-9，未动）**：
>   **L-8** — image-scan 的 **每周 cron trivy 门禁已连红 5 周**（09-07→10-05，根因 =
>   镜像 HIGH/CRITICAL 真漏洞命中、门禁在正常工作）——**需立项决定是否修漏洞**；
>   **L-9** — image-scan `Build image` 步带 `continue-on-error: true` 且扫描步
>   `if: build success` ⇒ 构建红时**扫描被静默跳过**（双层失能不自知；本次 Dockerfile
>   修复让构建恢复成功、链路重通，但模式仍在）。
> - ③ pre-commit dist 检查仅 advisory —— **✅ 2026-10-07 深夜闭环**（用户拍板三项之三）：
>   硬化落地（源 `6ca417c95` + dist `10a1172d8`，R-5 两段式实弹示范）——**禁原子 src+dist**
>   + **stale-dist 硬校验**（BUILD_ID 按 index 状态重算比对，算法提取为单一真源
>   `web/scripts/build-id.mjs`，vite.config 与钩子共用，四方等价实证）+ 自动补 add 收敛为
>   dist-only 场景。scratch 12 场景矩阵全过后装钩子；复检官在主工作树**实弹反向验证**：
>   原子提交被拦、HEAD 不动、三方 BUILD_ID `09231a1ef86e` 一致、还原 0 脏。
>   **两件连带发现**：(a) wrapper 自 `18d6625ec` 起无退出码传播——secrets/dist/drift 三道
>   "硬拦"**历史上从未真正拦下任何 commit**（scratch 首轮实证：文案打印、commit 照过），
>   已修（`|| exit 1`×3 + `--check` 校验传播）；(b) `check-token-orphans.sh` 自身 2m28s，
>   旧 `timeout 30` 被杀无 summary → **该检查在超时下静默失效 18 天**（登记 L-12）。

### 4.12 L-6 关闭 + 挖出 L-7 级联 bug（2026-10-07 复检官独立复验）

**L-6 关闭（`de0292f08` + dist `5c9725db9`）**：
- 复检官**独立复算六组 WCAG 比值全部逐位吻合**：登记值复现 4.473/2.307 →
  修复后 **4.556 / 4.730 / 6.113**（均 ≥AA）；light 三值 12.115/4.833/3.376 不回归。
- 违规定位：`MobileMessageBubble.vue` + `mobile-glass.css`（移动端专属 scope，类 20.188 核实）；
  用户气泡渐变是双主题同声明故 token 双主题同修，助手对是 dark 块专属只加 dark override。
- **门禁覆盖决策（为什么 axe 加不了）**：两处背景都是 `background-image`（linear-gradient /
  radial 极光）→ axe color-contrast 对 background-image 只报 incomplete、对极光只读
  `background-color` 算出 ~5.9 **假通过**——改回旧值也永远不红，过不了反向验证。
  改为**确定性计算门禁** `bubble-contrast.test.js`（292 行 9 断言，解析真实 CSS 接线 +
  512 点渐变采样 + 逐层合成 + light 不回归锁），跑在 Lint CSS 的 vitest 实门；
  反向验证双向红（旧色 → 报错原文恰为登记值 4.473/2.307）。
- 视觉基线 **0 张需重录**（light 欢迎气泡字节不变、无 user 气泡/dark chat 基线）——
  CI 对未改动基线在 verify 模式绿，实测 diff=0。
- 真 CI：Playwright run `37509065816` @ `5c9725db9` success；Lint CSS @ `de0292f08`
  success（stylelint 0 + vitest 实门含新测试）。

**L-7 新登记（C 路发现、复检官级联分析独立坐实、已派修）**：
`variables.css:1815` 的 `--color-text-secondary: #6B6E76`（+rgb 1816）写在 **:root**，
与 `:root` 行 48 原值、`[data-theme="dark"]` 行 809 的 v69 提亮值**同特异度且更靠后**
⇒ **dark 主题 computed 被盖成 #6B6E76**（Chromium 实测 + 级联分析双证）——暗色全站该
token ≈2:1，且该值在任何深底到不了 4.5，组件级无解。1813 块注释明写"只调 light、
**不动 dark**"——**注释与行为正好相反**（铁律型错误）。
修法（外科手术）：仅两条覆盖型声明改 light-scoped，dark 恢复 `#a8aab0`；新增型 token
不整块挪（dark 会变 undefined）。连带处置：钉该 token 的 `grade-tag-extension` spec、
dark 视觉基线（`mobile-ux-v3-dark` 等**确有覆盖**）按实测 diff 重录、light 基线零变动、
双主题 ≥4.5 确定性门禁 + 反向验证。
  **→ 已闭环（2026-10-07，源 `b124d49fa` + dist `dba1465f2`）**：Chromium computed
  双主题实测 light `#6B6E76` / dark `#a8aab0`；复检官独立复算 7.269/5.928/4.600/5.101
  四值逐位吻合；277 行 13 断言新门禁 + 反向验证（裸 `:root` → 7 failed 含结构守卫）；
  `grade-tag` spec 那处引用是未被使用的死字符串（实断言不钉值，无需改）；
  视觉基线 verify 模式实测 diff **恰 2 张**（orange-dark desktop/tablet）且仅重录这 2 张、
  其余 47 张 md5 前后不变；两个 head 全 CI 绿（Lint CSS vitest 151 文件 1504 passed）。

**L-6 范围外已登记未动（C 路如实上报）**：light `.msg-meta` 3.376（已加 ≥3.37 不回归锁）、
`.msg-error` #E26A6A dark 3.615、`--mg-gradient-btn` 白字面 ~20 处（同 2.31 家族，改则波及
全部移动基线）、EventBadges 瞬态徽章色。

### 4.13 L-1 关闭：ChatViewSSE script 拆分三阶段全过（2026-10-07 复检官复验）

**阶段与 commit**：
- `6b407a5d9` 阶段1：`ChatViewSSE.behavior.test.js` **613 行 24 用例**（真 mount：发送流程/
  Enter 守卫/SSE 流 mock/停止互换/会话切换+断线续答/对话内搜索/附件错误态/重生成/离线横幅）。
- `3eafc48e1` 阶段2：script **927→330**，拆 4 模块入 `composables/chat/`
  （Composer 478 / Scroll 205 / Search 140 / BackgroundPoll 89）+ Scroll 独立单测 7 用例。
- `4f340b97d` 阶段3：棘轮 `ChatViewSSE.vue 1352→755` + 新登记 `useChatViewComposer.ts|478`。
- dist 由并行 L-7 按 R-5 两段式入包（`dba1465f2`）；L-1 途中撞上"BUILD_ID 卷入他人未提交
  字节"——**主动停下协调而非强行构建**（新纪律的正确用法）。

**复检官独立复验**：
- **template/style 逐字节不动**：自己写提取脚本比对拆分前后 `<template>`（15410 字符）
  与 2 个 `<style>` 块——**完全一致**；
- 行数实测 755/478/205/140/89 逐个吻合；行为测试 `readFileSync` 实际调用 **0**
  （唯一命中是注释文字"不读一行源码"）；
- 17 源码钉盘点：文件级总数吻合（A11y 2 + W100Plus61 3 + W100Plus55 12），**仅 1 处
  script 钉迁移**（④b 钉的是零调用死 import，迁为 mount 级 props 契约断言，迁移注记在
  `W100Plus55...:31`），其余 CSS/template/越界钉零裸删；
- 棘轮 `sh scripts/frontend-size-budget-check.sh` → **exit 0，13007/13007 精确平衡**；
- tip `dba1465f2` 我亲手 `npm run build` → `git status web/dist` = **0 脏**（含全部本轮
  改动的终局收敛）；
- CI：三阶段 head 各四门 **12/12 绿** + 终态 head 全绿；无视觉 diff（script 拆分不动渲染）。
- 小瑕疵留档：阶段1 commit message 里钉子分桶数（CSS 12/越界 2）与详表（CSS 10/越界 3/
  死读 1）不一致——总数 17 与"仅迁 1"两边一致，分桶是描述性笔误（历史不改写）。

### 4.14 收尾计划工程项全清（2026-10-07 终态）

§4 待做清单六项 + 挖掘项全部闭环：L-1 ✅（§4.13）· L-2 ✅（CSS 抽出、script 定不拆）·
L-3 ✅（visual 转硬门）· L-4 ✅（误报无需处理）· L-5 ✅（`298160077`）· L-6 ✅（§4.12）·
L-7 ✅（§4.12 当日闭环）· R-1/R-3 ✅（§3.1/3.3）· R-5 ✅（§4.11）·
恒红门禁/smoke 五缺陷/fvD 两断点 ✅（§4.9/4.10）· a11y −1 ✅。
**原"唯一未完：D5 1000 题完整测试"已于 2026-10-07 终局**——凭据管道打通（401→本机
qwen3.8:27b 路线）后 smoke-200 解剖出**三层结构性恒红**（§4.15），用户拍板**选项 D：
直接删除测试**（`08185c3da` 整删 D5 workflow + `fa66f4f66` smoke 摘判红留探针 + 悬挂
引用清理 `fe8e92076`/`c4b7fc12b`，全部复检见 §4.15 尾注）。**至此收尾计划全项闭环**，
仅余 L-8（trivy 漏洞修复，安全债待立项）与 L-9/pre-commit 两项低优先留档
**→ 2026-10-07 深夜用户拍板"三项逐项做"，现已全部执行**：L-9 ✅（`4ca93a76c`，反向验证
含既存坏构建现形）、L-8 🔶（`a091b9869` OS 层 146→0、db/web 转绿；68 条 pip 残留分三组
待拍板）、pre-commit ✅（`6ca417c95`+`10a1172d8`，含 wrapper 无传播/token-orphan 静默失效
两个连带发现，登记 L-12/L-13）。明细见 §4.4 各行与 §4.11 ③。
OpenRouter secrets 已配（余额 0）留档备用。
另有两件潜伏项——2026-10-07 晚已双双闭环（Dockerfile 固定输入通道 + 重复键
合并，证据见 §4.11 更新注记）；新登记 L-8（trivy 门禁连红 5 周=真漏洞）/ L-9
（image-scan 构建失败时静默跳扫描）待立项，及 pre-commit advisory 一项留档。

**→ 2026-10-08 用户拍板 L-8 三组「(i) 做/(ii) 缓/(iii) 不做」并逐项执行**：
L-8 组 (i) ✅（`f9e7defff` 6 镜像 setuptools→84.0.0，run 37790111506 实测
6/6 `Build image` success + code scanning setuptools alert=0；门禁仍红在OS 层
新披露 CVE + DS-0002，均与本次无关，定性留档，详见 §4.16）、
**L-12 ✅**（token-orphan 假绿门禁两文件同批闭环：内建化 3m37.5s→0.498s +
超时 fail-loud `exit 1` 阻塞，详见 §4.4 该行）。

**→ 2026-10-09 又闭环两项**（均为真 CI 验证，无一项靠自报）：

**§4.5 墙钟源 ✅**（`ff9ef524b` 源码 + `93daa7344` dist）—— 勘察发现**实为四处**
（漏 `useRAGEval.js`）且 `MobileDashboard` 走 dayjs 而非 `new Date()`、
`MobileProjectStatsView` 并非消费点。新增 `useNow` 单一入口（可选参数注入，照
`timeDivider.ts` 惯例，**墙钟缺省以保libfaketime 正交性**），四处收敛 +
顺修一处真实 bug（greeting/日期 latch 在首屏，跨小时不更新）。
**真 CI run `37810087503` 视觉回归全绿** ⇒ 像素零变化。详见 §4.5。

**visual regression 门禁自身失效 ✅**（`b7ea584ee`）—— §4.5 验证时 run
`37808071926` 结论 `cancelled`。**根因被复检官证伪修正**：不是 runner 竞争，
是 `timeout-minutes: 25` 撞线（两跑精确贴 25m 被砍；同 run 并发的 a11y 全成功
是反证）。四项修复：timeout 25→40、`push` 加 11 条 paths 过滤（消灭 74% 无谓
触发）、`concurrency` 闸门、改写两处"预期 job 是 failure"的过期注释。
**真 CI run `37814992814`**：双 job success（证明 paths 未堵死 dispatch）+
**concurrency 互斥实证**（6 秒窗口内新旧 run 互斥）。详见 §4.17。

**L-8 组 (ii) ✅**（`7db39f2b1`，2026-10-09）—— 三个 pin 升级落地，
**真 CI run `37880041033` `Build & push app-test image to GHCR` = success**
⇒ 依赖在真镜像构建里装成功。⚠️ **原记"5 pin=43 条"的前提经实测证伪**，
真实是 3 个 `==` pin 命中（"43"对不上是因 trivy 8 镜像 matrix 跨镜像重复上报）。
关键证据：python-jose **新旧版 token 逐字节相同**（滚动部署/回滚均无风险）；
python-multipart 升级是**修既存违规**（starlette/fastapi 都要求 `>=0.0.18`，
而容器装着 0.0.6）；urllib3 加下限实测全量解析 exit 0。第二批 ecdsa/nltk/langsmith
**三个全不做**（前两个已是 PyPI 最新版 = 空操作，langsmith 会引发 websockets 栈级冲突）。
详见 §4.18。

阶段内**再无开着工的工程项**；余 L-13（观察项）+ OS 层周期债 / DS-0002（留档）+
**3 个同型 workflow 的 paths/concurrency 病灶**
（`qa-bench-smoke` / `rag-framework-ci` / `secret-scan`，本轮未动，建议推广）。

### 本轮新登记两笔待立项（本轮未动）

| # | 内容 | 为什么重要 |
|---|---|---|
| **L-14** | **`tests/test_auth.py` 8 用例全 ERROR** —— DB 建连阶段就挂（`InvalidPasswordError`），**根本没跑到 jose 代码** | **JWT 回归测试失能**，与 L-12 同性质：门禁在，但不知道它跑没跑 |
| **L-15** | **同文件并行编辑纪律缺失** —— 本轮 3 个 agent 并行改 `requirements.txt`，agent B/C 均报告"文件被并发修改"，所幸三处落在不同区段（第 4/83/90 行）才没互相覆盖 | 若两agent 改同一行，后写的**静默覆盖**先写的且无人察觉 |

### 4.15 D5 结构性恒红的完整解剖（2026-10-07 本地 qwen3.8:27b smoke-200 交付，复检官逐条复验）

**起因**：本机 ollama `qwen3.8:27b`（tools 能力实测可用，105-150 tok/s / RTX 5090）跑通
smoke 200（真 LLM 应答+工具调用、ERROR=0、repo 零写入），0.0% 通过。按复检官改道指令做了
三分解后，**结论：D5 的 80% 门禁是"恒红门禁"的第 5 型实例——三层结构性阻断，任何模型、
任何资金、任何环境都到不了 80%**：

1. **口径层（决定性）**：D5 实际题库（`questions_780` + `d4_extra_300`）**985/1000 的
   `expect.intent` 是过时大写 6 值**（复检官按 `expect` 路径独立重数：685+300 大写、
   0 小写、15 无 intent；生成器 `gen780.py:91` 自带旧 `INTENT_TYPES`）。分类器现行输出
   小写 8 类枚举，`runner.py:438` 精确 `==` 区分大小写 → **结构性永远 mismatch**。
   关键机制：`intent_mismatch` **不在 critical 元组**（`runner.py:946-957`，复检官逐字核）
   → 只产 WARN 不 FAIL，但 **PASS 要求零 issue** → **985 题永远不可能 PASS** →
   该门禁今日上限 = 15/1000 = **1.5%**，与模型无关。（我方早期"全库约一半过时"的数字
   是跨全部 questions*.jsonl 的——小写期望都在 D5 不加载的文件里，D5 切片实为 98.5% 过时。）
   **（2026-10-07 晚补实测，L-10 范围内）**：① 题库**至少叠了三个出题规范时代**——
   GUIDE 手工题 `intent: "list_tasks"`（工具名当意图）→ 生成器大写 6 值（现存 985）→
   分类器小写 8 类，从未统一；② **500/1000（50%）题面是未替换的占位符**
   （`[占位] A 类 L1 题 #1 (W2 由 gen_base.py 替换)` 原文即题面；P/K 类 200 全真 +
   extra 300 全真 = 500 真题），且 CI `Generate 1000 题题库` 步 success 却**并未替换**——
   占位原文在 D5 真跑日志出现（`[401/1000] ... [占位] C 类 L3 题 #201`）。
   ⇒ L-10 迁移时须一并处置：占位 500 题是补生成、删减还是改判"不计分"，与口径映射同批拍板。
2. **时长层（本地特有）**：ollama 单 slot 串行 → 题均 78.7s、>60s 占 108/200 →
   `duration_too_long` 在 critical 元组内 → **86/119 FAIL 是纯时长杀**（72%）。
3. **真质量层**：排除口径+时长后仍剩 **33/200 真 critical**（hallucinated_names 17 /
   missing_tools 13 / fake_xml_leaked 3）+ WARN 残渣（filler 16 / tool_error_with_excuse 14 /
   missing_required_tools 20 / forbidden_names 数据 bug 9 等）。

**反事实（离线复算，复检官独立验算 86/33/分布逐项吻合）**：
- 口径对齐 alone：0.0% → **1.0%**（WARN 仍卡 PASS）
- 口径对齐 + 去 `duration_too_long`（保留 duration_warn）：**97/200 = 48.5%**（agent 口径；
  其"整体移除"标签不精确——真正两种 duration 全不计为 **132/200 = 66%**，两者均 <80%）
- 历史佐证：7 月 mimo/cloud 亦 77% mismatch、pass 5/35，**80% 从未被任何模型摸到**

**历史定性**：与 §3.7 四假门禁同族——恒绿/恒红是同一枚硬币两面；本门禁脚本层的恒红
（heredoc 崩溃）已于 §4.10 修掉，但**数据层+阈值层的恒红**今日才解剖出来。

**原待拍板 A/B/C → 2026-10-07 用户拍板选项 D：直接删除测试**（"之前已经测试过很多次
1000题了，我感觉目前来说无用"）。已执行并复检：
- **D5 workflow 整删**（`08185c3da`，恰 1 文件 620 行删除）+ 悬挂引用清理（`fe8e92076`，
  5 文件纯注释）+ smoke 内 7 处过时注释收尾（`c4b7fc12b`，复检官亲修）——原始 API 实证
  workflow 列表 12→11、`318399493 state=deleted`、**每周六 02:30 cron 一并退役**；
  D7 独立 workflow 实跑 success（run 37581989734）；两个删除 push 的 Playwright/Secret/RAG
  全绿；分支本无保护无必需检查。
- **smoke 同型门禁按用户选项 1 摘判红、保留探针**（`fa66f4f66`）：判红步替换为恒 exit 0
  的报数步（保留 `Smoke 通过率` 打印 + 退役注明），runner/fvD/上传全保留；**首转绿**
  run 37581862664（job success、runner×2 + fvD success、零非预期红步）。
- **范围边界**：题库 `questions_*.jsonl`、runner.py、历史 results 归档、D7、`endpoint_lock`
  契约全部保留（smoke 与归档仍依赖）；测试数据未删——删的是"测试运行与判红"。
- 本地环境产物：`%TEMP%/qa-bench-local/`（repo 零写入），栈已清理、生产容器全程只读。

---

## 4.16 L-8 组 (i) 落地并经真 CI 验证（2026-10-08）

**三组拍板**：用户 2026-10-08 拍「(i) 做 / (ii) 缓（单独立项 PoC）/ (iii) 不做（留档）」，
并拍「**6 镜像全升**（非计划原文的 4 镜像）+ **requirements.txt 不动**」。

### 为什么是 6 镜像而不是计划记的 4 镜像

勘察（`image-scan.yml` matrix 实为 8 项）发现含 Python/pip 的镜像共 **6 个**：
`app` / `funasr` / `mcp` / `voice-pipeline` / `whisper` / `commercial`。
`db`(postgres-alpine) / `web`(node+nginx) 无 Python，**结构上不可能有 setuptools CVE**。
「8 条命中 4 镜像」与「6 镜像统一升」不冲突——setuptools 是 base image 通病，
统一升可避免下轮修补时在未命中的镜像上复现。**方案 B（换 base）经勘察全部不适用**：
app/funasr/whisper/commercial 已 pin `python:3.11.17-slim[-bookworm]`（`a091b9869` 刚bump），
voice-pipeline 因 CUDA 底座锁死必须保留 `nvidia/cuda:12.1.1-runtime-ubuntu22.04`。

### 落地（`f9e7defff`，6 文件净 +6 行）

每文件**净 +1 行**，插在 `pip install --upgrade pip` 之后、依赖安装之前（防被旧 setuptools
wheel 覆盖回退）。**两个必须记录的实现事实**：

1. **双重 `&&` 语法陷阱**：brief 字面给的 `&& pip install ... setuptools \` 与上一行末尾
   `&& \` 拼接后成为 `cmd1 && && cmd2`，bash 直接 syntax error（agent 首次尝试踩中，
   主动还原并上报，未留脏改动）。whisper/funasr 最终走「不带前导 `&&`、自带后继分隔符」
   的等价写法，`bash -n` + `sh -n` 双解析预检 PASS。
2. **commercial multi-stage**：`--upgrade setuptools` 只进 **builder 阶段**，
   runtime 阶段不带 pip，**碰了必构建失败**。

`requirements.txt` 零改动（setuptools 是构建期工具，进应用依赖图反而让测试装包时也拉一次）。

### 真CI 验证：run 37790111506（全量 8 镜像 dispatch）

| job | 结论 | Build image | trivy 门禁 |
|---|---|---|---|
| db / web | success | — | — |
| app / mcp / funasr / whisper / voice-pipeline / commercial | failure | **success** | failure |

**6 个失败 job 的 `Build image` 全部 success** —— 改法 100% 正确，pip 链跑通，
无一例语法或构建错误。CI 日志直接物证（mcp job）：

```
setuptools 79.0.1 → 84.0.0   Successfully installed setuptools-84.0.0
```

code scanning 中 setuptools 相关 alert = **0**。**组 (i) 的 8 条已清零，工程项闭环。**

### 门禁仍红，但红在两类与本次无关的债（定性留档，不在本轮动）

1. **OS 层 bookworm 新披露 CVE**（trivy DB 在 10-07 那次 base 升级后 24h 内更新）：
   `CVE-2026-78410/78409/78408`（util-linux / mount / login / libuuid1 / libsmartcols1）、
   `CVE-2026-76642`（perl-base）、`CVE-2026-9538`（ncurses-bin）。
   与 `a091b9869` 同性质的**周期债**，归下一个 base 镜像窗口。
2. **DS-0002（HIGH）** `Specify at least 1 USER command in Dockerfile with non-root user`：
   mcp job 的门禁计数是 `Failures: 1 (HIGH: 1, CRITICAL: 0)` —— 即 mcp 镜像
   **已无真实可利用漏洞**，纯 Dockerfile 配置告警。改 `USER` 需评估
   volume 挂载（app）与 CUDA 设备访问（voice-pipeline）兼容性，**本轮不动，留档**。

**三条失败原因中，没有一条是「setuptools 漏洞仍在」。**

### 一条附带确认

`image-scan.yml` 触发条件是 `pull_request` / `schedule` / `workflow_dispatch`，**不含 push**，
所以推 main 不会自动扫，需手动 `gh workflow run image-scan.yml --ref main`。

---

## 4.17 visual regression 门禁自身失效（cancelled）—— 根因与四项修复（2026-10-08/09）

> **✅ 2026-10-09 闭环**。commit `b7ea584ee`，真 CI run `37814992814` 验证：
> 双 job success + **concurrency 互斥实证**。

### 事故链：为验证 §4.5 触发的 run 结论 `cancelled`

为验证 §4.5 墙钟收敛是否改变像素输出，dispatch 了 `image-scan` 之外的
`playwright.yml`，run `37808071926` 结论 **`cancelled`** —— 视觉断言根本没跑完，
**验证作废**（§4.5 本身后来由 push run `37810087503` 证明无像素变化）。

被取消 job 的步骤明细（关键证据）：
```
Set up job / Build pinned image / Install dependencies / Start test environment
Init test DB schema+seed / Get fresh TEST_TOKEN        → 全部 success
Run visual regression tests→ cancelled   ← 唯一被取消步
Upload visual diff on failure            → skipped
```
若真是像素不一致，该步会 **failed** 并触发后面的 diff 上传，而它是 `skipped`。

### ⚠️ 初判被证伪：根因不是 runner 竞争，是 `timeout-minutes: 25` 撞线

**当时的初判**（错）：看到 run 列表里三个 playwright run 时间重叠，
且本 run 被取消 ⇒ 归因"并发抢 runner"。

**证伪证据**（复检官拿 job 时间戳 + 配置推翻）：

| run | visual job 耗时 | a11y job |
|---|---|---|
| `37808071926`（本次） | **25m23s** | 8m37s **success** |
| `37808055507`（同期 push） | **25m19s** | 9m29s **success** |

1. 两个独立 run 的 visual job **在同一秒被砍，耗时精确贴 `timeout-minutes: 25`**
   （`playwright.yml:359`）
2. **同 run 内并发跑的 a11y job 全部成功** —— 若是 runner 饥饿/抢占，a11y 会先饿死。
   **这是决定性反证**
3. 成功 run 的 visual job 常态耗时 6 例实测：22m44s / 23m55s / 22m05s / 23m05s /
   23m10s / 22m54s ⇒ **基线 ~23min，预算 25min，余量恒定 1–3 分钟**

⇒ **并发只是把已贴边的耗时推过界**（npm ci / docker pull ghcr / 每次 `docker build`
钉镜像三件事同时打网络），**是压死骆驼的最后一根稻草，不是病根**。

> **方法论沉淀**：这是本阶段第二次"看到相关性就下结论"。同型错误已犯两次：
> ① 本次把 timeout 撞线误判为 runner 竞争；② 用 `gh api --jq .headSha` 取到空值
> （**正确键是 `head_sha`，snake_case**）导致差点误判"run 与我无关"而漏掉验证结论。
> **判据**：归因任何 CI 失败前，必须先拉 **job 时间戳**与 **workflow 配置**，
> 不能只看 run 列表的时间重叠。

### 四项改动（用户拍板 A1 + B1 + C1）

| # | 改动 | 内容 |
|---|---|---|
| **1** | P0-a timeout | visual job `25 → 40` 分钟（a11y 的 30 未动） |
| **2** | P0-b paths | `push` 加 11 条 paths 过滤 |
| **3** | P1 concurrency | `playwright-${{ github.ref }}` + `cancel-in-progress: true` |
| **4** | B1 注释 | 改写两处"预期本 job 是 failure"的过期断言 |

#### 改动 2 的 11 条 paths（两轮独立验证，正查漏项 + 反向确认排除项）

| 路径 | 依据 |
|---|---|
| `web/src/**` | 两 job 的 vite dev server 出图源 |
| `web/tests/**` | 测试用例 + **49 张视觉基线 PNG 都在这里** |
| `web/scripts/**` | `vite.config.js:11` import `build-id.mjs`，**dev server 启动即 require** |
| `web/public/**` | **KaTeX 字体 20 个 .woff2** + `katex.min.css`，字体不在 `src` 下 |
| `web/index.html` | `lang="zh-CN"` **直接影响 axe `html-has-lang` 规则**与字体回退 |
| `web/vite.config.js` `package.json` `package-lock.json` | vite 配置 + `npm ci` + cache key |
| `docker/visual-regression/**` | 实测 4 文件，Dockerfile 是 build context 根 |
| `docker-compose.test.yml` | 两 job 起栈 + 建号 + teardown |
| `.github/workflows/playwright.yml` | 自身 —— **必须含**，否则改门禁的提交被自己的过滤误杀 |

**独立佐证**：`web/scripts/build-id.mjs:42-51` 自己枚举了前端构建输入的权威清单，
与上述 web 路径**逐条对上** —— 这是项目自己的代码给出的答案，不是推测。

**两个刻意排除（各留注释，防后人误加回去）**：
- **`web/dist/**`** —— 两 job 都起 `npx vite` **dev server**（行 109 / 487，
  **全仓无 `vite preview`**），从 src 出图；`build-id.mjs:82` 明写"不碰 dist"。
  dist 重建是 4/19 无谓触发源之一
- **`scripts/init_db.py` / `scripts/ensure_test_user.py`** ——
  `docker-compose.test.yml:128-131` **只挂 `./app` `./alembic/versions`
  `./models/hf_cache`，未挂 `./scripts`**，它们烘在 app-test 镜像里，改仓库不生效。
  留着会造成"我改了脚本所以门禁会验证"的**错觉，与 L-12 假绿同型**

**为什么 paths 过滤不能写漏**：写漏 = 视觉门禁变成"永不触发的门禁"，而它
**表面照样显示绿**。这与 L-12（超时被吞、永远报 0 orphan、18 天）和 §3.8
（visual 是"从未运行过的门禁"）是同一种病 —— 故本次清单经两轮独立验证才落。

#### 改动 4顺带修掉一颗"下一个 L-12 的种子"

`playwright.yml` 两处注释仍写着「**预期本 job 是 failure**，原因是缺基线」
+「这 5 个 spec 的 -snapshots/ 基线在 git 里全都不存在」。这已被 `fcc0c74b0`
（2026-10-05）推翻 —— 49 张基线 PNG **现已入库并被 git 跟踪**，
visual job 现在是**真在拿入库基线做像素比对并通过**。

留着该注释，下一个人看到红会**以为红是常态**，照此判断即 L-12 的重演。

**并追出一处数字差异**：commit message 写"50 张"、实测现存 49 张，
系 `043d48d12`（修 vite 504 空白页时重录）删掉 1 张旧基线，属正常重录非丢文件 ——
注释按"入库 50 → 现存 49"写全，**免得后人拿 message 对不上数以为基线丢了**。

### 真 CI 验证（run `37814992814`）

| 验证点 | 结果 |
|---|---|
| (a) paths 没堵死 dispatch | ✅ **两个 job 都 success、无 skipped** —— 手动验证能力完好 |
| (b) visual 跑时 | **23分03秒**（17:15:47→17:38:50） |
| (c) concurrency 互斥 | ✅ **抓到实证**（见下） |
| (d) job 结论 | ✅ 双 success |

**concurrency 的实证**（比预想更有说服力）：run列表暴露一个 6 秒窗口内的竞争
```
37814979195  push               cancelled  17:14:10
37814992814  workflow_dispatch  success    17:14:16
```
`cancel-in-progress: true` **正确工作** —— 同属 `playwright-refs/heads/main` 组，
新 run 取消旧 run，任一时刻只有一个在飞。且被取消那个 run 只改了 `playwright.yml`
一个文件 ⇒ **恰好验证了"改门禁自身的提交不能被自己的过滤杀掉"这条设计**：
它在 11 条清单里，触发是对的。

**关于 (b) 的诚实表述**：23m03s **低于**旧预算 25min，所以**本次不构成
"timeout 救场"的直接实证** —— 只能说改动落地后跑一次没撞线、40min 给了余量。
撞线的真证据仍在事故那次（25m23s / 25m19s 两跑精确贴 25min 被砍）。
40min 把这类 flake 从"验证作废"变成"正常完成"。

### 已知边界（用户拍板 A1：不加 `app/**`）

`docker-compose.test.yml:129` 有 `./app:/app/app`，app-test 容器把仓库 `app/`
盖在镜像上；seed 走 `app/seed/member_seeder.py` 的 `DEFAULT_MEMBERS`
（`init_db.py:53/67`），**spec 截的就是这批后端产生的数据** ⇒ 改后端 API 字段或
seed 数据，视觉输出会变而本门禁不触发。

**这是既有状态不是本次引入** —— `pull_request` 侧本来就只有 `web/**` 过滤。
用户拍板 A1：不加 `app/**`（加则 74% 降幅基本消失，paths 过滤失去意义），
**改为把边界显式化**（commit message 与 §4.17 均写明"视觉门禁守前端渲染层，
后端变更靠 PR 侧现有 paths + 其他门禁兜底"）。沉默地不写才是下一个 L-12。

### 附带查明：main 无分支保护

`gh api .../branches/main/protection` → **404 Branch not protected**。
`main` 无 required status checks ⇒ **push 到 main 的视觉红不挡合并、不挡部署**，
约束力只来自 PR 侧。无任何 workflow 用 `needs:` / `workflow_run` 引用 playwright，
`scripts/*.sh`（含 `deploy-auto.sh`）grep `playwright|visual` 零命中。

⇒ **这道门的真实收益是省算力 + 降重叠频率**，不是"打开一道门"。这也降低了
paths 过滤写漏的风险敞口（但不可作为放过的理由）。

### 波及面（**本轮未动，留档**）

11 个 workflow 中 **10 个没有 `concurrency:`**，其中 **4 个存在与本次同型的
"push到 main 无 paths 过滤"病灶**：
`qa-bench-smoke.yml` / `rag-framework-ci.yml` / `secret-scan.yml` / （playwright 已修）。
`build-image.yml` 虽已过滤，但 docker build 与 playwright 的 `docker pull` 同源抢网络，
其注释自述"近 3 个月 8 次 push 全 cancelled/failed"，值得单独查。

⇒ 建议待本次改动验证稳定后，按同一范式推广。

---

## 4.18 L-8 组 (ii)：三个 pin 升级落地并经真构建验证（2026-10-09）

> **✅ 2026-10-09 闭环**。commit `7db39f2b1`，**真CI run `37880041033`
> `Build & push app-test image to GHCR` = success** ⇒ 依赖在真镜像构建里装成功。

### ⚠️ 首要发现：原登记的"5 pin = 43 条"前提是错的

组 (ii) 自 10-07登记以来一直写「requirements 5 个 pin = 43 条」，**从未核实过**。
本次勘察（`gh api code-scanning` 全量拉取 + 按 `(包,CVE)` 去重）**证伪**：

| 项 | 原记 | 实测 |
|---|---|---|
| pin 数 | 5 个 | **3 个 `==` pin 命中**（requirements.txt 共 22 个 `==` pin） |
| 漏洞条数 | 43 条 | 数字对不上 —— 口径不同 |

**"43"对不上的机制**：trivy 的 8 镜像 matrix 会把同一 CVE **跨镜像重复上报**
（原始 9714 条 → 按 `(包,CVE)` 去重后 5688 条）。"43 条"应是某次**单镜像**的
per-instance 计数，与全量口径不是一回事。

命中高危的三个包（`python-dotenv` 命中但仅 MEDIUM，不算）：

| 包 | 当前 pin | 类型 | trivy 建议修复版 | 收益 |
|---|---|---|---|---|
| `python-jose[cryptography]` | `==3.3.0` | pin | **3.4.0** | 2 CRITICAL + 1 |
| `python-multipart` | `==0.0.6` | pin | **0.0.30** | 5 HIGH |
| `urllib3` | **不在文件里** | 传递依赖 | **>=2.8.0**（新增约束） | 2 HIGH |

> **与组 (i) 同型的教训**："4 镜像 8 条"实测是 6 镜像（见 §4.16）、"5 pin 43 条"
> 实测是 3 pin。**这两处数字都是从 run 总结里转述来的，没人核过。**
> 凡是要据此做决策的数字，必须重新拉一手数据。

### 落地（`7db39f2b1`，requirements.txt 3 行）

| 包 | 改动 | 性质 |
|---|---|---|
| `python-jose[cryptography]` | `==3.3.0` → `==3.4.0` | 改 1 行 |
| `python-multipart` | `==0.0.6` → `==0.0.30` | 改 1 行 |
| `urllib3` | **新增 `urllib3>=2.8.0`** | 加 1 行（非改版本号） |

### 三个 PoC 的验证证据（复检官独立复验，非采信agent 自报）

**① python-jose 3.3.0 → 3.4.0：token 逐字节相同**
- 使用面复核：agent报"4 个文件"，**实测 `app/` 下只有 `app/core/security.py` 一个**
  （另 3 个是 tests/ 里匹配到 "jwt" 字样但非 jose）—— agent 如实纠正了派工brief 的错
- 4 处调用全是稳定 API：`jwt.encode`（:57/:74）、`jwt.decode`（:92）、`except JWTError`（:94），
  **无边缘 API**（未用 jose.jws/jwe/具体异常类）
- **决定性证据**：复检官独立建 venv 装 3.4.0，与容器里 3.3.0 对打 ——
  同一 payload+key 下两版产出token **字符串逐字符完全相同**
  （`eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...bL8_wkYkdzTM89oFcPBL9eDjB-c9musiOB4VjzU8gbs`），
  且 3.3.0 能成功解码 3.4.0 的 token
- ⇒ **向后完全兼容，滚动部署（老 token 不失效）与回滚均无风险**

**② python-multipart 0.0.6 → 0.0.30：这是"修错"不是"引入风险"**
- **关键发现（容器实查）**：starlette 1.6.0 与 fastapi 0.141.1 的 metadata 都声明
  `python-multipart>=0.0.18`，**而容器实际装的是 0.0.6 —— 本就违反下限**
- ⇒ 升级到 0.0.30 是**让依赖树合规**，不是引入风险
- 兼容性实测：
  - 0.0.30 wheel **同时提供新旧两套命名空间** `python_multipart/` 与 `multipart/`
    （0.0.6 只有旧名，靠 starlette fallback）
  - `parse_options_header` 返回值格式**逐字节不变**：
    `(b'form-data', {b'name': b'a', b'filename': b'b.txt'})`
  - starlette form parser 实测：字段值 + UTF-8 中文文件名 + 文件 1000 字节全部正确解析
- 使用面：`app/` 下**直名 `multipart` 零引用**，全经 fastapi的 `UploadFile`/`Form`/`File`
  间接使用（11 个路由文件），**无一处直调 multipart API**

**③ urllib3 >=2.8.0：全量解析实测无冲突**
- agent **纠正了派工 brief 的错误猜测**：urllib3 **不来自 httpx**
  （httpx 走 httpcore → h11，与 urllib3 无关）。真实来源是
  `requests`（langchain 链拉入）+ `minio` + `modelscope`
- **冲突检查（传递依赖加下限最易出事的地方）**：
  | 上游 | 对 urllib3 的约束 | 兼容 >=2.8.0？ |
  |---|---|---|
  | `requests`（解析为 2.34.2） | `<3,>=1.26` | ✅（老版 requests 2.25.1 的 `<1.27` 才是真冲突点） |
  | `minio` 7.2.0 | 裸 `urllib3`（无上限） | ✅ |
  | `modelscope` | `>=1.26` | ✅ |
- 全量解析实测：`pip install --dry-run --ignore-installed -r requirements.txt` → **exit 0**，
  解出 `urllib3-2.8.0`
- 应用零引用（`grep -rn "import urllib3\|from urllib3" app/` = 0）

### 第二批候选（ecdsa / nltk / langsmith）：**三个全不做**

| 包 | trivy | 判定 | 硬证据 |
|---|---|---|---|
| `ecdsa` | 1 HIGH (CVE-2024-23342) | **不做** | trivy **未提供 Fixed Version**（上游无修复版）；且 **0.19.2 已是 PyPI 最新版**（复检官独立核实）——**加约束是空操作** |
| `nltk` | 1 HIGH (CVE-2026-81726) | **不做** | 同上，**3.10.3 已是 PyPI 最新版**（独立核实） |
| `langsmith` | 1 HIGH (GHSA-f4xh-w4cj-qxq8) | **不碰** | 有 Fixed Version 0.8.18，但**实测解析直接失败** |

**langsmith 的冲突链条被完整拆解**：
```
langsmith >=0.8.18  要求  websockets >=15.0
      ✗ 冲突
requirements.txt:5 硬钉   websockets==12.0
      ↑ 而 uvicorn[standard] 0.24.0 要求 websockets>=10.4（12.0 满足）
```
要修必须把 websockets 从 12 → ≥15 并连带升 uvicorn/fastapi 栈——
**这不是"加一行下限"能解决的，是栈级改造**，明确超出 PoC 范围。

### 一个附带发现：容器版本比 requirements.txt 解析结果旧得多

| 包 | 容器实际装 | requirements.txt 全量解析出 |
|---|---|---|
| `langsmith` | **0.8.5** | 0.14.4 |
| `python-multipart` | 0.0.6 | 0.0.30 |
| `urllib3` | 2.7.0 | 2.8.0 |

⇒ **容器构建时另有约束/缓存层在钉版本**，改 requirements.txt **不保证容器真会升**。
这正是"必须跑一次真构建才算验证"的原因 —— 而真构建（`37880041033`）已通过。

### 顺带发现两笔待记账项（**本轮未动**）

1. **`tests/test_auth.py` 8 个用例全 ERROR** —— 根因
   `InvalidPasswordError: password authentication failed for user "postgres"`，
   **测试在 DB 建连阶段就挂了，根本没跑到 jose 代码**。
   ⇒ **JWT 回归测试目前是失能的**，与 L-12（超时被吞、永远报 0 orphan）**同性质**：
   门禁在，但你不知道它跑没跑。**建议单独立项**
2. **三个 agent 并行改同一文件**（`requirements.txt`）—— agent B / C 都报告了
   "文件被并发修改"，实际是彼此。**所幸三处落在不同区段**（第 4 / 83 / 90 行）
   才没互相覆盖。
   ⇒ **纪律：同文件并行编辑应串行化，或让每个 agent 改不同文件。**
   若两个 agent 改同一行，后写的会静默覆盖先写的且无人察觉

### 一条环境备注（非缺陷）

复检官本机 `pip install -r requirements.txt` 首次报 `UnicodeDecodeError: 'gbk' codec`——
**是 Windows 默认 GBK 读 UTF-8 文件所致，与依赖无关**（文件本身 UTF-8 无 BOM 正常，
容器是 Linux UTF-8 locale，既有中文注释早已存在且 CI 从未出问题）。
加 `PYTHONUTF8=1` 即可。**不做改动**：既有 3 条中文注释已存在很久，
为这个改是过度反应。

---

## 六、与主文档的关系

- **主文档** [`2026-09-30-phase-closeout-plan.md`](2026-09-30-phase-closeout-plan.md)
  记录**阶段内做了什么**（S3.0–S3.8 + 执行记录 21 轮）。
- **本文档** 记录**还欠着什么、为什么欠、怎么还**，是收尾阶段的唯一入口。
- 两份文档若有冲突，**以本文档的实测复核结果为准**——
  本文所有数字都在 2026-10-02 由复检官独立复测，非转述。

---

**复检官签署**：本文档第 3.1（296 条 / 41 文件 / 文件分布）、3.2（unauthorized 原文 /
compose 实况）、3.3（`anthropic` 缺依赖 / requirements:23 已声明 / workflow 出现 0 次）、
3.5（`vite.config.js:45` / 三次 build 对照表 / 确定性 diff=0）均为**本机实测**，
非引用他人结论。写于 2026-10-02。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>