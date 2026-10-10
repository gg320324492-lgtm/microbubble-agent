# 工单 ZB-1：备份隐私隔离（`backups/` 目录复活 private）

> 签发：总指挥 · 2026-09-29 ｜ 优先级：**高（安全缺陷，用户已拍板方案）**
> 方案裁决（用户 2026-09-29 拍板）：**服务端给 `backups/` 目录复活 `visibility='private'`，不动客户端**
> 来源：ZB 恢复演练设计发现 ① · 战报 `docs/acceptance/2026-09-29-ZB-restore-drill.md`
> **本单是服务端工单**（改 `app/` + 新增 alembic 迁移），与 DL-7（桌面端）**不同轨、可并行，且不阻塞 v1.3.2 列车**

---

## 一、问题陈述（真实存在，非理论风险）

零感托管备份把**加密容器**和**解密钥匙 key.json**一起传到该用户自己的网盘 `backups/` 目录（`auto-provision.ts:14` `CLOUD_BACKUP_ROOT = 'backups'`，`cloud-backup.service.ts:123-131` 密钥与容器同目录同命名）。

服务端 2026-09「单一团队空间」改造后：

- `app/services/drive_service.py:499` —— `create_file()` 对**所有** drive 文件**硬置 `is_team_shared = True`**，入参忽略
- `app/services/drive_service.py:1993` —— `create_instant_upload()`（秒传路径）同款
- `app/api/v1/drive_files.py:505` —— 列表接口把 `is_team_shared_filter` **恒传 `None`**，personal/team 隔离**已完全退役**
- alembic `133_single_team_workspace.py` —— 存量全部回填 `is_team_shared = true`

**结论：容器虽 AES-256-GCM 加密，但钥匙就摆在旁边，且全组可见。任何登录成员拿到 key.json 即可解密他人备份容器。** ZB 的核心承诺是「笔记本报废也能救回」，这条链路目前对组内成员是敞开的。

---

## 二、总指挥已定案的技术路线（**不要另起炉灶**）

### 2.1 禁用 `is_team_shared`（重要，别走错路）

该字段**已是死字段**：写入恒 True、读取恒不过滤、存量已回填 true，代码注释自述「`is_team_shared` 服务端恒 True（该字段退役）」。用它做隔离属于复活一个语义废弃的字段，会给未来接手者埋坑。

> ⚠️ 桌面端 `cloud/transfer.ts:232` 的注释「`is_team_shared` 不传 → 服务端默认 false = 个人网盘视图（隐私语义所在），勿改」**是失效描述**——服务端随即覆盖为 True。上一窗口很可能即被此误导，才把本方案误述为「用 `is_team_shared` 隔离」。**本单可顺手修正该注释**，但**不得**改其上传行为。

### 2.2 复用 `visibility='private'`（读取侧权限逻辑仍完整活着）

- `drive_service.py:292-296` `visibility_see_cond`（private 仅 owner 可见）**仍在过滤链中**，注释明说「保留防脏数据兜底」——功能在，只是**没有新数据进来了**
- `drive_files.py:3320` 版本接口明确「走 `_can_see_file`，private 文件仅 owner 可看」，说明**下载侧存在对应鉴权闸**

**掐死 private 的只有一处**：`create_file:493-498` 那句「private 已退役，强制改写为 team」。所以本单真实成本是**给 `backups/` 开个洞让它保留 private**，而不是造一套新隔离机制。

**关键设计选择（总指挥定案）**：由**服务端依据目标文件夹路径**判定是否落在备份保留区，**不接受客户端传标志位**。理由：省掉客户端改动（本单可独立于任何桌面版本上线）、且不信任客户端自报的隐私属性。

---

## 三、执行要求

### Part A：备份保留区判定 + 豁免强制改写

1. 新增判定函数（建议 `drive_service.py` 内私有方法，或同模块纯函数 + 单测）：给定 `folder_id` → 该文件夹是否位于**备份保留区**（路径首段为 `backups`，大小写与前后空白归一）。保留区根常量请提取为具名常量并写明「与桌面端 `CLOUD_BACKUP_ROOT` 对齐」。
2. `create_file()`（第 492–499 行）：把「无条件 `is_team_shared = True` + private 强制改写 team」改为**条件豁免**——落在保留区时**保留 `visibility='private'`**；区外维持今天行为（一根手指都不许变）。
3. `create_instant_upload()`（第 1985–1993 行）：**同款**豁免，否则走秒传路径的文件会漏网。
4. 分块上传完成路径（`drive_chunked_uploads.py:137-141` → `create_file`）自然覆盖，但请**实测确认**一次，不要凭推断打勾。
5. 保留区的父文件夹若不存在，**本单不负责创建**（桌面端负责建），服务端只做判定。

### Part B：读取路径审计（**本单成立的前提，不许跳过**）

**必须逐条盘点并给出结论**：列出**所有**能取到 drive 文件内容或元数据的路径，逐一确认是否经过 private 闸（`_can_see_file` / `visibility_see_cond`）。至少覆盖：

- 文件下载 / 预览（`GET /files/{id}/download` 及任何直链、Range 请求）
- 分块上传的秒传命中（`create_instant_upload` 的 hash_lookup 分支）
- 版本历史 / 版本回滚（`drive_files.py:3312` `list_file_versions` 已自述走 `_can_see_file`）
- 回收站列表 / 彻底删除
- 搜索（语义检索与文件名 trgm 搜索）**是否会命中 private 行并泄露文件名/摘要**
- 收藏（`drive_file_stars`）跨用户可见性
- 任何 `share_token` / 分享链接路径
- 缩略图 / OCR 派生资源

**红线**：**任何一条读取路径若绕过 private 闸，本单不成立**——必须补齐过滤，而不是写进「已知问题」。报告中给出「路径清单 → 是否过闸 → 结论」的完整表格，缺一不可。

### Part C：存量回填（新增 alembic 迁移 `140_*`）

- `down_revision` **必须指向实际 head（当前为 `139_drop_wechat_fields`）——接单时自行确认，勿照抄本单**
- 作用：把**已存在的**、落在 `backups/` 保留区下的存量 drive 行 `visibility` 刷为 `private`（容器与 key.json 两类都要覆盖）
- **只动保留区内的行**；区外一行不碰
- `downgrade()` 必须可逆（把保留区内 `private` 行刷回 `team`），并在 docstring 写清影响面
- **注意**：迁移后这些文件在「团队共享盘」视图里会消失（符合预期），但**负责人本人是 owner，不受影响**

### Part D：部署与双账号实证

- ⚠️ **老坑**：`deploy-auto.sh` **不重启 Python 后端**——新迁移与新代码需**手动 `docker compose restart`**（+ 必要时 rebuild）才生效，报告须写明实际重启了哪些服务
- 实证（用 `cismoke` 演练账号，**用户真实数据零接触**）：
  1. 账号 A 在 `backups/` 上传一个测试容器 + key.json
  2. 账号 B 登录 → 网盘**列表看不到** A 的容器与 key.json；**直接用 A 的 file_id 调下载/预览接口 → 必须 404/403，不是 200**
  3. 账号 A 自己 → 可见可下载
  4. 区外普通上传文件 → 行为与今天完全一致（全组可见），确认零回归
- 迁移前后各跑一次，贴真实请求/响应

---

## 四、范围红线

- **不动** `is_team_shared` 的写入/读取语义（保持死字段现状，只改 `visibility`）
- **不动** `web/` 前端（web 端网盘视图若显示异常，报告说明，由总指挥裁决）
- **不动** 备份容器格式（`MNBBK1`）、不动零感备份的客户端逻辑（`apps/desktop/**` 本单零改动，注释修正除外）
- **不删** `cismoke` 账号（members id=1458，desktop-release 冒烟步依赖真实登录）
- **不改** MinIO 凭证（09-29 已轮换）、**不碰** `.env` 任何值
- 保留区之外的**所有** drive 行为逐字不变——区外任何行为变化都是回归，按退回处理
- 保护路径零改动：`alembic/` 以外的 `app/` 子模块无关文件、`.env`、`docker-compose*`、`nginx/`

---

## 五、验收证据（缺一退回）

1. **Part B 读取路径审计表**（路径 → 是否过闸 → 结论）——这是本单最重要的证据
2. **Part D 双账号实证**：A/B 双向请求响应贴证，含「区外文件仍全组可见」的零回归证据
3. 迁移 `up/down` 各跑一次的实际输出
4. 相关单测全绿（新增单测：保留区判定边界 —— 名为 `backups` / `backups2` / `BackupS` / 嵌套子目录 / 非保留区 五类）
5. 报告注明：实际重启的容器清单、迁移 revision 号、任何超出本单的发现（**发现不等于动手**，单列待裁决）

## 六、交付

- 提交链干净；报告贴出后**总指挥独立复核，不采信报告**
- 本单**不占用 v1.3.2 列车**——服务端改动独立生效，与桌面端版本解耦
- 完成后**必须更新** `docs/acceptance/2026-09-29-ZB-restore-drill.md` 的「发现 1」状态（由总指挥在验收时落笔）
