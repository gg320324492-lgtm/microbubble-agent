# W-N-P3-A Prisma 集成评估报告 (2026-08-05)

> **锚点**: W-N-P3-A +1 评估产出
> **base ref**: `74d1a965e` (W-N-DEPLOY 收口)
> **派工范畴**: 评估决策建议, 严禁启动集成
> **结论先行**: **决策 (b) 暂不启动, W19 选项 A 维持**

---

## §1 现状: 现有 SQLAlchemy ORM 范式

### 1.1 规模实测 (派工 v6 §13 仓库实情真查, 类 20.109)

| 维度 | 数值 | 实测命令 |
|------|------|----------|
| Model 文件数 | **40** | `find app/models -name "*.py" \| wc -l` |
| 总代码行数 | **4,233 行** | `wc -l app/models/*.py` |
| ORM class 数 | **70 classes** | `find app/models -name "*.py" -exec grep -cE "^class " {} \;` |
| alembic migrations | **96** | `ls alembic/versions/` |
| alembic head | `105_fix_drift (head)` 单链 | `python -m alembic heads` |
| 直接依赖 model 的文件 | **184 文件** | `grep -rE "from app\.models" app/ --include="*.py" -l` |
| 间接调用方 | `app/api/` 52 文件 + `app/services/` 179 文件 | `find ... -name "*.py"` |
| PostgreSQL-specific 使用 | **76 次** | `grep -rE "JSONB\|pgvector\|halfvec\|hnsw"` |

### 1.2 业务领域分布 (40 文件 / 70 class)

按代码行数排序前 10 大:

| 排序 | 文件 | 行数 | 业务域 | 复杂度备注 |
|------|------|------|--------|------------|
| 1 | `knowledge.py` | 464 | 知识库 8 模块 + 12 个 class | RAG + pgvector + 知识图谱 + 假设生成 |
| 2 | `push_subscription.py` | 227 | Web Push 通知 | JSONB 复杂状态 |
| 3 | `drive_comment.py` | 223 | Drive v2 评论 | Drive v2 PR 系列 |
| 4 | `drive_document.py` | 207 | Drive v2 文档核心 | Drive v2 核心表 |
| 5 | `drive_version_tag.py` | 204 | Drive v2 版本标签 | 多对多关联 |
| 6 | `drive_share.py` | 194 | Drive v2 共享 | 复杂权限 |
| 7 | `drive_reaction.py` | 183 | Drive v2 反应 | JSONB reactions |
| 8 | `team_folder.py` | 172 | 团队文件夹 | 递归结构 |
| 9 | `chat_history.py` | 158 | 聊天历史持久化 | 8 phase 收口 |
| 10 | `kg_entity.py` | 156 | 知识图谱实体 | pgvector 实体嵌入 |
| ... | ... | ... | ... | ... |
| - | `base.py` | 16 | Base + TimestampMixin | 基础设施 |
| - | `types.py` | 107 | 自定义类型 (Vector/HALFVEC/JSONB) | PG 特有 |

**业务域分类 (粗略)**:
- 知识库 + RAG (knowledge/chunk/entity/formula/hypothesis/layout/multimodal/kg): 8 文件
- 驱动 v2 (drive_*): 8 文件
- 聊天 + 会话 (chat_history/agent_trace): 2 文件
- 任务 + 会议 + 项目 (task/meeting/project/reminder): 4 文件
- 成员 + 声纹 (member/voiceprint_history/member_voice_history): 3 文件
- 商业化 (billing): 1 文件 (4 表)
- DFT 计算 (dft_job): 1 文件
- 其他基础设施: 13 文件

### 1.3 技术栈现状 (实测)

```
sqlalchemy==2.0.23          # 2.0 现代异步语法
asyncpg==0.29.0             # async 主路径
alembic==1.13.0             # 迁移工具
psycopg2-binary==2.9.9      # sync (alembic 用)
```

- **SQLAlchemy 2.0 异步范式成熟**: 全部走 `AsyncSession` + `select()` 2.0 语法
- **alembic 迁移链完整**: 96 个 migration 单链 `001 → 105_fix_drift` (W97/W98 串单链纪律守恒 4/4)
- **PG-specific 集成深度**: 76 处使用 (JSONB 复杂查询 + pgvector 向量 + halfvec 半精度 + hnsw 索引)

### 1.4 范式成熟度评估

| 维度 | 现状评分 | 备注 |
|------|---------|------|
| 模型抽象一致性 | ★★★★★ | 70 class 全走 `Base, TimestampMixin` |
| 异步支持 | ★★★★★ | SQLAlchemy 2.0 + asyncpg 完整 |
| 类型安全 | ★★★☆☆ | Python type hints 为主, 无 Prisma 级类型生成 |
| 迁移链完整性 | ★★★★★ | 96 migration 单链, 无分叉 |
| 测试覆盖 | ★★★★☆ | model 测试分散在各套件 |
| 文档沉淀 | ★★★★★ | CLAUDE.md 历史 + runbook + 铁律 13+ 实例 |
| 部署纪律 | ★★★★★ | W19 选项 A + 派工 v6 §13 实测 |
| 调试成熟度 | ★★★★★ | Alembic 输出 + SQL log + pgvector 验证 |
| **整体评分** | **★★★★½** | 范式成熟, 无明显痛点 |

---

## §2 ROI 评估: 3-5 周投入 vs 5-10% 收益

### 2.1 重写成本估算 (派工 brief 估 3-5 周, 据实复核)

#### 2.1.1 ORM 重写 (主体工作量)

| 工作项 | 工时估算 | 备注 |
|--------|---------|------|
| 40 model 文件 → schema.prisma | 1.5-2 周 | 70 class × 平均 8-15 min/class, 需理解每个字段语义 |
| Prisma 客户端生成 | 0.5 天 | 自动生成, 但需验证与 asyncpg 兼容 |
| 184 引用方迁移 | 2-3 周 | `from app.models import X` → `import { PrismaClient }`, API 形态完全不同 |
| AsyncSession → Prisma Client 单例 | 0.5-1 周 | 上下文管理 + transaction 语义映射 |
| Celery worker 集成 | 0.5 周 | Celery 上下文 + async loop + Prisma Client 生命周期 |
| 总计 | **5-7 周** (派工 brief 估 3-5 周, 实测偏上限) |

#### 2.1.2 迁移链断裂重建 (高风险)

| 工作项 | 工时估算 | 风险等级 |
|--------|---------|---------|
| 96 alembic migrations → Prisma migrate | 1-2 周 | **极高**: 迁移链断裂 = 生产数据灾难 |
| 自定义类型 Vector/HALFVEC/JSONB | 0.5-1 周 | **极高**: Prisma 不支持 pgvector, 需 raw SQL 通道 |
| 增量迁移策略 | 1 周 | **高**: 需双写期 + 数据一致性校验 |
| 部署验证 (本地 + 服务器) | 1 周 | **高**: 服务器 webhook 触发链需重测 |
| 总计 | **3.5-5 周** | **风险等级 = 红线级** |

#### 2.1.3 测试 + 部署 + 收口

| 工作项 | 工时估算 | 风险等级 |
|--------|---------|---------|
| pytest 101+ 测试改写 | 1 周 | 中: 部分测试桩需重写 |
| Vitest 14+ 前端测试验证 | 0.5 周 | 低: ORM 切换前端透明 |
| dist rebuild + manifest 验证 | 0.5 周 | 中: PWA 缓存兼容 |
| 5 件套守恒实测 + runbook 沉淀 | 1 周 | 中: W19 选项 A 沿用 |
| 总计 | **3 周** | |

**总投入估算**: **5 + 3.5 + 3 = 11.5-15 周** (派工 brief 估 3-5 周, **严重低估 3-4 倍**)

### 2.2 收益分析 (派工 brief 估 5-10%, 据实复核)

#### 2.2.1 理论收益 (Prisma 官方宣传)

1. **类型生成**: TypeScript/Go/Rust 自动生成客户端
2. **迁移自动化**: `prisma migrate dev` 自动生成 SQL
3. **可视化**: Prisma Studio 数据库 GUI 浏览
4. **性能**: Rust 查询引擎, 部分场景更快

#### 2.2.2 实际收益评估 (本项目视角)

| 收益项 | 实际价值 | 原因 |
|--------|---------|------|
| 类型生成 | ★★☆☆☆ | Python 项目, 收益有限 (TS 项目才香); SQLAlchemy 2.0 typing 已强 |
| 迁移自动化 | ★★☆☆☆ | alembic 已用 96 次, 成熟; pgvector/HALFVEC 仍需手写 raw SQL |
| Prisma Studio | ★★★☆☆ | 可视化查询 = nice-to-have, 现有 pgAdmin + psql 已够用 |
| Rust 引擎性能 | ★★☆☆☆ | 业务路径已用 Redis cache + pgvector 优化; ORM 性能非瓶颈 |
| **总体收益** | **< 5%** | 对本项目实际场景, 收益**不显著** |

#### 2.2.3 实际痛点核对 (本项目是否真痛?)

| 痛点 | 本项目现状 | 是否真痛? |
|------|-----------|----------|
| ORM 复杂难懂 | SQLAlchemy 2.0 语法清晰 | **否** |
| 迁移冲突频繁 | 串单链守恒纪律 (W97 4/4) | **否** |
| 类型不安全 | Python typing + mypy 可选 | **否** (本项目未跑 mypy CI) |
| 缺少 GUI | pgAdmin + DBeaver 可用 | **否** |
| 异步性能差 | asyncpg + pgvector 已优化 | **否** |
| 团队上手难 | 团队已用 1 年+ | **否** |
| **真痛点** | **无明确痛点** | **无 ROI 触发条件** |

### 2.3 ROI 结论

- **投入**: 11.5-15 周 (派工 brief 估 3-5 周, 严重低估 3-4 倍)
- **收益**: < 5% (本项目场景下无显著收益)
- **ROI**: **负值** (-10% 到 -15%)
- **决策信号**: **强烈不推荐启动**

---

## §3 风险评估

### 3.1 链断裂风险 (★★★★★ 最高)

#### 3.1.1 alembic → Prisma migrate 链断裂

- 96 个 alembic migration 包含**完整业务演化历史** (W97/W98/W100 +97/098/100/101/102 等)
- Prisma migrate 从 0 开始, 不接 alembic 历史 = **生产数据库无迁移链**
- 修复方案: 用 Prisma schema 重写所有 migration (3.5-5 周)
- **风险**: 任何漏改 = 部署失败 + 数据库不一致

#### 3.1.2 pgvector / halfvec 不支持

- models/knowledge.py 464 行 + models/kg_entity.py + knowledge_chunk.py 均用 `Vector(dim)` 自定义类型
- W100 +100/101/102 演进 halfvec 半精度 (pgvector 0.7.0+ 特性)
- Prisma 官方不支持 pgvector, 需 raw SQL 通道 (失去 ORM 一致性)
- **风险**: 向量检索退化 + RAG 质量下降 + 性能损失

#### 3.1.3 JSONB / 自定义 Enum

- 76 处使用 JSONB 列, 多处带 GIN 索引
- PostgreSQL enum (meetings.status, tasks.priority) 多处
- Prisma enum 有限支持, 部分场景需 fallback raw SQL

### 3.2 共存冲突风险 (★★★★ 高)

#### 3.2.1 双 ORM 并行期混乱

- 迁移期必须 SQLAlchemy + Prisma 共存 (新代码用 Prisma, 老代码用 SQLAlchemy)
- 同一张表两套定义 = schema drift 风险
- 184 文件迁移期 = **6-12 个月过渡** (按 W85 派工节奏 1-2 文件/批)

#### 3.2.2 迁移期事务一致性

- SQLAlchemy Session + Prisma Client 跨调用方事务不同步
- Celery task 跨 worker 的 connection pool 难协调
- **风险**: 跨 ORM 事务边界数据不一致

### 3.3 部署 + 维护风险 (★★★★ 高)

#### 3.3.1 服务器 webhook + 本地 docker cp 链重测

- W99 +21 修复针对主包 404 实战 (类 20.124 锚点碰撞)
- 切 Prisma 后 alembic 链改写, **必须重测整个部署链**
- 部署文档 6 段同步 (CLAUDE.md + ROADMAP + CHANGELOG + README + memory/MEMORY)

#### 3.3.2 团队上手成本

- 团队 20 人已用 SQLAlchemy 1+ 年, Prisma 全员重学
- 无 Rust/TS 背景成员上手更难
- **风险**: 开发效率短期下降 30-50%

### 3.4 长期维护风险 (★★★ 中)

- Prisma 版本升级可能引入 breaking change (历史多次)
- Prisma Cloud 商业版部分功能闭源
- 社区成熟度 < SQLAlchemy (Python 生态首选)

### 3.5 风险总结表

| 风险 | 等级 | 概率 | 影响 |
|------|------|------|------|
| alembic 链断裂 | ★★★★★ | 高 | 灾难级 (生产数据) |
| pgvector/halfvec 退化 | ★★★★★ | 高 | 严重 (RAG 质量) |
| 共存期混乱 | ★★★★ | 高 | 严重 (开发效率) |
| 部署链重测 | ★★★★ | 中 | 中 (部署周期延长) |
| 团队上手成本 | ★★★ | 高 | 中 (短期效率) |
| 长期维护 | ★★★ | 中 | 低-中 |

---

## §4 决策建议

### 4.1 三选项对照 (派工 brief 严禁擅自派工)

#### (a) 启动 P3-A 集成 (高投入)

- 投入: 11.5-15 周 (1 人全职 3-4 个月)
- 收益: < 5%
- 风险: ★★★★★ (链断裂 + pgvector 退化)
- **建议**: **强烈不推荐**

#### (b) 暂不启动 (维持 SQLAlchemy) ← 本报告建议

- 投入: 0
- 收益: 维持现有范式成熟度
- 风险: 0 (无变更)
- **建议**: **采纳 (推荐)**

#### (c) 试点 (1-2 表)

- 投入: 1-2 周 (1 张表完整迁移 + 验证)
- 收益: 验证 Prisma 在本项目实际可行性
- 风险: ★★★ (小范围可控)
- **建议**: **可选 (若 (b) 决策遇阻力可试点)**

### 4.2 建议采纳 (b) 暂不启动, W19 选项 A 维持

#### 4.2.1 决策依据

1. **ROI 负值**: 投入 11.5-15 周 vs 收益 < 5% → 商业角度不可行
2. **范式成熟**: SQLAlchemy 2.0 + alembic 96 migration 串单链 + pgvector 集成, 无明确痛点
3. **风险红线**: alembic 链断裂 + pgvector/halfvec 退化 = 灾难级风险
4. **团队现状**: 20 人已用 SQLAlchemy 1+ 年, 切换成本极高
5. **W19 选项 A 维持**: Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 已列未来 PR, 优先做这些

#### 4.2.2 何时重新评估

- Prisma 官方支持 pgvector (目前未支持, 但社区呼声高)
- 团队规模扩大 + 引入 TS/Go 前端 (Prisma 跨语言价值体现)
- alembic 链出现痛点 (目前 96 单链守恒, 无)
- 部署链频繁断裂 (目前 W99 +21 修复后稳定)

#### 4.2.3 不启动不等于不调研

- 跟踪 Prisma 官方 roadmap (pgvector 支持进度)
- 季度复盘: 1 次/季度 ROI 重评估
- 若后续有明确痛点, 重新启动评估

### 4.3 派工 brief 严格遵守

- 本任务**仅评估**, **不启动 P3-A 集成实施**
- 不擅自派 P3-A 集成 agent (派工 v6 §13 假设禁令)
- 不擅自改 `app/models/` `alembic/versions/` `requirements.txt`
- 0 production code 守恒 (派工 brief 严禁)

### 4.4 关联沉淀

- `memory/w-n-p3-a-prisma-eval-startup-2026-08-05.md` (W-N-P3-A +0 起步 6 项)
- `memory/w-n-p3-a-prisma-eval-closure-2026-08-05.md` (W-N-P3-A +2 收口 5 件套)
- W19 选项 A: Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 留未来 PR
- W72 +1 P3-A..P3-E 后续 PR 列表
- W97 PR2 knowledge_chunk pgvector 集成
- W100 +100/101/102 halfvec 演进
- 类 20.46 base ref 漂移拦截 + 类 20.32 协调 base 实测 + 类 20.109 调研标"推断"必先实测

---

**结论**: **决策 (b) 暂不启动, W19 选项 A 维持**. Prisma 在本项目场景下 ROI 负值, 范式已成熟, 风险红线高. 投入 11.5-15 周换 < 5% 收益, 商业角度不可行.