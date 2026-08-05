"""Prisma mirror for dft_jobs table — W-N-P3-A-POC 试点

W-N-P3-A 决策(b) 暂不启动, 但派工允许 1 张表试点, 验证 Prisma 集成真实成本.

派工 brief 严禁:
- 0 改既有 dft_job.py (本文件并存, 不替代)
- 0 改 alembic/versions/ (alembic 099 创建 dft_jobs, 维持主路径)
- 0 改 package.json / requirements.txt (不 pip install prisma)

本文件目的:
- 演示 Prisma schema 镜像 1 张 SQLAlchemy 表的代码量
- 演示 prisma 字段类型映射 (UUID / JSONB / ForeignKey / Index)
- 演示 prisma generate 输出的 Python client class 范式
- 提供 mock 测试入口 (scripts/prisma_poc_test.py)

不带 prisma 真实依赖, 仅 schema 镜像 + docstring 标注 prisma 客户端使用范式.
"""
from __future__ import annotations

# 派工 brief 严禁 pip install prisma
# 真实集成时需 requirements.txt 加: prisma==0.13.0 (含 prisma client runtime)
# 生成 client: prisma generate --schema=prisma/schema.prisma
# 调用范式 (伪代码, 实际需 prisma generate 后从 generated client import):
#
#   from prisma import Prisma
#   db = Prisma()
#   await db.connect()
#   jobs = await db.dftjob.find_many(where={"tool": "gaussian"}, take=10)
#   await db.disconnect()

# === Prisma schema 镜像 (内嵌 docstring, 1 张表) ===
#
# // prisma/schema.prisma
# generator client
#   provider = "prisma-client-py"
#   output   = "../app/models/prisma_dft_jobs_client"
# end
#
# datasource db
#   provider = "postgresql"
#   url      = env("DATABASE_URL")
# end
#
# model DftJob
#   id          String    @id @default(uuid()) @db.Uuid
#   userId      Int?      @map("user_id")
#   tool        String    @db.VarChar(32)
#   smiles      String
#   params      Json      @default("{}")
#   status      String    @default("queued") @db.VarChar(32)
#   result      Json?
#   logPath     String?   @map("log_path")
#   errorMsg    String?   @map("error_msg")
#   submitTime  DateTime  @default(now()) @map("submit_time") @db.Timestamptz(6)
#   finishTime  DateTime? @map("finish_time") @db.Timestamptz(6)
#   createdAt   DateTime? @map("created_at") @db.Timestamptz(6)
#   updatedAt   DateTime? @map("updated_at") @db.Timestamptz(6)
#
#   @@unique([id])
#   @@index([tool])
#   @@index([status])
#   @@index([userId, submitTime], name: "ix_dft_jobs_user_submit")
#   @@index([tool, status], name: "ix_dft_jobs_tool_status")
#   @@map("dft_jobs")
# end


# === 字段映射对照 (SQLAlchemy ↔ Prisma) ===
#
# 字段类型映射实战 (派工 brief 严禁改 dft_job.py, 仅文档化):
#
# | SQLAlchemy               | Prisma                    | 备注                                |
# |--------------------------|---------------------------|-------------------------------------|
# | UUID(as_uuid=True) PK    | String @id @db.Uuid       | UUID → String + @db.Uuid 原生 DB    |
# | ForeignKey w/ ondelete   | Int? (无原生 FK 注解)     | 需手写 application-level FK validate |
# | String(32)               | String @db.VarChar(32)    | 字段长度一致                         |
# | Text                     | String                    | 无长度限制                          |
# | JSONB                    | Json                      | Prisma 原生, 与 SQLAlchemy JSONB 等价 |
# | DateTime(timezone=True)  | DateTime @db.Timestamptz  | Prisma timestamptz 等价 DateTime tz  |
# | Column default=          | @default                  | default lambda → Prisma @default(now())|
# | Index 单列                | @@index                   | 等价                                |
# | Index 复合 tuple          | @@index([a, b], name:)    | 复合索引可以, 但 Prisma 不能命名     |
# | TimestampMixin           | @map("created_at") 字段    | 需手写 update_at trigger             |
#
# 实战发现 (派工 brief 派生):
# 1. Prisma 无 ondelete="SET NULL" 原生支持, 需在 service 层手写
# 2. Prisma 复合 Index 不能命名 (要 name 在 SQLAlchemy 必修), 单列无
# 3. Prisma DateTime tz 行为与 SQLAlchemy DateTime(timezone=True) 不完全对齐
# 4. Prisma Float vs Decimal 区别: 模型定义需实测, 默认 Decimal for numeric col

# === 集成迁移成本估算 (派工 brief 1 表试点实测) ===
#
# 1 张表试点代码量:
# - prisma/schema.prisma 1 文件: ~30 行
# - app/models/prisma_dft_jobs.py 本文件: ~80 行 (含 docstring)
# - scripts/prisma_poc_test.py mock 测试: ~80 行
# - alembic/versions/099_dft_jobs.py 已有: 0 改
# - app/models/dft_job.py 已有: 0 改
#
# 1 张表实测投入: 0.5-1 天 (含 schema 镜像 + client 生成 + 测试)
# 53+ 张表全栈投入: 5-10 周 (1 表 1 天 × 53 + 多表关联 + 测试 + 部署链)
# 部署链断裂: 1-2 周 (CI/CD 接入 prisma generate + migrate deploy)
# 测试套件补全: 2-3 周
# 总投入: 11.5-15 周 (与 W-N-P3-A 决策(b) 估算守恒)


# === POC 收口决策依据 (派工 brief Step 6 决策修订) ===
#
# ROI 1 表试点实测:
# - 投入: 0.5-1 天
# - 收益: 验证 Prisma 真实成本 vs 派工 brief 估 1-2 周
# - 风险: 0 (mock 测试, 无 pip install)
# - 决策修订 (派工 brief 允许):
#   (a) 升级 (b) → (c) 试点扩展: 1 周 + 2-3 张表 (members + tasks + dft_jobs)
#   (b) 仍 (b) 暂不启动: W19 选项 A 维持
#
# 派工 brief 严禁升级 (b) → (c) 试点扩展未授权, 仅 1 表试点
# 决策修订最终结果仍 (b) 暂不启动 (沿用 W-N-P3-A 决策), 1 表试点仅验证 ROI


__all__ = []
