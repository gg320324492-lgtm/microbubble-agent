# 工单 ZB-2：堵死备份隐私漏洞（真实形态接保留区 + 备份形态跳过知识库抽取）

> 签发：总指挥 · 2026-09-29 ｜ 优先级：**最高（安全）· 随 v1.3.2 列车一起发**
> 用户裁决 2026-09-29：① 堆进 v1.3.2，组员装 v1.3.2 时漏洞已堵上 ② 备份形态**跳过抽取**，不再产生 kb 孪生行 ③ ZB-1 遗留物（zb1probe 账号 / backups/ 文件夹 / 3 个探针）**全部保留**作复验基座
> 前序：ZB-1（`40b4b9883` + 迁移 140）代码**保留**，是本单地基，不是白做
> **本单同时动桌面端与服务端**，两者缺一则漏洞照旧

---

## 一、为什么必须有本单（ZB-1 验收实证）

ZB-1 把 `backups/` 目录复活了 private，但**生产中根本不存在这个目录**。总指挥直查库实证：

```
id 2829–2844  workbench-*.mnbbak / *.key.json  folder_id=NULL  visibility=team
```

**16 个真实备份产物全部在根目录、team 可见**——ZB-1 一条都没保护到。

---

## 二、两条根因（总指挥已在源码级定位，执行端不必重找）

### 根因 A · 桌面端丢弃目录信息

`apps/desktop/src/main/ipc.ts:1834-1845`：

```ts
uploadFile: async (remotePath, bytes) => {
  const parts = remotePath.split('/')
  const name = parts.pop() ?? 'backup.mnbbak'   // ← 目录段被丢弃
  const r = await remoteDrive.upload({
    filename: name,          // ← 只传文件名
    fileSize: bytes.length,
    readChunk: async (offset, length) => bytes.subarray(offset, offset + length)
    // ← 没有 parentId
  })
```

对比同文件 **1144 行的普通文件上传**：`remoteDrive.upload({ ..., parentId })` —— **先例就在眼前，照抄即可**。

结果：`backups/<user>/x.mnbbak` → 服务端收到无 `folder_id` 的请求 → 落根目录 + team。

### 根因 B · 服务端把备份抽进了知识库，并主动放宽可见性

触发链：
1. `drive_service.py:591-593` —— `create_file` 成功后 `index_drive_content_task.delay(...)`
2. → `app/services/drive_ingest_tasks.py:47` —— `DriveToKBService(db).ingest_drive_file(...)`
3. → `app/services/drive_to_kb_service.py:394-403` —— 建 `storage_mode='kb'` / `source_type='drive_extracted'` 孪生行，**复用同一 MinIO 对象**

**最恶劣的一行**（`drive_to_kb_service.py:393`）：

```python
visibility = row.visibility if row.visibility != "private" else "team"
```

**drive 行是 private 时，孪生行被显式翻成 team。** 抽取动作本身在放大可见性。这条影响**所有** private 文件，不止备份。

总指挥查库实证的后果：

```
id 2843/2844  kb  folder_id=NULL  team  content=166 字符（密钥信封）
knowledge_chunks 里有 5 条对应 chunk → 已进向量索引，可被语义检索命中
```

**严重性倒挂**：容器本体是 AES-256-GCM 加密的，但**钥匙躺在一行全组可见、全文可检索、已向量化的明文里**。

---

## 三、执行要求

### Part A · 桌面端：保留目录信息并落到 `backups/` 文件夹

1. `ipc.ts:1834-1845` `uploadFile`：拆出 `remotePath` 的**目录段**（`backups/<user>`），find-or-create 对应文件夹，取其 `folder_id` 传为 `parentId`。**行为参照 1144 行既有上传**，不要另造通道。
2. find-or-create 的查找手段参照同文件 **1846-1848 行 `listRemote`**（已在用 `remoteDrive.list`）。**不得**硬编码 folder id。
3. 目录段解析必须防路径穿越（`..`、绝对路径、空段），与 `backup.service.ts:202` 既有防穿越口径一致。
4. `listRemote`（1846）同步按目录段查找，否则保留策略 `applyRetention` 找不到目录导致清理失效——**这是同一个 bug 的另一半，别只改一半**。
5. 桌面端**不改**备份容器格式（`MNBBK1`）、不改 `remoteDir` 的既有构造（`auto-provision.ts` 的 `CLOUD_BACKUP_ROOT='backups'`）。

### Part B · 服务端：备份形态跳过知识库抽取 + 堵住 private→team 翻转

1. **跳过抽取**：在**入队前**判定文件名后缀为 `.mnbbak` / `.key.json`（建议提为具名常量集合 + 纯函数，附单测）时，**不触发** drive→kb 入库。
   - 判定点二选一并说明理由：`drive_service.py:591` 的 `index_drive_content_task` 入队前，或 `drive_ingest_tasks.py` 任务入口。**必须早于建孪生行**——「先跑后删」不算数。
   - 跳过必须**留日志**（哪个 file_id、为什么跳过），否则以后无从追溯。
2. **堵 `drive_to_kb_service.py:393`**：`private → team` 的翻转**必须去掉**。孪生行应继承源行 visibility。
   - 这条影响**所有** private 文件，不止备份。改动前**先查清有没有别处依赖这个翻转**（例如 web 端入库后可见性被人为上调过），有依赖则在报告中单列。
3. 若你判断第 2 条风险超出本单范围，**可以只做第 1 条**，但必须在报告中明确写「`private→team` 翻转未修，private 文件经手动 extract 仍会变 team」并停手等裁决——**不许默默跳过**。

### Part C · 迁移 141（回填存量 + 清除已泄露的密钥明文）

`down_revision` = **140**（接单时自行确认 head）。

1. **drive 行回填**：`storage_mode='drive'` 且落在备份形态（根目录存量，folder_id IS NULL 或位于 backups 子树）→ `visibility='private'`。
2. **kb 孪生行清除（安全强制项）**：存量 `source_type='drive_extracted'` 且对应备份形态的 kb 行，**含 `content` 里的密钥明文**——按用户裁决「跳过抽取」，这些行**应当删除**，并同步清理 `knowledge_chunks` 关联行（否则向量索引里仍留着密钥片段）。
   - **删除前必须先输出完整清单**（id / file_name / created_by / content 长度）交总指挥过目，再执行。
   - **只删备份形态的 kb 行**，其他 `drive_extracted` 条目（真实文档入库）**一根手指都不许碰**。
   - `downgrade()` 语义：能恢复到「行还在」即可（明文内容无法还原），docstring 写明这一点。
3. 迁移前后各跑一次，贴真实输出。

### Part D · 部署与双账号复验

- ⚠️ `deploy-auto.sh` **不重启 Python 后端**——必须手动 `docker compose restart`（app / celery-worker / celery-meeting-worker / celery-beat），报告写明实际重启清单。
- **复验基座保留**（用户裁决）：`zb1probe` 账号 1459、`backups/` 文件夹、cismoke 3 个探针文件**都不许删**。
- 实证（真实 HTTP，cismoke=A、zb1probe=B）：
  1. A 在真实上传路径（新代码）产生一份备份 → 断言落进 `backups/` 文件夹、drive 行为 `private`
  2. B 对该容器/key：列表不可见、搜索不可见、直连 file_id 下载 **404/403**
  3. **B 的语义检索搜不到密钥信封内容**（这条是本单的核心验收点，ZB-1 漏的就是它）
  4. **全库断言**：`SELECT count(*) FROM knowledge WHERE source_type='drive_extracted' AND file_name LIKE '%.key.json%'` = **0**
  5. `knowledge_chunks` 中无备份形态密钥 chunk
  6. 存量 2829–2844 复验：迁移后 B 不可见/不可下
  7. **零回归**：区外普通文件 B 照常可见可下

---

## 四、范围红线

- **不动** ZB-1 已落地的 11 处 private 写路径闸与保留区判定（地基，只加不改）
- **不动** 备份容器格式 `MNBBK1`、不动零感备份的自动配置与触发逻辑
- **不动** `web/` 前端
- **不删** `zb1probe` 账号、`backups/` 文件夹、3 个探针文件（用户明确保留）
- **不删** `cismoke`（id=1458，desktop-release 冒烟步依赖真实登录）
- 区外所有 drive/kb 行为**逐字不变**；区外任何行为变化都算回归，按退回处理
- Part C 的 kb 行删除**必须先出清单过总指挥目**，不得跳过
- 不碰 `.env`、MinIO 凭证（09-29 已轮换）、`nginx/`、`docker-compose*`

---

## 五、验收证据（缺一退回）

1. **Part C 删除前清单** + 删除后 count=0 的 SQL 输出
2. **Part D 全部 7 条实证**（尤其第 3、4、5 条——语义检索与全库断言）
3. 容器内测试全绿（新增用例：跳过抽取判定、private 继承、迁移 up/down）
4. 回归：drive 测试族 + drive_to_kb 测试族全绿，**特别确认「private 文件手动 extract 后仍 private」**这条新语义
5. 报告注明：实际重启容器清单、迁移 revision、`private→team` 翻转是否已修、若未修则明确标注为已知未完成项

## 六、交付

- 提交链干净；报告贴出后**总指挥独立复核，不采信报告**
- 本单完成后走 **v1.3.2 列车**（CHANGELOG 追加一段「备份隐私加固」，发布时定稿）
- 验收通过后由总指挥回填 `docs/acceptance/2026-09-29-ZB-restore-drill.md` 的「发现 1」状态
