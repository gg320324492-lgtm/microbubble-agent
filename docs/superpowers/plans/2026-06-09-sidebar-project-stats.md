# 侧边栏项目动态组件实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在左侧边栏底部添加「项目动态」组件，展示项目体量、已解决痛点、待做事项、更新日志

**架构：** 静态 JSON 数据 + 后端 API（git 统计）+ Vue 组件（垂直卡片流），集成到 MainLayout 侧边栏底部

**技术栈：** Vue 3 + Element Plus + FastAPI + Redis 缓存

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `web/src/data/changelog.json` | 静态数据：痛点、待做、更新日志 |
| `web/src/components/SidebarProjectStats.vue` | 新组件：垂直卡片流展示 |
| `web/src/layouts/MainLayout.vue` | 修改：侧边栏底部引入组件 |
| `app/api/v1/dashboard.py` | 新增：project-stats 端点（git 统计） |
| `app/main.py` | 修改：注册 dashboard 路由 |

---

### 任务 1：创建静态数据文件 changelog.json

**文件：**
- 创建：`web/src/data/changelog.json`

- [ ] **步骤 1：创建 changelog.json**

```json
{
  "pain_points": [
    {
      "category": "幻觉",
      "icon": "🎯",
      "items": [
        "Whisper 三层防护",
        "反幻觉七重过滤",
        "低置信度短文本过滤"
      ]
    },
    {
      "category": "部署",
      "icon": "🚀",
      "items": [
        "Webhook SSH fallback",
        "Celery 任务丢失修复",
        "ThreadingHTTPServer"
      ]
    },
    {
      "category": "安全",
      "icon": "🔒",
      "items": [
        "Nginx 扫描器屏蔽（88% 恶意流量）",
        "认证限流",
        "sessionStorage 残留修复"
      ]
    },
    {
      "category": "性能",
      "icon": "⚡",
      "items": [
        "声纹维度 256→192 修正",
        "VAD 精细化",
        "silero-vad 本地缓存"
      ]
    },
    {
      "category": "架构",
      "icon": "🏗️",
      "items": [
        "全局录音器单例",
        "WebSocket 闪烁根因定位",
        "async session lazy load"
      ]
    }
  ],
  "todos": [
    { "id": 7, "name": "多模态知识库", "cycle": "4-6 周", "priority": "高" },
    { "id": 8, "name": "实时语音科研助手", "cycle": "6-8 周", "priority": "中" },
    { "id": 9, "name": "自动化文献综述", "cycle": "6-8 周", "priority": "中" },
    { "id": 10, "name": "智能实验方案生成", "cycle": "6-8 周", "priority": "中" },
    { "id": 11, "name": "深度论文理解", "cycle": "4-6 周", "priority": "高" },
    { "id": 12, "name": "课题组专属 AI 研究员", "cycle": "8-12 周", "priority": "低" }
  ],
  "changelog": [
    {
      "date": "2026-06-09",
      "title": "听会后台录音 + 全局指示器",
      "tag": "功能",
      "pain_point": "导航离开录音中断"
    },
    {
      "date": "2026-06-09",
      "title": "Webhook 自动部署修复",
      "tag": "修复",
      "pain_point": "扫描器正则误杀 /webhook"
    },
    {
      "date": "2026-06-09",
      "title": "Nginx 安全防护",
      "tag": "安全",
      "pain_point": "88% 恶意扫描器流量"
    },
    {
      "date": "2026-06-08",
      "title": "Webhint 无障碍+性能+安全头优化",
      "tag": "优化",
      "pain_point": "ARIA/Cache-Control/CSS 动画问题"
    },
    {
      "date": "2026-06-08",
      "title": "垃圾桶批量删除",
      "tag": "功能",
      "pain_point": "批量操作触发限流"
    },
    {
      "date": "2026-06-06",
      "title": "声纹识别系统重大优化",
      "tag": "功能",
      "pain_point": "VAD 精细化 + 语义断句 + KMeans 分裂"
    },
    {
      "date": "2026-06-06",
      "title": "会议纪要标准格式固化",
      "tag": "优化",
      "pain_point": "AI 分析输出密度不一致"
    },
    {
      "date": "2026-06-05",
      "title": "知识库 UI 全面升级",
      "tag": "功能",
      "pain_point": "Dashboard + 分类系统 + 实体图谱"
    },
    {
      "date": "2026-06-05",
      "title": "极简风格前端项目",
      "tag": "功能",
      "pain_point": "独立极简 UI 方案"
    },
    {
      "date": "2026-06-04",
      "title": "代码质量全面升级",
      "tag": "优化",
      "pain_point": "API 规范化 + 测试 + 组件拆分（30 commit）"
    },
    {
      "date": "2026-06-03",
      "title": "垃圾桶软删除系统",
      "tag": "功能",
      "pain_point": "误删任务无法恢复"
    },
    {
      "date": "2026-06-02",
      "title": "声纹会议系统线上修复",
      "tag": "修复",
      "pain_point": "WS 闪烁 + 声纹维度 + pipeline 输入"
    },
    {
      "date": "2026-06-01",
      "title": "声纹会议系统第三波",
      "tag": "功能",
      "pain_point": "声纹库中心 + 跨会议关联 + 模板"
    },
    {
      "date": "2026-05-31",
      "title": "声纹会议系统第二波",
      "tag": "功能",
      "pain_point": "实时声纹识别 + 置信度图表"
    },
    {
      "date": "2026-05-30",
      "title": "声纹会议系统第一波",
      "tag": "功能",
      "pain_point": "3D-Speaker 嵌入 + 会议实时转录"
    },
    {
      "date": "2026-05-28",
      "title": "知识库深层逻辑系统",
      "tag": "功能",
      "pain_point": "自主进化知识大脑（八大模块）"
    },
    {
      "date": "2026-05-25",
      "title": "企业微信部署",
      "tag": "功能",
      "pain_point": "DNS + Nginx + SSL + 成员录入"
    },
    {
      "date": "2026-05-20",
      "title": "前端图片识别",
      "tag": "功能",
      "pain_point": "多模态对话支持"
    },
    {
      "date": "2026-05-19",
      "title": "FRP 内网穿透部署",
      "tag": "功能",
      "pain_point": "云服务器 + 本地电脑分离架构"
    },
    {
      "date": "2026-05-17",
      "title": "Phase 3-5 完成",
      "tag": "功能",
      "pain_point": "Redis 会话 + Alembic + 限流 + 测试 + 腾讯会议 + MinIO"
    },
    {
      "date": "2026-05-16",
      "title": "Phase 1-2 完成",
      "tag": "功能",
      "pain_point": "Agent 工具路由 + 认证 + 语义搜索"
    }
  ]
}
```

- [ ] **步骤 2：验证 JSON 格式**

运行：`node -e "require('./web/src/data/changelog.json')" && echo "JSON valid"`
预期：JSON valid

- [ ] **步骤 3：Commit**

```bash
git add web/src/data/changelog.json
git commit -m "data: 添加项目动态静态数据（痛点/待做/更新日志）"
```

---

### 任务 2：创建后端 API 端点

**文件：**
- 创建：`app/api/v1/dashboard.py`
- 修改：`app/main.py`（注册路由）

- [ ] **步骤 1：创建 dashboard.py**

```python
"""项目动态统计 API"""
import subprocess
import os
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from app.core.redis import redis_client

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# 排除的目录和文件扩展名
EXCLUDE_DIRS = {
    "node_modules", ".git", "dist", "__pycache__", ".venv", "venv",
    "models", ".idea", ".vscode", "alembic/versions"
}
EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".so", ".o", ".a", ".dll", ".exe", ".whl"}


def _count_lines_and_files() -> tuple[int, int]:
    """统计项目源码行数和文件数"""
    total_lines = 0
    total_files = 0
    
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # 排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            # 排除扩展名
            if any(file.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                continue
            
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    total_lines += len(lines)
                    total_files += 1
            except (IOError, UnicodeDecodeError):
                continue
    
    return total_lines, total_files


def _get_git_stats() -> tuple[int, str]:
    """获取 Git 提交总数和首次提交日期"""
    try:
        # 提交总数
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )
        total_commits = int(result.stdout.strip()) if result.returncode == 0 else 0
        
        # 首次提交日期
        result = subprocess.run(
            ["git", "log", "--reverse", "--format=%ai", "--max-count=1"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )
        first_commit_str = result.stdout.strip() if result.returncode == 0 else ""
        
        return total_commits, first_commit_str
    except (subprocess.TimeoutExpired, ValueError):
        return 0, ""


def _calculate_dev_days(first_commit_str: str) -> int:
    """计算开发天数"""
    if not first_commit_str:
        return 0
    try:
        # 解析日期（格式：2026-05-16 22:37:48 +0800）
        first_date = datetime.strptime(first_commit_str[:10], "%Y-%m-%d").date()
        return (date.today() - first_date).days
    except ValueError:
        return 0


@router.get("/project-stats")
async def get_project_stats():
    """获取项目开发统计数据"""
    # 尝试从 Redis 缓存获取
    cache_key = "dashboard:project-stats"
    cached = await redis_client.get(cache_key)
    if cached:
        import json
        return json.loads(cached)
    
    # 计算统计数据
    total_lines, total_files = _count_lines_and_files()
    total_commits, first_commit_str = _get_git_stats()
    dev_days = _calculate_dev_days(first_commit_str)
    
    result = {
        "total_lines": total_lines,
        "total_commits": total_commits,
        "dev_days": dev_days,
        "total_files": total_files
    }
    
    # 缓存 1 小时
    import json
    await redis_client.setex(cache_key, 3600, json.dumps(result))
    
    return result
```

- [ ] **步骤 2：注册路由到 main.py**

在 `app/main.py` 中添加：

```python
from app.api.v1.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="/api/v1")
```

- [ ] **步骤 3：验证 API 可访问**

运行：`curl http://localhost:8000/api/v1/dashboard/project-stats`
预期：返回 JSON `{"total_lines": ..., "total_commits": ..., "dev_days": ..., "total_files": ...}`

- [ ] **步骤 4：Commit**

```bash
git add app/api/v1/dashboard.py app/main.py
git commit -m "feat: 添加项目统计 API（代码行数/commit数/开发天数/文件数）"
```

---

### 任务 3：创建 SidebarProjectStats 组件

**文件：**
- 创建：`web/src/components/SidebarProjectStats.vue`

- [ ] **步骤 1：创建组件**

```vue
<template>
  <!-- 折叠态：仅显示图标 -->
  <div v-if="collapsed" class="stats-collapsed" title="项目动态">
    <el-icon size="20"><DataBoard /></el-icon>
  </div>

  <!-- 展开态：垂直卡片流 -->
  <div v-else class="stats-container">
    <!-- 标题 -->
    <div class="stats-header">
      <span class="stats-title">🚀 项目动态</span>
    </div>

    <!-- 项目体量 -->
    <div class="stats-card">
      <div class="card-title">📊 项目体量</div>
      <div class="card-divider"></div>
      <div class="stat-item">
        <span class="stat-icon">📝</span>
        <span class="stat-text">{{ formatNumber(stats.total_lines) }} 行代码</span>
      </div>
      <div class="stat-item">
        <span class="stat-icon">🔀</span>
        <span class="stat-text">{{ formatNumber(stats.total_commits) }} 次提交</span>
      </div>
      <div class="stat-item">
        <span class="stat-icon">⏱️</span>
        <span class="stat-text">开发 {{ stats.dev_days }} 天</span>
      </div>
      <div class="stat-item">
        <span class="stat-icon">📁</span>
        <span class="stat-text">{{ formatNumber(stats.total_files) }} 个文件</span>
      </div>
    </div>

    <!-- 已解决痛点 -->
    <div class="stats-card">
      <div class="card-title">🔧 已解决痛点</div>
      <div class="card-divider"></div>
      <div v-for="group in data.pain_points" :key="group.category" class="pain-group">
        <div class="pain-header">
          <span class="pain-icon">{{ group.icon }}</span>
          <span class="pain-category">{{ group.category }}</span>
        </div>
        <ul class="pain-list">
          <li v-for="item in group.items" :key="item" class="pain-item">
            · {{ item }}
          </li>
        </ul>
      </div>
    </div>

    <!-- 待做事项 -->
    <div class="stats-card">
      <div class="card-title">🔜 待做事项</div>
      <div class="card-divider"></div>
      <div v-for="todo in data.todos" :key="todo.id" class="todo-item">
        <span class="todo-phase">Phase {{ todo.id }}</span>
        <span class="todo-name">{{ todo.name }}</span>
      </div>
    </div>

    <!-- 更新日志 -->
    <div class="stats-card">
      <div class="card-title">📅 更新日志</div>
      <div class="card-divider"></div>
      <div
        v-for="(log, index) in displayedLogs"
        :key="log.date + log.title"
        class="log-item"
      >
        <span class="log-date">{{ formatDate(log.date) }}</span>
        <span class="log-title">{{ log.title }}</span>
      </div>
      <div
        v-if="data.changelog.length > 5"
        class="log-toggle"
        @click="showAll = !showAll"
      >
        {{ showAll ? '收起' : '查看全部 →' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import changelogData from '@/data/changelog.json'
import { DataBoard } from '@element-plus/icons-vue'

const props = defineProps({
  collapsed: {
    type: Boolean,
    default: false
  }
})

const data = ref(changelogData)
const stats = ref({
  total_lines: 0,
  total_commits: 0,
  dev_days: 0,
  total_files: 0
})
const showAll = ref(false)

const displayedLogs = computed(() => {
  if (showAll.value) {
    return data.value.changelog
  }
  return data.value.changelog.slice(0, 5)
})

const formatNumber = (num) => {
  if (num === undefined || num === null) return '0'
  return num.toLocaleString()
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const parts = dateStr.split('-')
  if (parts.length === 3) {
    return `${parts[1]}-${parts[2]}`
  }
  return dateStr
}

onMounted(async () => {
  try {
    const res = await axios.get('/api/v1/dashboard/project-stats')
    stats.value = res.data
  } catch (e) {
    console.error('获取项目统计失败:', e)
  }
})
</script>

<style scoped>
/* 折叠态 */
.stats-collapsed {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: color var(--duration-fast) var(--ease-out);
}
.stats-collapsed:hover {
  color: var(--color-primary);
}

/* 展开态 */
.stats-container {
  padding: 12px;
  overflow-y: auto;
  max-height: calc(100vh - 64px - 200px); /* 减去 logo 和菜单高度 */
}

.stats-header {
  padding: 8px 0;
  margin-bottom: 8px;
}

.stats-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

/* 卡片 */
.stats-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 12px;
  margin-bottom: 10px;
}

.card-title {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.card-divider {
  height: 1px;
  background: var(--color-border);
  margin-bottom: 8px;
}

/* 体量指标 */
.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.stat-icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
}

.stat-text {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

/* 痛点 */
.pain-group {
  margin-bottom: 10px;
}

.pain-group:last-child {
  margin-bottom: 0;
}

.pain-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.pain-icon {
  font-size: 14px;
}

.pain-category {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.pain-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.pain-item {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  padding: 2px 0 2px 26px;
  line-height: 1.4;
}

/* 待做事项 */
.todo-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.todo-phase {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  min-width: 60px;
}

.todo-name {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

/* 更新日志 */
.log-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 0;
}

.log-date {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  min-width: 45px;
  flex-shrink: 0;
}

.log-title {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-toggle {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
  cursor: pointer;
  padding: 8px 0 0;
  text-align: center;
}

.log-toggle:hover {
  text-decoration: underline;
}
</style>
```

- [ ] **步骤 2：验证组件语法**

运行：`cd web && npx vue-tsc --noEmit 2>&1 | head -20`
预期：无语法错误

- [ ] **步骤 3：Commit**

```bash
git add web/src/components/SidebarProjectStats.vue
git commit -m "feat: 创建 SidebarProjectStats 组件（垂直卡片流）"
```

---

### 任务 4：集成组件到 MainLayout

**文件：**
- 修改：`web/src/layouts/MainLayout.vue`

- [ ] **步骤 1：导入组件**

在 `<script setup>` 中添加：

```javascript
import SidebarProjectStats from '@/components/SidebarProjectStats.vue'
```

- [ ] **步骤 2：在侧边栏底部添加组件**

在 `</el-menu>` 之后、`</el-aside>` 之前添加：

```html
      <!-- 项目动态 — 侧边栏底部 -->
      <div class="sidebar-stats">
        <SidebarProjectStats :collapsed="isCollapse" />
      </div>
    </el-aside>
```

- [ ] **步骤 3：添加样式**

在 `<style scoped>` 中添加：

```css
/* 侧边栏底部项目动态 */
.sidebar-stats {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-sidebar);
}
```

- [ ] **步骤 4：修改侧边栏为相对定位**

在 `.aside` 样式中添加 `position: relative;`：

```css
.aside {
  /* ... 现有样式 ... */
  position: relative;
}
```

- [ ] **步骤 5：验证组件渲染**

运行：`cd web && npm run dev`
预期：侧边栏底部显示项目动态组件，折叠时仅显示图标

- [ ] **步骤 6：Commit**

```bash
git add web/src/layouts/MainLayout.vue
git commit -m "feat: 集成 SidebarProjectStats 到侧边栏底部"
```

---

### 任务 5：构建前端并验证

**文件：**
- 修改：`web/dist/`（构建产物）

- [ ] **步骤 1：构建前端**

运行：`cd web && npm run build`
预期：构建成功，无错误

- [ ] **步骤 2：验证 dist 文件**

运行：`ls -la web/dist/assets/index-*.js | wc -l`
预期：至少 1 个 index-*.js 文件

- [ ] **步骤 3：提交 dist**

```bash
git add -f web/dist/
git commit -m "build: 更新前端 dist（添加项目动态组件）"
```

---

### 任务 6：推送并验证部署

- [ ] **步骤 1：推送代码**

```bash
git push origin main
```

- [ ] **步骤 2：验证 webhook 触发**

检查 `/var/log/webhook-deploy.log` 是否有 `[DEPLOY] 部署成功 ✓`

- [ ] **步骤 3：验证线上页面**

访问 `https://agent.mnb-lab.cn`，检查侧边栏底部是否显示项目动态组件
