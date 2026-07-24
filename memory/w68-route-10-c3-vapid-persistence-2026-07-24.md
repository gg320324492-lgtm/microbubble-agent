# W68 第 10 批 C-3: VAPID 持久化脚本 + 部署必做 (锚点范式第 130 守恒)

**日期**: 2026-07-24
**任务**: W68 第 10 批 C-3 (主指挥拍板 0 production code 改动铁律例外, 仅新功能)
**锚点范式**: 第 130 守恒
**0 production code 改动铁律**: 维持 (push_service 增强 = 新功能 PWA push 系列, 不算破坏老路径)

---

## 1. 背景

### 1.1 触发点

W68 第 7 批 B-3 (PWA Push Backend) 已实施 (commit `b31386d61`), 但**没做**
部署必做的 VAPID 持久化机制. W68 第 9 批 D-1 调研报告 P0 高优先级:

- VAPID 密钥启动时生成, 默认存 `/data/push/vapid_*.pem`
- **没做**: 部署必做目录创建 + docker volume mount + 持久化脚本
- **后果**: 每次 `docker compose restart app`, VAPID 重新生成
  → 旧 subscription 全部失效 → 用户需手动重新订阅 (浏览器弹"允许通知" → UX 灾难)

### 1.2 关键发现 (主指挥协调)

W68 第 7 批 B-3 设计文档 (commit `b31386d61`) 包含 VAPID 持久化代码
(`_generate_and_save` + atomic write tmp/rename), 但**部署文档**仅写"mkdir"
一行命令, **没有** docker volume mount 提示 + 一键脚本 + 备份策略 + 回滚文档.

主指挥判定: **P0 高优先级, 部署前必做**. 即使代码逻辑已正确, 部署链路缺一环
就会触发旧订阅失效事故.

---

## 2. 实施内容 (4 文件)

### 2.1 新建 `scripts/setup_vapid_persistence.sh` (~290 行)

**职责** (5 步):
1. 创建 `/data/push/` 持久化目录 (主机 + 容器两侧)
2. 检查是否已有 VAPID 密钥 (`vapid_private.pem` + `vapid_public.pem`)
3. 如有: 提示 "已存在, 跳过" + 输出公钥 (对账用)
4. 如无: 触发 `docker compose restart app` → lifespan init 生成 + 持久化
5. 输出公钥 base64url (浏览器 subscribe 用)

**关键设计**:
- **默认 dry-run** (打印命令不真跑), 加 `--apply` 才真改
- **支持 4 模式**: `--apply` (真跑) / `--dry-run` (默认) / `--reset` (强制重生) / `--check` (仅检查)
- **永远不自动重启 app** — 主指挥拍板, 避免部署窗口期连动
- **失败 fail-loud** — exit 1 + log 详细原因
- **跨平台** — Linux (云 server) + Windows Git Bash (本地 PC dry-run)
- **彩色输出** — ANSI 颜色 (无 TTY 自动禁用)

**关键代码段**:
```bash
# 原子写 (tmp → rename), 防半写状态被读到
priv_tmp = VAPID_KEY_FILE + ".tmp"
with open(priv_tmp, "wb") as f: f.write(priv_pem)
os.replace(priv_tmp, VAPID_KEY_FILE)  # Linux rename / Windows MoveFileEx
```

### 2.2 改 `app/services/push_service.py` (+~50 行)

**W68 第 7 批 B-3 已有逻辑** (不动):
- `_generate_and_save()` + atomic write (tmp + rename) ✓ 已有
- `_load_from_files()` + `_generate_in_memory()` fallback ✓ 已有
- 环境变量覆盖 (`PUSH_VAPID_KEY_FILE` / `_PUBLIC_KEY_FILE`) ✓ 已有

**本批增强**:
- **加 `app.config import settings`** (走 Pydantic settings, 不再纯 os.environ.get)
- **加 `PUSH_VAPID_DIR` setting** (默认 `/data/push`, `.env` 可覆盖)
- **`VAPID_DIR` 改从 settings 读**, 兼容老环境变量覆盖
- **`_generate_and_save` 加详细 log**:
  - `PermissionError` 走明确 raise (不是静默 fallback)
  - 写 tmp 失败清理 `.tmp` 残留 (防下次启动误用半写文件)
  - 加 `self.source = "file" / "memory"` 字段 (诊断用)
- **公开密钥走 settings** + 文件路径在 `VAPID_DIR` 下 (统一管理)

**关键设计**:
- 不破坏老路径 (环境变量 `PUSH_VAPID_KEY_FILE` 仍可单独 override 单文件)
- 兼容旧部署 (环境变量缺失走默认)
- atomic write 已强化 (tmp 失败清理 + 详细 log)

### 2.3 改 `app/config.py` (+~10 行)

**新增 setting**:
```python
# W68 第 10 批 C-3: PWA 浏览器推送 VAPID 密钥持久化目录
PUSH_VAPID_DIR: str = "/data/push"
```

**为什么必须加 settings 字段**:
- 跨 `.env` / docker-compose.yml / K8s ConfigMap 一致性
- 避免 push_service.py 与文档分散配置
- 便于单元测试 mock (settings.PUSH_VAPID_DIR = "/tmp/test-push")

### 2.4 新建 `docs/push-vapid-persistence-deploy.md` (~270 行)

**8 节内容**:
1. 背景与风险 (P0 高, 部署前必做)
2. 部署必做 (docker volume mount + 跑脚本)
3. 验证 (公钥不变 + 旧订阅仍能收推送 + 文件存在)
4. 备份策略 (季度 cron + 异地容灾 + 恢复)
5. 回滚策略 (软回滚 / 硬回滚 / 紧急关闭推送)
6. 监控与告警 (健康检查端点 + 日志监控 + 失败率告警)
7. 已知问题与限制 (重启丢失 / 密钥轮换 / 备份泄漏风险)
8. 跨文档引用 + 修改历史

**关键决策**:
- docker volume mount **必须** `/data/push:/data/push:rw` (而非 bind mount)
- 公钥验证 = 2 次 curl 必返相同值 (持久化生效判定)
- 旧订阅者验证 = 测试推送 delivered=1 (VAPID 私钥未变判定)

---

## 3. 5 条新铁律

### 铁律 1: VAPID 密钥必须持久化 (P0 高)

- **原因**: 启动时生成, 默认存 `/data/push/vapid_*.pem`
- **后果 (不持久化)**: 每次 `docker compose restart app` → 公/私钥全变
  → 旧 subscription 401/403 → 用户需重新订阅 (UX 灾难)
- **部署必做**:
  ```bash
  # docker-compose.yml app service 加 volume
  volumes:
    - /data/push:/data/push:rw
  # 跑一键脚本
  bash scripts/setup_vapid_persistence.sh --apply
  ```
- **验证**: 重启后 `curl /api/v1/push/vapid-public-key` 应返**相同公钥**

### 铁律 2: 原子写 tmp → rename 防半写

- **原因**: VAPID 私钥写盘过程崩溃 → 读到半写状态 → 下次启动加载失败
- **正模式** (push_service.py `_generate_and_save`):
  ```python
  priv_tmp = VAPID_KEY_FILE + ".tmp"
  with open(priv_tmp, "wb") as f: f.write(priv_pem)
  os.replace(priv_tmp, VAPID_KEY_FILE)  # 原子操作
  ```
- **反模式**: 直接 `open(VAPID_KEY_FILE, "wb")` 写 (崩溃留半写)
- **纪律**:
  ① `os.replace` 是原子操作 (Linux `rename` / Windows `MoveFileEx`)
  ② 写 tmp 失败必须清理 `.tmp` 残留 (防下次启动误用)
  ③ tmp 路径必须与目标路径**同一文件系统** (rename 失败 = cross-device)

### 铁律 3: docker volume mount 部署必做

- **原因**: 容器内 fs 临时, 重启清空 → 必须挂主机持久化路径
- **正模式** (docker-compose.yml):
  ```yaml
  services:
    app:
      volumes:
        - /data/push:/data/push:rw  # VAPID 持久化 (W68 第 10 批 C-3)
  ```
- **反模式**:
  ```yaml
  # ❌ bind mount 到 git 仓库 (Windows 路径冲突 + 误提交风险)
  - ./data/push:/data/push:rw
  # ❌ 匿名 volume (重启丢, 主机看不到)
  - /data/push
  ```
- **验证**: `docker inspect <container> | grep Mounts` 期望 destination=`/data/push`
- **纪律**: setup 脚本 `check_volume_mount` 主动探测, 不挂即告警

### 铁律 4: 持久化目录必须走 settings (不硬编码)

- **原因**: 路径分散 → 文档/代码/脚本不一致 → 部署事故
- **正模式** (app/config.py):
  ```python
  PUSH_VAPID_DIR: str = "/data/push"  # 默认, .env 可覆盖
  ```
- **push_service.py 读 settings**:
  ```python
  VAPID_DIR = getattr(settings, "PUSH_VAPID_DIR", None) or os.environ.get(
      "PUSH_VAPID_DIR", _VAPID_DIR_DEFAULT,
  )
  VAPID_KEY_FILE = os.path.join(VAPID_DIR, "vapid_private.pem")
  ```
- **纪律**:
  ① push_service.py **不要**硬编码 `/data/push` 字符串 (走 settings)
  ② 兼容老环境变量 `PUSH_VAPID_KEY_FILE` (override 单文件)
  ③ settings 字段命名 = `PUSH_VAPID_DIR` (与 `.env` key 一致)

### 铁律 5: 季度备份 + 异地容灾 (VAPID 等同密码)

- **原因**: `/data/push/vapid_private.pem` 泄漏 = 攻击者可冒充服务端推送给所有用户
- **备份策略**:
  ```bash
  # /etc/cron.weekly/backup-vapid.sh
  BACKUP_DIR="/backup/vapid-$(date +%Y%m%d)"
  mkdir -p "$BACKUP_DIR"
  cp -r /data/push "$BACKUP_DIR"
  # 保留最近 4 季度
  find /backup -maxdepth 1 -name "vapid-*" -mtime +120 -exec rm -rf {} \;
  ```
- **纪律**:
  ① 备份目录权限 **700** (root:root), `chmod 600 vapid_private.pem`
  ② 异地备份用**专用 SSH 密钥** (不用 root 主密钥)
  ③ 月度审计 `/backup/vapid-*` 权限 + 大小
  ④ 备份恢复前必须先 `docker compose stop app` (避免读写竞争)

---

## 4. 0 production code 改动铁律维持

**本批例外**: push_service.py 增强 = **新功能 PWA push 系列**, 不算破坏老路径
(W68 第 7 批 B-3 已建立). push_service.py 改动集中在 VAPID 持久化强化 + 走
settings, **不动**已有推送逻辑 (`subscribe` / `push_to_user` / `push_to_topic`).

**未改动**:
- `app/api/v1/push_notifications.py` (5 REST endpoints) — 0 改动
- `app/models/push_subscription.py` (3 表 ORM) — 0 改动
- `alembic/versions/065_push_subscriptions.py` — 0 改动
- `notification_service.py` (push_with_priority 双通道) — 0 改动
- `web/src/composables/useMobilePushNotification.ts` — 0 改动
- `web/src/components/MobilePushPermissionDialog.vue` — 0 改动

**改动 (新功能)**:
- `app/services/push_service.py` (+~50 行, 强化 VAPID 持久化 + 走 settings)
- `app/config.py` (+10 行, 加 `PUSH_VAPID_DIR` setting)

**新建 (scripts + docs)**:
- `scripts/setup_vapid_persistence.sh` (~290 行)
- `docs/push-vapid-persistence-deploy.md` (~270 行)

---

## 5. 验证清单

### 5.1 bash syntax
- [x] `bash -n scripts/setup_vapid_persistence.sh` 0 错误
- [x] dry-run 模式跑通 (Windows Git Bash)
- [x] `--help` 输出完整用法
- [x] `--check` 仅检查状态

### 5.2 typing imports CI
- [x] `bash scripts/check_typing_imports.sh app/services` → "扫描了 90 个文件, ✅ 所有 typing 注解的 import 都齐全"
- [x] `python -c "import ast; ast.parse(open('app/services/push_service.py', encoding='utf-8').read())"` 0 错误
- [x] `python -c "import ast; ast.parse(open('app/config.py', encoding='utf-8').read())"` 0 错误

### 5.3 部署链路验证 (主指挥 SSH 跑)
- [ ] `bash scripts/setup_vapid_persistence.sh --apply` 创建 `/data/push/`
- [ ] `docker compose restart app` 触发生成 + 持久化
- [ ] `curl /api/v1/push/vapid-public-key` 返相同公钥 (重启前后)
- [ ] 测试推送 `delivered=1` (旧订阅者仍能收)
- [ ] `cp -r /data/push /backup/vapid-$(date +%Y%m%d)` 季度备份就绪

### 5.4 跨文档一致性
- [x] `docs/push-vapid-persistence-deploy.md` 第 7 节引用 `scripts/setup_vapid_persistence.sh` + `app/services/push_service.py` + `app/config.py`
- [x] 与 `docs/mobile-pwa-push-backend.md` 第 2 节互补 (本批 doc 是专门持久化深度, 原 doc 是 PWA push 全栈)
- [x] MEMORY.md 索引待主指挥合并后补 (本批不在合并范围)

---

## 6. 后续 PR (W69+)

| PR | 内容 | 优先级 |
|----|------|--------|
| W69 | VAPID 密钥轮换 (迁移期双私钥接受) | P1 中 |
| W69 | push_service 单元测试 (`test_push_service_persistence.py`, 5 场景) | P1 中 |
| W69 | `purge_stale_subscriptions` 推到 Celery beat (90 天清理) | P2 低 |
| W70 | push_to_topic admin 权限控制 (防滥用广播) | P2 低 |

---

## 7. commit 信息 (待主指挥合并)

```
chore(w68-10th-batch-c3): VAPID 持久化脚本 + 部署必做 (锚点范式第 130 守恒)

- scripts/setup_vapid_persistence.sh (~290 行, 默认 dry-run, --apply 真跑)
- docs/push-vapid-persistence-deploy.md (~270 行, 8 节: 背景/部署/验证/备份/回滚/监控)
- app/services/push_service.py (~50 行增强, VAPID_DIR 走 settings + atomic write 强化)
- app/config.py (+10 行, PUSH_VAPID_DIR setting)

0 production code 改动铁律维持 (push_service 增强 = 新功能 PWA push 系列)
5 新铁律: 持久化 / atomic write / docker volume / settings / 季度备份

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

## 8. 跨周期引用

- W68 第 7 批 B-3 PWA Push Backend commit `b31386d61` (源)
- W68 第 9 批 D-1 调研报告 P0 高优先级 (触发点)
- W68 第 10 批 A-1/A-2 主指挥合并 (待 commit 编号)
- `docs/mobile-pwa-push-backend.md` (原 PWA Push Backend 部署 doc)
- `memory/w68-route-9-d1-8-smallfixes-2026-07-24.md` (D-1 调研报告)