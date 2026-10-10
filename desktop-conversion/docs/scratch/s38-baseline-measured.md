# S3.8 勘察 — 已实测基线（主指挥侧 + 2026-10-02 二次订正）

⚠️ **本文件第 3 节的旧结论已被本轮勘察推翻，见下方「订正」段。**

## 0. 文件位置
`web/src/utils/paperAdapter.js` 在**父仓** `/e/microbubble-agent/web/`，**不在** `desktop-conversion/` 下。

## 1. 测试基线
```
cd /e/microbubble-agent/web && npx vitest --run src/utils/__tests__/paperAdapter.test.js
→ Test Files 1 passed (1) / Tests 176 passed (176) / exit 0 / 735ms
```
基线可信。勘察 agent 独立复跑两次（15:14:43 / 15:22:55）同样 176 passed / exit 0。

## 2. 行数（wc -l 口径）
`wc -l` = **5633**；python 独立复核 = **5633**；行尾纯 LF（CRLF 0 处）。

## 3. ⚠️ 订正：4,588 是真的，我第一次判它"无法复现"是错的

我最初只跑了 `Measure-Object -Line`（pwsh 7.6.3 默认编码）得 5,205，判定 4,588 复现不出。
**勘察 agent 用 `-Encoding ansi` 精确复现了 4,588。主指挥已独立复核确认：**

| 口径 | 结果 |
|---|---|
| `wc -l` / python | **5633** |
| pwsh 7.6.3 默认（UTF-8） `Measure-Object -Line` | **5205** |
| pwsh 7.6.3 `-Encoding ansi` `.Count` | **5011** |
| pwsh 7.6.3 `-Encoding ansi` `Measure-Object -Line` | **4588** ← 派工单的值 |

**两个成因叠加**：① 该文件无 BOM，`-Encoding ansi` 按 zh-CN→gb2312 解码，非法字节序列让解码器吞掉换行（5633→5011，丢 622）；② `Measure-Object -Line` 按定义跳过空行（5011→4588，再丢 423）。

**教训（本阶段第 N 次"工具骗人"，且是最标准的一次）**：我在 pwsh 7 默认编码下判定"4,588 无法复现"，并据此写进 scratch 让 agent 别用——**我自己也犯了"只试一种口径就下结论"的同款错误**。正确做法是先穷举编码维度再判"不可复现"。
⇒ **4,588 = 5,011 − 423**，不是"来历不明的假数字"。

**纪律**：PowerShell 数行数必须显式 `-Encoding UTF8`（或用 pwsh 7+ 默认），否则无 BOM 中文文件会掉 622 行。

## 4. variables.css 消费者（三个数都对，但口径不同）
```
grep -rl "variables\.css" web/src       → 26   (含 variables.css 自身)
排除 web/src/assets/variables.css 自身   → 25   ← 旧记的"24" = 25 − sw.js(全注释)
顶层(非递归)                             → 2   (main.js, sw.js) ← 旧记的"3" 是目录文件数
```
- `sw.js` 7 处命中**全在注释里**（L64/156/171/178/187/200/215，逐行 strip 后以 `//` 开头）。
- **真 import 只有 1 处**：`web/src/main.js:58 import './assets/variables.css'`。
- 另有 3 处非 import 型真实依赖：`web/.stylelintrc.json:54`、`cssVariables.test.js:52/135`、
  `HypothesisBlock.test.js:49/50`（**我第一轮漏了这个第三处，勘察 agent 补出**）。
⇒ "消费者数"在 1～4 之间浮动，**取决于是否把测试/stylelint 算消费方 + 注释剥离是否做对**。
⇒ 该数字**不能**当"已知答案"用——它本身就是待验证对象。

## 5. 棘轮基线是对的，别动
`.github/workflows/lint-css.yml:174` → `["web/src/utils/paperAdapter.js"]=5633`（正确）。
文档 L169 里那个 5,205 是"旧快照"列的历史值，同行"实测"列已是 5,633，**不需要改**。

## 6. S3.8 export 面
`grep -n "^export"` → 24 处（行号见勘察报告）。

## 7. 勘察 agent 留的两个缺口（主指挥已补验）
- **`normalizeGraphData` 的 `.vue` 侧测试**：`KnowledgeGraphExplorer.vue` **有** mount 测试
  （`KnowledgeEntityTab.test.js` / `KnowledgeGraphLabel.test.js`，会真跑该组件 → 真跑
  `normalizeGraphData`），但 `KnowledgeDetailView.vue` **无测试**。
  ⇒ 勘察报告的 FM1「re-export 漏了 `normalizeGraphData` 抓不到」应修正为
  **部分可抓**（组件测试能抓到 import 崩掉），但抓不到行为变更。
- **`_embedAnchors`(1588) / `_isTocPage`(4692)**：全仓 grep（排除 paperAdapter.js 自身）**零命中**
  ⇒ 是真死码候选，但**删除属生产代码改动**，不在本轮范围。
