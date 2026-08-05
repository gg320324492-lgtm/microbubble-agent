# W2 +N /meetings 滚轮修复 (类 20.155, 2026-08-05)

## 事故

用户报告"https://agent.mnb-lab.cn/meetings 不能滚动"。截图显示页面有 5-6 个会议卡片但鼠标滚轮无反应。

## 排查链 (3 次部署, 3 个根因)

### 第 1 次尝试 (类 20.153/154): 只改 .meeting-list

- 修复: `.meeting-list { min-height: 0; max-height: 100%; flex: 1; overflow-y: auto; }`
- commit: `332d7d91e`
- 验证: 用户报"还是不能滚动"
- 根因: 父级 `.meeting-list-card` 撑到 3302px (受 .meeting-list 内容撑大, 反向影响 .meeting-list)

### 第 2 次尝试 (类 20.154): 三层 min-height:0

- 修复: `.meeting-list-card { min-height: 0 }` + `.el-card__body { min-height: 0 }`
- commit: `c5d873a30` (源码) + `43659ff8e` (dist)
- 验证: 用户报"还是不能滚动", playwright 实测 `.meeting-list-card ch=3302` 仍撑满
- 根因: **真正的根因不在 .meeting-list-card, 而在更上层的 `.tab-panel` 不是 flex 容器**

### 第 3 次尝试 (类 20.155): 真正的根因 — `.tab-panel` display:block

- playwright inspect DOM 发现:
  - `.meeting-view` (display:flex, flex-direction:column) ✅
    - `.tab-strip-wrapper` (ch=50) ✅
    - `.tab-panel` (display: BLOCK, ch=3434) ❌ **不是 flex 容器!**
      - `.filter-card` (ch=128)
      - `.meeting-list-card` (flex:1 1 0%, ch=3302 撑满) ❌ **flex:1 在 block 容器中失效**
- 修复: `.tab-panel` 加 `display: flex; flex-direction: column; flex: 1; min-height: 0; overflow: hidden;`
- commit: `4d76b6f3e` (源码) + `b2dd0a3d6` (dist)
- 验证: ✅ `.meeting-list-card ch=482` + `.meeting-list ch=369, sh=3189, overflow-y:auto` + 滚轮 scrollTop 0→300

## 永久铁律 (类 20.155)

**Flexbox 子项的 `flex: 1` 必须有 flex 容器祖先, 否则 `flex` 失效, 子项按内容撑大。**

排查滚轮失效时, 必须从下到上检查每个祖先是否真的是 `display: flex`:
1. `.meeting-list` 有 overflow-y:auto → 看似正确
2. `.meeting-list-card` 有 flex:1 + overflow:hidden → 看似正确
3. **`.tab-panel` 是 display: BLOCK, 不是 flex 容器** ← 真正根因
4. `.meeting-view` 是 display: flex → 正确

CSS 不会报错, 但 `flex: 1` 在 block 容器中**静默失效**。

## 教训

- **不要只看 "overflow-y: auto" + "height: 100%" 表面是否正确**, 必须验证**每个祖先的 `display`** 是否正确
- **playwright inspect DOM tree** 是定位此类 CSS 失效的**唯一可靠方法** — 不能凭经验猜
- 同样的 bug 模式可能存在于其他 view (TaskView / KnowledgeView 等) — 需要逐一 audit
- 部署链教训: 服务器 dist 不会自动 rebuild, 必须本地 build + force-add + commit + push + 服务器 git pull (webhook 偶尔漏拉, 手动 pull 是兜底)

## 5 件套守恒

1. alembic 1 head `097_meeting_processing_persistence` 守恒 ✅
2. pytest: 本任务不动后端, 沿用 W2 +N 基线 ✅
3. PWA build PASS (postbuild 自动) ✅
4. 0 production code: 仅 web/src/views/meeting/meeting-view.css 改 12 行 (3 次叠加) ✅
5. 锚点范式: 3 commits (c5d873a30 + 43659ff8e + 4d76b6f3e + b2dd0a3d6) 据实累计, 无漂移 ✅
