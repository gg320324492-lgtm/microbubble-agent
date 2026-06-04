# 代码质量全面升级 — 设计规格

> 日期: 2026-06-04
> 状态: 待审批
> 方案: 逐层推进（方案 A）

## 1. 背景与目标

### 1.1 问题现状

| 维度 | 现状 | 风险 |
|------|------|------|
| 巨型文件 | KnowledgeView 2236行、TaskView 1173行、MeetingView 1086行 | 难维护、易出 bug |
| 测试覆盖 | 后端 33 个测试文件但覆盖有限，前端 0 个测试 | 回归风险高 |
| API 设计 | 命名不一致、错误格式混乱、无统一分页 | 不专业、难对接 |
| 安全防护 | 仅登录端点有限流，缺安全响应头 | 恶意请求可打垮服务 |

### 1.2 升级目标

- 前端主要 View 组件拆分至 ≤200 行/文件
- 后端核心服务测试覆盖率 ≥70%
- 全站 API 统一规范（命名/状态码/分页/错误格式）
- 全站 API 限流 + 安全响应头

### 1.3 约束

- 不改变现有功能行为（纯重构 + 补测试）
- 不改变数据库 schema
- 不改变前端 URL 路由
- 每层完成后系统必须可用（可独立部署）

---

## 2. 执行方案：逐层推进

```
第 1 轮：API 规范化（全站统一）
第 2 轮：后端测试补全（核心服务 + API 集成）
第 3 轮：前端组件拆分（KnowledgeView → TaskView → MeetingView）
第 4 轮：前端测试补全（Vitest 单元测试）
```

每轮独立可验证，API 改完后测试直接覆盖新规范，组件拆分后测试直接写在新结构上。

---

## 3. 第 1 轮：API 规范化

### 3.1 统一错误响应格式

**当前状态**：各端点错误格式不一致（`{"detail": "..."}` vs `{"error": "..."}`）

**目标格式**：
```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "任务不存在",
    "details": {"task_id": 123}
  }
}
```

**实现方式**：
- 新增 `app/core/exceptions.py`，定义业务异常类层次
- 新增 FastAPI exception handler 统一格式化
- 各端点的 try/except 改为抛业务异常

**异常类层次**：
```
AppException (base)
├── NotFoundException (404)
├── ValidationException (422)
├── AuthException (401)
├── ForbiddenException (403)
├── ConflictException (409)
└── RateLimitException (429)
```

### 3.2 统一分页格式

**当前状态**：部分端点用 `skip/limit`，部分无分页

**目标格式**：
```json
// 请求: GET /tasks?page=1&page_size=20
// 响应:
{
  "items": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 156,
    "total_pages": 8
  }
}
```

**实现方式**：
- 新增 `app/schemas/pagination.py`，定义 `PaginationParams` 和 `PaginatedResponse`
- 各列表端点统一使用 `PaginationParams` 作为 Query 参数
- 返回统一使用 `PaginatedResponse` 包装

### 3.3 命名规范化

| 当前 | 规范化后 | 说明 |
|------|---------|------|
| `GET /reminders/pending-count` | `GET /reminders/stats` | 统计信息用 stats |
| `POST /meetings/{id}/agenda` | `PATCH /meetings/{id}/agenda` | 部分更新用 PATCH |
| `POST /tasks/{id}/restore` | `POST /tasks/{id}/restore` | 保持（动作类用 POST） |
| `DELETE /tasks/{id}` | `DELETE /tasks/{id}` | 保持，响应加 `deleted_at` 字段 |

### 3.4 全站 API 限流

**当前状态**：仅登录端点有 rate_limit

**扩展方案**：按端点类型分级限流

| 类型 | 限制 | 适用端点 |
|------|------|---------|
| 认证 | 5 次/分钟 | `/auth/login`, `/auth/register` |
| 写操作 | 30 次/分钟 | POST/PUT/PATCH/DELETE |
| 读操作 | 100 次/分钟 | GET |
| 上传 | 10 次/分钟 | `/upload/*` |

**实现方式**：
- 扩展 `app/core/rate_limit.py`，支持按类型配置
- 新增 `RateLimitMiddleware` 中间件，自动按 HTTP 方法分类
- 登录端点保留独立限流逻辑

### 3.5 安全响应头

**Nginx 添加**（`nginx/conf.d/tunnel.conf`）：
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

**FastAPI 添加**（`app/main.py`）：
```python
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Request-ID"] = str(uuid4())
    return response
```

---

## 4. 第 2 轮：后端测试补全

### 4.1 测试架构

```
tests/
├── conftest.py              # 完善 — 补充 fixtures
├── unit/                    # 新增 — 服务层单元测试
│   ├── test_task_service.py
│   ├── test_meeting_service.py
│   ├── test_knowledge_service.py
│   ├── test_member_service.py
│   ├── test_voiceprint_service.py
│   └── test_reminder_service.py
├── integration/             # 新增 — API 集成测试
│   ├── test_api_tasks.py
│   ├── test_api_meetings.py
│   ├── test_api_knowledge.py
│   ├── test_api_auth.py
│   └── test_api_members.py
└── existing tests...        # 保留已有 33 个测试文件
```

### 4.2 单元测试策略（service 层）

每个 service 方法测 3 类场景：
- **正常路径**：标准输入 → 预期输出
- **边界条件**：空值、极大值、边界状态
- **错误处理**：不存在的资源、权限不足、并发冲突

**优先级排序**：
1. `task_service.py`（最简单，验证框架可用）
2. `meeting_service.py`（核心业务）
3. `knowledge_service.py`（复杂逻辑最多）
4. `member_service.py`（声纹相关）
5. `voiceprint_service.py`（外部依赖多）
6. `reminder_service.py`（时间相关）

### 4.3 集成测试策略（API 层）

使用 `httpx.AsyncClient` 测试真实 HTTP 请求：
- 认证流程（登录 → 获取 token → 访问受保护端点）
- 权限检查（不同角色的访问控制）
- 响应格式（验证符合新规范的错误/分页格式）
- 完整 CRUD 流程（创建 → 查询 → 更新 → 删除 → 恢复）

### 4.4 依赖 Mock

| 外部依赖 | Mock 策略 |
|---------|----------|
| PostgreSQL | 使用测试数据库（已有 conftest.py） |
| Redis | 使用 `fakeredis` |
| Claude API | 使用 `respx` mock HTTP 响应 |
| Embedding 模型 | 使用固定向量 mock |
| MinIO | 使用 `tmp_path` fixture 本地文件 |

### 4.5 conftest.py 补充

新增 fixtures：
- `mock_redis` — fakeredis 实例
- `mock_claude` — respx mock 的 Claude API 响应
- `mock_embedding` — 返回固定 192 维向量
- `sample_task` / `sample_meeting` / `sample_member` — 测试数据工厂
- `auth_headers` — 带有效 JWT 的请求头

---

## 5. 第 3 轮：前端组件拆分

### 5.1 KnowledgeView.vue（2236 行 → ~8 个文件）

```
views/
├── KnowledgeView.vue              # ~150 行 — 路由容器 + tab 切换
├── knowledge/
│   ├── KnowledgeDashboard.vue     # ~200 行 — 知识库概览 tab
│   ├── KnowledgeSearch.vue        # ~180 行 — 语义搜索 tab
│   ├── KnowledgeRelations.vue     # ~150 行 — 关联图谱 tab
│   ├── KnowledgeEntities.vue      # ~150 行 — 实体图谱 tab（含 ECharts）
│   ├── KnowledgeHypotheses.vue    # ~150 行 — 假设生成 tab
│   ├── KnowledgeFormulas.vue      # ~150 行 — 公式库 tab
│   └── KnowledgeHealth.vue        # ~120 行 — 健康监控 tab
composables/
└── useKnowledge.js                # ~200 行 — 共享状态 + API 调用
```

### 5.2 TaskView.vue（1173 行 → ~5 个文件）

```
views/
├── TaskView.vue                   # ~120 行 — 主容器 + 筛选
├── task/
│   ├── TaskList.vue               # ~200 行 — 任务列表 + 分页
│   ├── TaskDetail.vue             # ~180 行 — 任务详情侧边栏
│   ├── TaskCreateDialog.vue       # ~150 行 — 新建/编辑弹窗
│   └── TaskTrash.vue              # ~120 行 — 垃圾桶 tab
composables/
└── useTask.js                     # ~200 行 — 共享状态 + API 调用
```

### 5.3 MeetingView.vue（1086 行 → ~5 个文件）

```
views/
├── MeetingView.vue                # ~120 行 — 主容器
├── meeting/
│   ├── MeetingList.vue            # ~200 行 — 会议列表
│   ├── MeetingCreateDialog.vue    # ~180 行 — 新建弹窗（含模板选择）
│   ├── MeetingDetail.vue          # ~200 行 — 会议详情（转录/摘要）
│   └── MeetingStats.vue           # ~150 行 — 发言统计图表
composables/
└── useMeeting.js                  # ~200 行 — 共享状态 + API 调用
```

### 5.4 Composable 设计模式

```javascript
// composables/useTask.js
export function useTask() {
  const tasks = ref([])
  const loading = ref(false)
  const currentPage = ref(1)
  const filters = ref({ status: 'all', search: '' })

  const fetchTasks = async () => { ... }
  const createTask = async (data) => { ... }
  const deleteTask = async (id) => { ... }

  const filteredTasks = computed(() => { ... })
  const pagination = ref({ total: 0, pageSize: 20 })

  return {
    tasks, loading, currentPage, filters,
    fetchTasks, createTask, deleteTask,
    filteredTasks, pagination
  }
}
```

### 5.5 拆分原则

1. **单一职责**：每个子组件只做一件事
2. **Props down, Events up**：父传 props，子 emit 事件
3. **Composable 共享**：多组件共用逻辑抽到 composable
4. **路由不变**：URL 不变，用户无感知
5. **逐个迁移**：先拆一个 tab，验证后再拆下一个

### 5.6 执行顺序

1. KnowledgeView（最大，收益最高）
2. TaskView
3. MeetingView
4. Dashboard（797 行）和其他中型组件

---

## 6. 第 4 轮：前端测试补全

### 6.1 测试架构

```
web/src/
├── composables/__tests__/
│   ├── useTask.test.js
│   ├── useMeeting.test.js
│   └── useKnowledge.test.js
├── components/task/__tests__/
│   ├── TaskList.test.js
│   └── TaskCreateDialog.test.js
└── __tests__/setup.js
```

### 6.2 Composable 测试（优先级最高）

```javascript
describe('useTask', () => {
  it('fetchTasks 成功后更新列表', async () => {
    const mockTasks = [{ id: 1, title: '测试任务' }]
    vi.mock('../../api/task', () => ({
      getTasks: vi.fn().mockResolvedValue({ items: mockTasks, pagination: { total: 1 } })
    }))
    const { tasks, fetchTasks } = useTask()
    await fetchTasks()
    expect(tasks.value).toEqual(mockTasks)
  })
})
```

### 6.3 组件测试（选择性覆盖）

```javascript
describe('TaskCreateDialog', () => {
  it('提交时 emit create 事件', async () => {
    const wrapper = mount(TaskCreateDialog)
    await wrapper.find('input[name="title"]').setValue('新任务')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('create')).toBeTruthy()
  })
})
```

### 6.4 Vitest 配置

```javascript
// vitest.config.js
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/__tests__/setup.js'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/composables/**', 'src/components/**']
    }
  }
})
```

### 6.5 依赖 Mock

| 依赖 | Mock 方式 |
|------|----------|
| Element Plus | 直接 mount |
| API 调用 | `vi.mock` 模块级 mock |
| Router | `createRouter` mock |
| Pinia | `createTestingPinia` |
| ECharts | `vi.mock('echarts')` |

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| API 改名导致前端调用失败 | 中 | 高 | 保留旧端点别名 1 个版本，前端先改 |
| 组件拆分引入渲染 bug | 中 | 中 | 逐个 tab 迁移，每拆一个立即手动验证 |
| 测试 mock 不准确 | 低 | 中 | 使用真实数据库做集成测试兜底 |
| 并行改动冲突 | 低 | 低 | 逐层推进，不并行 |

---

## 8. 成功标准

| 指标 | 目标值 |
|------|--------|
| 前端最大文件行数 | ≤ 200 行 |
| 后端核心服务测试覆盖 | ≥ 70% |
| API 命名一致性 | 100% 符合 RESTful 规范 |
| 错误响应格式一致性 | 100% 统一格式 |
| 全站 API 限流覆盖 | 100% 端点有限流 |
| 安全响应头 | 5 个标准头全部到位 |
| 前端测试 | ≥ 10 个 composable 测试文件 |

---

## 9. 不在范围内

- 数据库 schema 变更
- 前端 URL 路由变更
- 新功能开发
- 性能优化（后续轮次）
- 无障碍合规（后续轮次）
- Docker/部署配置变更（安全头除外）
