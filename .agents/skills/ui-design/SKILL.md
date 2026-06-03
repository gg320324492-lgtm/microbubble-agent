# UI Design Skill — 前端界面设计规范

## 核心理念

好的 UI = 清晰 > 一致 > 美观。设计服务于功能，而非炫技。

---

## 一、设计原则

### 1.1 四大黄金法则

| 法则 | 说明 | 实现方式 |
|------|------|---------|
| ** proximity 接近** | 相关内容靠近 | 分组卡片内边距一致（16-24px），组间间距更大（24-32px） |
| ** alignment 对齐** | 建立视觉联系 | 同级元素左对齐，数字右对齐或居中 |
| ** repetition 重复** | 保持一致性 | 全局颜色变量、圆角 8-12px、阴影层级统一 |
| ** contrast 对比** | 区分主次 | 主操作橙/蓝色，次操作灰色；大标题 vs 说明文字 18px vs 14px |

### 1.2 移动优先原则
- 从 375px 设计起步，大屏逐步增强
- 核心交互在 44px 触控区域内
- 文字最小 12px，颜色对比度 ≥ 4.5:1

---

## 二、色彩系统

### 2.1 主色板（暖橙系，适合课题组温馨氛围）

```css
:root {
  /* 主色 */
  --color-primary:       #FF7A5C;   /* 珊瑚橙，主操作 */
  --color-primary-light: #FF9D85;   /* 主色悬停 */
  --color-primary-dark:  #E85A3A;   /* 主色按下 */
  --color-primary-bg:    #FFF0ED;   /* 主色浅底 */

  /* 辅助色 */
  --color-accent:        #FFB347;   /* 金橙，渐变/高亮 */
  --color-accent-bg:     #FFF8ED;   /* 辅助色浅底 */

  /* 功能色 */
  --color-success:        #67C23A;
  --color-success-bg:     #F0F9EB;
  --color-warning:        #E6A23C;
  --color-warning-bg:     #FDF6EC;
  --color-danger:         #F56C6C;
  --color-danger-bg:     #FEF0F0;
  --color-info:          #909399;
  --color-info-bg:        #F4F4F5;

  /* 中性色 */
  --color-text-primary:  #2D2D2D;
  --color-text-regular:  #606266;
  --color-text-secondary:#909399;
  --color-text-placeholder: #C0C4CC;
  --color-border:        #EBEEF5;
  --color-bg-page:       #F5F7FA;
  --color-bg-card:       #FFFFFF;
  --color-bg-sidebar:    rgba(255, 245, 240, 0.92);

  /* 阴影 */
  --shadow-sm:   0 1px 4px rgba(0,0,0,0.06);
  --shadow-md:   0 4px 16px rgba(0,0,0,0.08);
  --shadow-lg:   0 8px 32px rgba(0,0,0,0.12);
  --shadow-glow: 0 4px 24px rgba(255, 122, 92, 0.25);
}
```

### 2.2 渐变规范
- 主渐变：`linear-gradient(135deg, #FF7A5C 0%, #FFB347 100%)`
- 辅渐变：`linear-gradient(135deg, #667eea 0%, #764ba2 100%)`（保留）
- 暖白渐变：`linear-gradient(180deg, #FFFFFF 0%, #FFF8F5 100%)`

### 2.3 语义化使用

| 场景 | 颜色 |
|------|------|
| 主按钮背景、强调渐变 | primary |
| 进行中状态 | primary-light |
| 已完成、成功状态 | success |
| 警告、即将到期 | warning |
| 逾期、危险操作 | danger |
| 辅助信息、次要操作 | info |
| 侧边栏背景 | bg-sidebar（玻璃拟态）|
| 页面背景 | bg-page |
| 卡片背景 | bg-card |

---

## 三、字体层级

```css
--font-size-xs:   12px;   /* 标签、次要说明 */
--font-size-sm:   13px;   /* 表格正文、辅助信息 */
--font-size-base: 14px;   /* 正文默认 */
--font-size-md:   15px;   /* 卡片标题、组长 */
--font-size-lg:   18px;   /* 区块标题 */
--font-size-xl:   22px;   /* 页面主标题 */
--font-size-2xl:  28px;   /* 欢迎语大字 */

--font-weight-normal:   400;
--font-weight-medium:   500;
--font-weight-semibold: 600;
--font-weight-bold:     700;
```

**行高规则：**
- 正文：1.6
- 标题：1.3
- 紧凑列表：1.4

---

## 四、间距系统

```css
--space-1:  4px;
--space-2:  8px;
--space-3:  12px;
--space-4:  16px;
--space-5:  20px;
--space-6:  24px;
--space-8:  32px;
--space-10: 40px;
--space-12: 48px;
```

**使用规范：**
- 元素内间距：8-16px
- 组件内分组间距：16-24px
- 页面级区块间距：24-32px
- 侧边栏宽度：220px（展开）/ 64px（收缩）

---

## 五、圆角与阴影

### 圆角规范
```css
--radius-sm:   4px;   /* 小标签、小按钮 */
--radius-md:   8px;   /* 卡片、输入框 */
--radius-lg:   12px;  /* 大卡片、对话框 */
--radius-xl:   16px;  /* 欢迎区、特色卡片 */
--radius-full: 9999px; /* 圆形头像、胶囊按钮 */
```

### 阴影层级
```css
--shadow-xs: 0 1px 2px rgba(0,0,0,0.04);
--shadow-sm: 0 2px 8px rgba(0,0,0,0.06);
--shadow-md: 0 4px 16px rgba(0,0,0,0.08);
--shadow-lg: 0 8px 32px rgba(0,0,0,0.12);
--shadow-primary: 0 4px 20px rgba(255, 122, 92, 0.30);
```

---

## 六、动画规范

### 6.1 时间曲线

| 类型 | 用途 | 时长 | 曲线 |
|------|------|------|------|
| 微交互 | 按钮悬停、输入框聚焦 | 150ms | ease-out |
| 状态切换 | 展开/折叠、开关 | 200ms | ease-out |
| 内容进入 | 卡片入场、弹框出现 | 300ms | ease-out |
| 页面过渡 | 路由切换 | 350ms | ease-in-out |
| 数字动画 | 计数器、进度条 | 500ms | ease-out |
| 装饰动画 | 背景光晕、脉冲 | 2000ms+ | ease-in-out |

### 6.2 入场动画模式（Staggered）

```css
/* 依次入场：每项延迟 60-100ms */
.card:nth-child(1) { animation-delay: 0ms; }
.card:nth-child(2) { animation-delay: 80ms; }
.card:nth-child(3) { animation-delay: 160ms; }
.card:nth-child(4) { animation-delay: 240ms; }

@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
.fade-slide-up { animation: fadeSlideUp 300ms ease-out both; }
```

### 6.3 微交互动效

```css
/* 卡片悬停 */
.card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
  transition: all 200ms ease-out;
}

/* 按钮悬停 */
.btn:hover {
  transform: scale(1.02);
  filter: brightness(1.05);
  transition: all 150ms ease-out;
}

/* 按钮按下 */
.btn:active {
  transform: scale(0.98);
  transition: all 100ms ease-out;
}

/* 头像悬停 */
.avatar:hover {
  transform: scale(1.08);
  transition: transform 200ms ease-out;
}
```

### 6.4 数字计数器动画

```javascript
// 数字滚动到目标值
function animateCounter(el, target, duration = 500) {
  const start = 0
  const startTime = performance.now()
  function update(currentTime) {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3) // ease-out cubic
    el.textContent = Math.round(eased * target)
    if (progress < 1) requestAnimationFrame(update)
  }
  requestAnimationFrame(update)
}
```

---

## 七、组件设计规范

### 7.1 卡片组件

```css
.card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--color-border);
  transition: all 200ms ease-out;
  overflow: hidden;
}
.card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
.card-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
  font-weight: var(--font-weight-semibold);
}
.card-body { padding: 20px; }
```

### 7.2 按钮层级

```css
/* 主要操作 */
.btn-primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 10px 20px;
  font-weight: 500;
  box-shadow: var(--shadow-primary);
}
.btn-primary:hover { filter: brightness(1.08); transform: translateY(-1px); }

/* 次要操作 */
.btn-secondary {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-md);
  padding: 10px 20px;
}

/* 文字按钮 */
.btn-text {
  background: none;
  border: none;
  color: var(--color-text-secondary);
  padding: 6px 12px;
  border-radius: var(--radius-sm);
}
.btn-text:hover { background: var(--color-primary-bg); color: var(--color-primary); }
```

### 7.3 头像组件

```css
.avatar {
  border-radius: var(--radius-lg);  /* 圆角头像 */
  object-fit: cover;
  transition: transform 200ms ease-out, box-shadow 200ms ease-out;
}
.avatar:hover {
  transform: scale(1.08);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.avatar-sm  { width: 28px; height: 28px; }
.avatar-md  { width: 36px; height: 36px; }
.avatar-lg  { width: 48px; height: 48px; }
.avatar-xl  { width: 64px; height: 64px; }
```

### 7.4 标签（Tag）规范

```css
.tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: 500;
  gap: 4px;
}
.tag-primary  { background: var(--color-primary-bg); color: var(--color-primary); }
.tag-success  { background: var(--color-success-bg); color: var(--color-success); }
.tag-warning  { background: var(--color-warning-bg); color: var(--color-warning); }
.tag-danger   { background: var(--color-danger-bg); color: var(--color-danger); }
.tag-info     { background: var(--color-info-bg); color: var(--color-info); }
```

---

## 八、骨架屏规范

```css
@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton {
  background: linear-gradient(
    90deg,
    var(--color-border) 25%,
    var(--color-bg-page) 50%,
    var(--color-border) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}

.skeleton-circle  { width: 40px; height: 40px; border-radius: var(--radius-lg); }
.skeleton-text    { height: 14px; margin: 6px 0; }
.skeleton-title   { height: 20px; width: 60%; margin-bottom: 12px; }
.skeleton-button  { height: 36px; width: 80px; border-radius: var(--radius-md); }
```

---

## 九、玻璃拟态规范

```css
.glass {
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
}

.glass-sidebar {
  background: rgba(255, 245, 240, 0.88);
  backdrop-filter: blur(16px);
  border-right: 1px solid rgba(255, 122, 92, 0.1);
  box-shadow: 4px 0 24px rgba(255, 122, 92, 0.08);
}
```

---

## 十、实施检查清单

每个页面 UI 升级前，对照检查：

- [ ] 颜色使用 CSS 变量（--color-*），无硬编码 hex
- [ ] 圆角使用规范值（4/8/12/16px）
- [ ] 阴影使用层级规范（sm/md/lg）
- [ ] 卡片有悬停提升动效（translateY + shadow）
- [ ] 按钮有微交互（hover/active 状态）
- [ ] 入场动画使用 stagger 模式
- [ ] 数字有计数器动画
- [ ] 加载态使用骨架屏
- [ ] 移动端有适配（media query 768px 断点）
- [ ] 无 @keyframes 在组件内重复定义（统一放全局或复用）
