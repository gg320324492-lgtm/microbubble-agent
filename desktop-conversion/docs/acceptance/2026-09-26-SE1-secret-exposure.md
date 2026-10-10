# 安全事件 SE-1：公开仓库暴露生产凭据（2026-09-26）

## 等级与状态

**P0 → 已止血，待轮换。** 仓库为 Public，`.env` 被 git 追踪推送（.gitignore 第 15 行早有 `.env` 条目，但文件先于规则被 track——gitignore 不追溯已追踪文件）。

## 暴露面（git 历史中现存）

| 文件 | 暴露凭据 | 影响 |
| --- | --- | --- |
| `.env` | SECRET_KEY（86 位）/ POSTGRES_PASSWORD / CLAUDE_API_KEY + MIMO_API_KEY（LLM 网关）/ LANGFUSE 4 键 | 生产系统直接凭据 |
| `.env.production.example` | **STRIPE_LIVE_SECRET_KEY / STRIPE_LIVE_PUBLISHABLE_KEY / 支付宝应用私钥（PEM）/ 微信支付商户私钥（PEM）** | 文件名带 example 实装真钥——**资金级风险** |

## 已执行（总指挥直接操作）

1. `git rm --cached .env`（解除追踪；本地文件保留，生产系统零影响）
2. `.env.production.example` 真实值全部净化为占位符（复扫 0 残留）
3. 提交推送 `040050bae`；`.gitignore` 无需改（第 15 行已有 `.env`）

## 必办轮换清单（用户执行，按风险排序）

| 序 | 凭据 | 轮换位置 | 后续 |
| --- | --- | --- | --- |
| 1 | **Stripe 生产密钥** | Stripe Dashboard → Developers → API Keys → Roll | 新钥更新服务器 .env + 重启计费相关服务 |
| 2 | **支付宝应用私钥** | 支付宝开放平台 → 重新生成密钥对/上传公钥 | 同上 |
| 3 | **微信支付商户私钥** | 微信商户平台 → API 证书重新申请 | 同上 |
| 4 | **POSTGRES_PASSWORD** | 改 .env → `docker compose up -d db` 重建（短暂停机） | 同步改 DATABASE_URL |
| 5 | **LLM 网关密钥（CLAUDE_API_KEY/MIMO_API_KEY）** | 密钥提供方控制台 | 同步更新服务器 .env 与桌面端设置页 ⚠️ 含此前拍板不轮换的网关钥——**本次为公开暴露，性质不同**，请重新评估 |
| 6 | **SECRET_KEY** | 生成强随机替换 → 全员会话失效 | 应用重启 |
| 7 | LANGFUSE 4 键 | Langfuse 设置页 | 低风险，随缘 |

## 可选加固

- **仓库转 Private**（最快掐断历史内容的访问；README 写明私有项目但仓库是 Public——矛盾点；桌面更新走 OSS 不受影响）
- git 历史清洗（git filter-repo + force push）——轮换完成后属锦上添花，非必需
- gitleaks 规则补 `.env` 类文件全量扫描（此前规则只匹配特定 key 前缀，tp- 网关钥与数据库密码漏网）

## 教训

「example 命名 ≠ 安全」——真钥装进 example 文件反而绕过直觉审查；`.gitignore` 有规则 ≠ 未追踪。盘点式清理的价值正在于此。

## 轮换执行记录（2026-09-26，总指挥直接执行）

| 项 | 结果 |
| --- | --- |
| SECRET_KEY | ✅ 已轮换（新 86 位随机，值不落对话；容器重建生效）|
| POSTGRES_PASSWORD | ✅ 已轮换（ALTER ROLE → 新密码登录验证 ✓ → 旧密码验证失效 ✗ → 全栈 15 容器重建全 healthy；postgres 5432 未对公网发布，暴露风险本就受限）|
| Stripe sk_live | ✅ **关闭**——Stripe API 实测判定 Invalid（key 无效），用户「没用过」印象被官方证实，无需轮换 |
| 支付宝/微信支付配置 | ✅ 已整体移除（用户裁决：本项目不涉及商业支付；原值为残缺桩/占位符从未生效）|
| LLM 网关密钥（CLAUDE/MIMO） | ⏳ **用户侧待办**——须在密钥提供方控制台轮换（总指挥无权限），新钥更新服务器 .env 与桌面端设置页 |
| Langfuse 4 键 | ⏳ 低风险，用户随缘 |

**轮换后验证**：生产 health 200 / 本地 API 200 / OSS 链路 200 / 全栈 15 容器 healthy。
**影响提示**：SECRET_KEY 轮换使既有会话与云端令牌失效——桌面端与网页端需重新登录一次（预期行为）。
**备份**：`.env.backup-pre-rotation-20260926`（含旧密钥，gitignore 覆盖内）——确认全系统稳定后可删。
