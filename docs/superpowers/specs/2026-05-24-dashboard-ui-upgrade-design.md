# Dashboard 首页 UI 全面升级设计方案

**日期：** 2026-05-24
**范围：** Dashboard 首页 + 侧边栏
**目标：** 温馨课题组风格、现代动效、交互友好

---

## 一、设计方向

- **风格：** 温馨课题组（D）
- **配色：** 珊瑚橙主色系 + 玻璃拟态侧边栏
- **动效：** 丰富动效，流畅华丽风格（500ms ease-in-out）
- **信息优先级：** 综合 — 任务概览 + 全员视角 + 截止节点 + 操作入口

---

## 二、配色方案

```css
/* 全局 CSS 变量（写入 web/src/assets/variables.css）*/
:root {
  /* 主色 - 珊瑚橙 */
  --color-primary:       #FF7A5C;
  --color-primary-light: #FF9D85;
  --color-primary-dark:  #E85A3A;
  --color-primary-bg:    #FFF0ED;

  /* 辅助色 - 金橙 */
  --color-accent:        #FFB347;
  --color-accent-bg:     #FFF8ED;

  /* 功能色 */
  --color-success:       #67C23A;
  --color-success-bg:    #F0F9EB;
  --color-warning:       #E6A23C;
  --color-warning-bg:    #FDF6EC;
  --color-danger:        #F56C6C;
  --color-danger-bg:     #FEF0F0;
  --color-info:          #909399;
  --color-info-bg:       #F4F4F5;

  /* 中性色 */
  --color-text-primary:  #2D2D2D;
  --color-text-regular:  #606266;
  --color-text-secondary:#909399;
  --color-text-placeholder: #C0C4CC;
  --color-border:        #EBEEF5;
  --color-bg-page:       #F5F7FA;
  --color-bg-card:       #FFFFFF;

  /* 玻璃拟态侧边栏 */
  --color-bg-sidebar:    rgba(255, 245, 240, 0.92);
  --shadow-glow:        0 4px 24px rgba(255, 122, 92, 0.20);

  /* 阴影层级 */
  --shadow-sm:   0 2px 8px rgba(0,0,0,0.06);
  --shadow-md:   0 4px 16px rgba(0,0,0,0.08);
  --shadow-lg:   0 8px 32px rgba(0,0,0,0.12);
  --shadow-primary: 0 4px 20px rgba(255, 122, 92, 0.30);
}
```

---

## 三、欢迎区

**结构：**
```
┌──────────────────────────────────────────────────────────┐
│  🌤️ 早上好，张三！                              [对话][任务] │
│  2026年05月24日 星期日   09:41:23                          │
│  🎯 您有 12 项进行中任务，逾期 3 项                       │
└──────────────────────────────────────────────────────────┘
```

- 背景：`linear-gradient(135deg, #FF7A5C 0%, #FFB347 100%)`
- 圆角：16px，阴影：`var(--shadow-primary)`
- 右侧快捷按钮：白底圆角按钮，hover 时缩放 1.02
- 背景增加 2-3 个淡色圆形光晕装饰（absolute 定位，opacity 0.2）

**入场动画：** 从上方滑入 + 淡入，400ms ease-out

---

## 四、统计卡片 — 大数字风格

**替换现有圆环，改为大数字卡片组：**

```
┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  🔵           │  │  ✅           │  │  ⏰           │  │  ⚠️           │
│  进行中        │  │  已完成        │  │  即将到期     │  │  已逾期        │
│     12        │  │     28        │  │      5       │  │      3        │
│  ↑ 比昨天多 2  │  │  完成任务消 3  │  │  未来3天     │  │  需要处理     │
└───────────────┘  └───────────────┘  └───────────────┘  └───────────────┘
```

**样式：**
- 左侧：56px 圆形图标区（各颜色对应背景色块 + 白色大图标）
- 中间：大号数字（36px bold）+ 状态标签
- 数字入场：计数器动画 500ms ease-out（从 0 滚动到目标值）
- 卡片入场：staggered，每项延迟 100ms，fadeSlideUp
- 悬停：translateY(-3px) + shadow 增强

---

## 五、进行中任务卡片

**头部：**
- 左侧：🚀 + "进行中任务" 标题
- 右侧：徽章（数量）+ "查看全部 →" 文字链接

**分组列表：**
- 负责人头部可折叠（已有功能，保留）
- 头部悬停：背景加深，左侧橙色指示条滑入（200ms）
- 任务行悬停：淡橙色背景高亮
- 每行右侧："完成"（success 色）+ "编辑"（primary 色）按钮

**入场动画：** 分组依次入场，每组延迟 80ms

---

## 六、即将到期卡片

**按紧急程度分组：**

```
┌─────────────────────────────────────────┐
│  ⏰ 即将到期                          🔔  │
├─────────────────────────────────────────┤
│ 【今天】3项任务    [紧急边框，橙色]       │
│ 【明天】2项任务    [普通边框]             │
│ 【后天】1项任务    [普通边框]             │
│ 【逾期】2项任务    [红色边框+红色背景]    │
└─────────────────────────────────────────┘
```

- 紧急（今天/逾期）：左侧 4px 橙色/红色边条 + 浅底色
- 悬停：整行提升 + 阴影

---

## 七、侧边栏升级（玻璃拟态）

**样式：**
```css
.el-aside {
  background: var(--color-bg-sidebar);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-right: 1px solid rgba(255, 122, 92, 0.12);
  box-shadow: 4px 0 24px rgba(255, 122, 92, 0.08);
}
```

**菜单项：**
- 头像：圆角 12px（`border-radius: 12px`）
- 菜单项 hover：左侧 3px 橙色指示条滑入 + 淡橙色背景
- 选中项：橙色文字 + 左侧 3px 粗橙色边条

---

## 八、骨架屏

Dashboard 加载时三块区域各自显示骨架：
- 统计卡片区：4 个骨架卡片
- 进行中任务区：2-3 个骨架分组
- 会议列表区：3 个骨架会议条目

骨架样式：淡橙灰色块 + shimmer 动画

---

## 九、动画规范汇总

| 元素 | 动画类型 | 时长 | 曲线 |
|------|---------|------|------|
| 欢迎区入场 | 滑入+淡入 | 400ms | ease-out |
| 统计卡片 staggered | fadeSlideUp | 300ms | ease-out |
| 数字计数器 | 0→目标值 | 500ms | ease-out cubic |
| 卡片悬停 | translateY(-3px)+shadow | 200ms | ease-out |
| 按钮悬停 | scale(1.02)+brightness | 150ms | ease-out |
| 按钮按下 | scale(0.97) | 100ms | ease-out |
| 头像悬停 | scale(1.08) | 200ms | ease-out |
| 侧边栏指示条 | width 滑入 | 200ms | ease-out |
| 任务行 stagger | fadeSlideUp | 250ms | ease-out |

---

## 十、关键文件

| 文件 | 改动 |
|------|------|
| `web/src/assets/variables.css` | 新建，全局 CSS 变量 |
| `web/src/main.js` | 导入 variables.css |
| `web/src/views/Dashboard.vue` | 全面重写样式 + 动画 |
| `web/src/layouts/MainLayout.vue` | 侧边栏玻璃拟态 |

---

## 十一、验收标准

- [ ] 页面加载时数字有滚动动画
- [ ] 欢迎区有入场滑入动画
- [ ] 统计卡片有 stagger 入场
- [ ] 卡片悬停有提升动效
- [ ] 侧边栏有玻璃拟态效果
- [ ] 骨架屏正常显示
- [ ] `npm run build` 无报错
- [ ] 移动端布局正常
