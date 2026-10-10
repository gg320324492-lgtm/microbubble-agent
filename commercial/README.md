# `commercial/` — 商业化功能代码

> **目录边界（结构重构批次 6，2026-10-10 补）**：本目录是**商业化业务代码**
> （SaaS 多租户 + 私有化部署）。它与主仓 `app/` **零 import 是刻意设计**，
> 见下方「为什么零 import」。

## 内容清单

```
commercial/
├─ saas-platform/          # SaaS 部署脚本 (CLI / usage / audit / billing gateway / deploy)
│   ├─ billing_gateway.py
│   ├─ tenant_manager.py
│   ├─ usage_tracker.py
│   ├─ audit_export.py
│   ├─ deploy.py
│   └─ deploy.sh
└─ private-deployment/     # 私有化部署
    ├─ private_config.py
    └─ billing_degrade.py
```

两个子目录名里都带连字符（`saas-platform` / `private-deployment`），
**不是合法 Python 包名**，进一步说明它们本来就不是被 `import` 的模块。

---

## 为什么零 import 是刻意设计，不是漏接线

全仓 `app/` 侧对 `commercial` 的引用共 7 处，**全部是字符串路径 / 注释 / 表名常量**，
没有一处是真 `import`：

| 位置 | 引用内容 | 性质 |
|---|---|---|
| `app/api/v1/billing.py:24` | `APIRouter(prefix="/commercial/billing")` | URL 路径字符串 |
| `app/api/v1/tenants.py:23` | `APIRouter(prefix="/commercial/tenants")` | URL 路径字符串 |
| `app/middleware/license_middleware.py:50` | `"/api/v1/commercial"` | 路径白名单字符串 |
| `app/middleware/tenant_middleware.py:28-29` | `"/commercial/billing/plans"` 等 | 路径白名单字符串 |
| `app/models/billing.py:26` | `__tablename__ = "commercial_plans"` | 表名常量 |
| `app/models/billing.py:10` | 注释「与 commercial/saas-platform 协同」 | 注释 |

**路径前缀与 SQL 表名共享 `commercial` 这个词，不代表代码依赖。**
路由和 ORM 模型已经在 `app/` 内自洽实现，本目录承载的是**交付形态**
（部署脚本 / 打包入口 / 商务侧工具），走的是 `python -m` / shell 调用而非包导入。

验证零 import：

```bash
grep -rn "import commercial\|from commercial" app/ --include="*.py"   # 期望无输出
```

---

## ⚠️ 不要试图"接线"或"搬移"

1. **不要接线** —— 把这里的模块 import 进 `app/`，等于把"可独立交付的部署脚本"
   变成应用运行时依赖。SaaS 与私有化是**互斥的交付形态**，不是要同时加载的两条路径。
2. **不要搬移** —— 从顶层移到 `app/` 下，对结构**没有任何改善**：
   它只是**把一个没人引用的目录换了个地方**，只增加 diff 成本和将来 grep 时的困惑。
   设计原则第 4 条明确"**不制造'为了分类而分类'**"。

真正让结构变乱的不是"目录名不够整齐"，而是**没人知道这些目录为什么在那、职责是什么、
能不能动**。这份 README 就是那个"边界可被验证"的产出。

---

## 意图路由权重去哪找

若你是在找**意图路由权重**，不在本目录，也不在配置文件里：

- **权威位置**：[`app/rag/intent_router.py`](../app/rag/intent_router.py) 的
  `DEFAULT_INTENT_WEIGHTS`（module-level dict，定义在第 42 行附近）
- 原 `config/intent_routing.yaml` 已于 **2026-10-10 作为死配置删除**，
  权重改为从 module-level dict 读取（类 20.126：不硬编码，从 `DEFAULT_INTENT_WEIGHTS` 查）

别再去 `config/` 找那个 yaml，它已经不存在了。
