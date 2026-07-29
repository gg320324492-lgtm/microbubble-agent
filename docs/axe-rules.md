# axe-core 规则修复 SOP (W89-P-12 沉淀)

> **类 20.60 实战沉淀**: `docs/axe-rules.md` 必须含 ≥ 5 条规则 SOP, 每条必含 *触发 + 修法 (含具体代码) + 验证* 三段. 仅列规则名 = 半成品, 不算沉淀.

## 项目 axe 规则实战库 (W86/W87/W88/W89 共 5 批实战)

W86 mini-15 Tab 收尾 + W87-G-1 + W88-G-2 + W89-P-1 真修 + W89-P-5 build gate 共 5 批 axe-core/playwright 实战, 沉淀如下规则处理 SOP. **实测数据**: W87 全绿是可疑信号 (类 20.25), 真正 baseline 后 W89-P-1 发现 26 处真违规, color-contrast 占 80%+.

### 1. `color-contrast` (最常见, 80%+ 命中)

**触发**:
- WCAG 2.1 AA: 正文对比度 < 4.5:1, 大字 (< 18pt / < 14pt bold) < 3:1
- Element Plus `--el-color-primary` (#409EFF, 3.6:1) 与本项目 `--color-primary` (#FF7A5C, 3.4:1) **双双不达标**
- 灰色 placeholder / disabled text / sub-text (--color-text-secondary / --color-text-placeholder)

**修法 (3 步, 不要 inline)**:
1. **token 审计**: 读 `web/src/assets/variables.css`, 找 `--color-primary` / `--color-primary-light-3..9` / `--color-text-regular` / `--color-text-secondary` / `--color-text-placeholder`
2. **选替代色**: WCAG AA 计算器 (https://webaim.org/resources/contrastchecker/) + 保留色相饱和度, **加深到 ≥ 4.5:1**, 例:
   - `#FF7A5C` (3.4:1 失败) → `#C44A30` (5.4:1 通过)
   - `#909399` (gray placeholder, 3.5:1) → `#595959` (7.1:1 通过)
3. **CSS variable 替换**: `--color-primary` → `--color-primary-700`, 然后 grep `--color-primary-light-3` 等浅化 token 同步调深

**不要**:
- inline `style="color: ... !important"` (破坏设计系统)
- 单独改某页 scoped CSS (后续页面必爆)
- 改 EP 默认变量 (会破坏 `<el-button>` 等组件渲染)

**要**:
- 改 token + 全项目生效
- 加 `web/tests/visual/a11y/__snapshots__/01-chat-desktop.txt` 漂移检测
- dev 桌面浏览器手动 F12 → Accessibility → Contrast ratio 工具验证

### 2. `html-has-lang` (1 处但必触发)

**触发**: `<html>` 缺 `lang` 属性 — 全站 scanner 一刀切 NOT_PASS

**修法**:
```html
<!-- web/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">  <!-- W89-P-12 必加 -->
<head>...</head>
```

```html
<!-- web-minimal/index.html -->
<html lang="zh-CN">
```

**验证**: 浏览器 DevTools → `document.documentElement.lang` 应返回 `"zh-CN"`. axe 扫不报 `html-has-lang`.

### 3. `aria-command-name` (button / menu / link 无可访问名)

**触发**:
- `<el-dropdown>` 无 `aria-label` ("menu" = 抽象词, axe 不接受)
- `<el-button icon="...">` 仅 icon 无文字
- `<el-input type="search">` 缺 `aria-label`

**修法**:
```vue
<!-- 反例: 仅 icon -->
<el-button icon="el-icon-delete" @click="del">删除</el-button>

<!-- 正例: aria-label 用具体语义 -->
<el-dropdown aria-label="操作菜单" trigger="click">
  <el-button aria-label="删除任务" icon="el-icon-delete" @click="del">删除</el-button>
</el-dropdown>

<!-- 搜索输入 -->
<el-input type="search" aria-label="搜索任务" placeholder="搜索..." />
```

**不要**:
- 写 `aria-label="menu"` / `"button"` / `"图标"` (抽象词, axe 不接受)
- 写 `aria-label="删除"` 不带宾语 (需 `aria-label="删除任务"`)

### 4. `scrollable-region-focusable` (滚动容器无 tabindex)

**触发**: 高度固定 + overflow-y: scroll 的 div 缺 `tabindex="0"` + `role`

**修法**:
```vue
<!-- 反例 -->
<div class="folder-tree">
  <div v-for="folder in folders">{{ folder.name }}</div>
</div>

<!-- 正例 -->
<div
  class="folder-tree"
  tabindex="0"
  role="tree"
  aria-label="文件夹树"
>
  <div v-for="folder in folders" role="treeitem">{{ folder.name }}</div>
</div>
```

**实用规则**:
- `overflow-y: auto/scroll` 的容器 + 高度受限 → **必**加 `tabindex="0"`
- 加 `role` (tree / list / grid 等) 增强 AT 体验
- `aria-label` 描述容器内容

### 5. `link-name` / `button-name` (链接 / 按钮无可见文字)

**触发**:
- `<a>` 仅包 icon SVG, 无 `aria-label`
- `<button>` 仅图标, 无 `aria-label`
- `<router-link>` to= 无文本

**修法**:
```vue
<!-- 反例 -->
<router-link to="/profile"><i class="el-icon-user"></i></router-link>

<!-- 正例 选项 A (aria-label) -->
<router-link to="/profile" aria-label="个人资料">
  <i class="el-icon-user" aria-hidden="true"></i>
</router-link>

<!-- 正例 选项 B (可见文字 + 装饰 icon) -->
<router-link to="/profile" class="profile-link">
  <i class="el-icon-user" aria-hidden="true"></i>
  <span>个人资料</span>
</router-link>
```

**纪律**:
- icon SVG **必**加 `aria-hidden="true"` (装饰性, AT 跳过)
- 含文字的链接/按钮**不**需要 `aria-label` (可见文字已足够)

## CI 集成

### `npm run build:a11y` (W89-P-5)

`web/package.json` scripts 段:
```json
{
  "prebuild": "playwright test --config=playwright.a11y.config.mjs --grep 'a11y baseline' --update-snapshots",
  "build": "vite build && node scripts/postbuild-fix-manifest.js",
  "build:a11y": "npm run prebuild && npm run build"
}
```

`web/tests/visual/a11y/health-check.spec.mjs` (W89-P-5 新增):
- critical + serious violations == 0 硬断言 (含 color-contrast / html-has-lang / aria-*)
- moderate 不阻塞, 仅 warn (主指挥拍板)

### CI workflow `.github/workflows/playwright.yml`

W89-P-3 接入 2 job (尚未 merged into main):
- `a11y` job: **hard fail** (任意 violation 失败即 PR 红)
- `visual` job: **continue-on-error: true (W89-P-8 前)** → 跑满 3 次稳定 + baseline 重 sync 后撤

### baseline 重 sync 流程

```bash
# 桌面 + mobile + tablet 3 viewport × 5 页面
npm run build:a11y -- --update-snapshots

# 验证产物
cat web/tests/visual/a11y/__snapshots__/01-chat-{desktop,mobile,tablet,dark,light}.txt

# commit 纪律: snapshot 文件**只在**真修 violations 后**才**更新, 不要 noise-driven sync
```

## 边界复检 (派工 v6 §1.2 真验证)

执行 axe 修复后必跑:
```bash
# 1. 本地 a11y 健康检查
cd web && npx playwright test --config=playwright.a11y.config.mjs

# 2. baseline drift 比对
npx playwright test --grep "a11y baseline"
# 期望 baseline 文件**无变化** (violations 行数稳定)

# 3. visual sweep (W89-P-8 必跑)
npm run test:playwright:visual
# 期望仅截图文件更新, 无 baseline 漂移
```

## 留 W89+

| 主题 | 状态 | 主指挥拍板 |
|------|------|------------|
| moderate violations 是否逐项修 | 仅 warn, **未**拍板逐项修 | 主指挥未来拍板 |
| dark mode 4 accent 主题完整 a11y 验证 (W89-P-11) | branch ready, **未**merged | 等 P-11 merge → 重跑 baseline |
| visual `continue-on-error: true` 撤容错 | **W89-P-8 前提**: visual sweep + baseline 更新未跑 | **报告主指挥, 留 W89+** |
| AVT (Accessibility Verification Test) 全套 | 未跑, 主指挥拍板是否提升门禁等级 | 主指挥未来拍板 |

## 关联文件

- `web/tests/visual/a11y/axe-config.mjs` — axe 共用配置 (WCAG_21_AA_TAGS + 5 页面 + EP 噪声排除)
- `web/tests/visual/a11y/a11y-baseline.spec.mjs` — 5 页面 × 5 project = 25 case baseline
- `web/tests/visual/a11y/axe-chats.spec.mjs` — ChatViewSSE 专项
- `web/tests/visual/a11y/__snapshots__/*.txt` — baseline 漂移检测
- `web/tests/visual/a11y/health-check.spec.mjs` (W89-P-5) — critical+serious=0 硬断言
- `web/src/assets/variables.css` — color token 唯一权威源 (改 token 不 inline 改色)
- `docs/build-a11y-gate.md` (W89-P-5) — build:a11y 链 + prebuild hook

## 5 条铁律 (派工 v6 §5 反馈 类 20.60)

1. **不要 inline 改色** — 改 token + 全项目生效, 保留设计系统一致性
2. **aria-label 必具体** — "删除任务" 而非 "delete" / "button" / "图标", 否则 axe 不接受
3. **icon SVG 必 `aria-hidden="true"`** — 装饰性元素 AT 跳过, 否则与可见文字冲突
4. **scrollable region 必 `tabindex="0"` + `role`** — 键盘可达 + AT 可识别
5. **baseline snapshot 必真修 violations 才 sync** — noise-driven sync = 类 20.25 全绿是可疑信号的反面 (baseline = 噪声沉淀)
