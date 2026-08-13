# JWT SECRET_KEY 管理 (2026-08-14, 类 20.155)

## 概述

`SECRET_KEY` 用于签发/验证所有 JWT (access_token + refresh_token), 单一密钥 + HS256 算法。**所有用户身份验证都依赖它**, 一旦丢失或错误配置, 整个系统认证崩溃。

## 当前持久化机制 (实测, 2026-08-13)

✅ **已 bind mount 持久化, 跨重启守恒**:

- `.env:5` 存放 88 字符 SECRET_KEY (e.g. `KFwPM5...aj2fw`)
- `docker-compose.yml:39-40` (app service) + `:267/321/350` (celery-worker / meeting-worker / beat) 都 `env_file: - .env`, 容器重建自动重新注入
- 仓库 `os.urandom / token_hex / token_urlsafe` 全文搜索 = **0 runtime 生成**, 无随机轮换
- `scripts/deploy.sh:74-76` + `scripts/deploy-local.sh:44-53` 仅在 `.env` 不存在时跑 `openssl rand -hex 32`, 已存在则跳过

✅ **结论**: 服务器关机/重建/`down && up` 不会让 SECRET_KEY 漂移, 类 20.155 沉淀中 "JWT secret 漂移" 假设不成立 (实测验证).

## 启动时验证 (2026-08-14 实施)

`app/main.py` lifespan 启动时打印:
```
[startup] SECRET_KEY sha256[0:8]=22506da4 length=86 app_env=development
```

`app/config.py` 的 `_validate_secret_key` validator:
- **production + 弱 key** (`""` / `"secret"` / `"your-secret-key"` / `"change-this-to-a-random-string"`) → `ValueError`, 启动失败
- **dev + 弱 key** → `warnings.warn`, 启动继续
- **length < 32 chars** (HS256 最低推荐) → `warnings.warn`
- **正常** → 静默通过

### 跨重启比对 (运维 SOP)

部署前:
```bash
# 记录当前 SECRET_KEY 指纹 (8 hex 字符)
docker exec microbubble-agent-app-1 python -c "
import hashlib
from app.config import settings
print(hashlib.sha256(settings.SECRET_KEY.encode()).hexdigest()[:8])
"
# 假设输出: 22506da4
```

部署后:
```bash
docker compose restart app
docker logs microbubble-agent-app-1 2>&1 | grep "SECRET_KEY"
# 期望: [startup] SECRET_KEY sha256[0:8]=22506da4 length=86 app_env=...
# 若不一致 → SECRET_KEY 已轮换, 所有旧 refresh_token 立即失效, 全员需重新登录
```

## 轮换流程 (人工, 无双 key verify)

⚠️ **当前版本 (2026-08-14) 不支持零停机轮换**. SECRET_KEY 一旦更换, 旧 token 全部立即失效, **所有用户被强制登出**.

### 轮换步骤

1. **通知用户**: 提前告知 "维护窗口, 期间需要重新登录"
2. **生成新 key**: `openssl rand -hex 32` (64 chars)
3. **改 .env**:
   ```bash
   # 备份旧 .env (虽然 .gitignore 不入仓, 但备份到 backups/)
   cp .env backups/env-pre-rotation-$(date +%Y%m%d).bak
   # 编辑 .env, 替换 SECRET_KEY 行
   ```
4. **重启所有依赖进程**:
   ```bash
   docker compose restart app celery-worker celery-meeting-worker celery-beat
   # 验证启动日志 fingerprint 变了
   docker logs microbubble-agent-app-1 2>&1 | grep "SECRET_KEY"
   ```
6. **触发全员登出**: 前端浏览器 localStorage 的旧 refresh_token 全部失效 → 用户访问时后端 401 → 前端跳 /login → 重新登录
7. **回滚 (如果出问题)**:
   ```bash
   cp backups/env-pre-rotation-YYYYMMDD.bak .env
   docker compose restart app celery-worker celery-meeting-worker celery-beat
   ```

## 未来改进 (留口, 不擅自扩)

- **零停机轮换**: 加 `SECRET_KEY_PREVIOUS` 字段, `decode_token` 改 try new-then-old (双 key verify). 未来 PR 实施.
- **自动轮换提醒**: 90 天未轮换启动时打 WARN (类 20 风格提示)
- **跨实例同步**: 多 app 实例共享同一 SECRET_KEY (`.env` 统一管理即可, 当前已 OK)

## .env 是非丢资产

- 必纳入 `backups/` 备份策略 (类似 backup_db.sh)
- `.gitignore` 已正确忽略 (line 15)
- `.env.backup-20260701-secret-rotation` 展示历史轮换痕迹 (不要删, 用于审计)

## 关联

- [CLAUDE.md 类 20.155](../CLAUDE.md) (本规则永久铁律)
- `app/main.py` lifespan 启动日志 (line 204-227)
- `app/config.py` `_validate_secret_key` validator (line 308-330)
- `memory/server-shutdown-refresh-429-loop-2026-08-13.md` (本次事件溯源)
- `scripts/backup_db.sh` (提醒 SECRET_KEY 轮换影响)