# 验收记录 · ZB-1 备份隐私隔离 —— **执行通过 / 安全目标未达成（漏洞仍敞开）**

> 验收：总指挥 · 2026-09-29
> 结论拆两半：**代码交付质量通过**；**本单要解决的安全目标未达成**，且**工单前提被证伪**
> 执行端报告：`docs/acceptance/2026-09-29-ZB1-exec-report.md`（commit `d9ffbde`）｜代码 `40b4b9883`

## 一、总指挥独立复核（不采信报告）

| 复核项 | 方法 | 结果 |
|---|---|---|
| diff 范围 | `git diff --stat 8c09434b2 40b4b9883` | 5 文件：`app/api/v1/drive_files.py`、`app/services/drive_service.py`、`alembic/versions/140_*`、`tests/`、桌面端 `transfer.ts`（**仅注释**）。`web/` `nginx/` `docker-compose*` `.env` 零触碰 ✓ |
| **11 处写路径闸的回归风险** | 读 `_can_see_file`（`drive_service.py:460-469`） | `非 owner → return file.visibility != "private"`。迁移 133 后**现存全部行是 team/public**，故这 11 处闸对既有数据**结构性恒真 no-op**。零回归是结构保证，不靠测试撞运气 ✓ |
| 身份参数正确性 | 追 `create_version` / `restore_version` 调用点 | 均传 `uploader_id=user.id`（`drive_versions.py:111`、`drive_files.py:3353`），即**当前登录用户**，非误传 → 闸真实生效 ✓ |
| 保留区判定 | 读 `is_backup_reserved_root_name` + `_is_backup_reserved_folder` | 整名相等（`backups2` 不误判）、大小写/空白归一、parent 链上溯带 16 层防环 ✓ |
| 测试基线 | **本人容器内复跑** `pytest tests/test_zb1_backup_privacy.py` | **23 passed**（88s）。首次复跑失败系我方环境（`SKIP_DB_SETUP=1` 跳过建表 / 变量名应为 `TEST_DATABASE_URL`），修正后复现，与报告一致 ✓ |
| 迁移 140 | 直查 DB | head=140，保留区行 private；区外 team 零变化 ✓ |

## 二、⚠️ 关键发现 1（执行端已报，总指挥查库坐实）：**本单保护了 0 个真实备份**

直接查库（`knowledge` 表）：

```
id 2829–2844  workbench-*.mnbbak / *.key.json  folder_id=NULL  visibility=team  created_by=1458
```

- **16 个真实 ZB 演练产物全部在根目录、`team` 可见** —— 修复上线后依然全组可见可下
- `backups` 文件夹（id=1541）**是验收驱动自己建的**，真实客户端从未建过
- 根因：桌面端 `uploadFile` 把 `backups/<user>/x.mnbbak` **拆出文件名后丢弃目录信息**，不带 `folder_id` → 服务端落根目录
- 结论：**`backups/` 保留区规则接不住任何真实数据形态**。工单的前提（备份落在 `backups/` 目录）不成立

## 三、⚠️ 关键发现 2（**执行端未报，总指挥独立查出**）：`kb` 镜像行泄露面比原漏洞更重

每个 drive 上传都会派生**第二条 `knowledge` 行**：

```
2841  drive  folder=NULL  team   ← ZB-1 保留区规则只管这一行
2843  kb     folder=NULL  team   ← drive_extracted 抽取副本，管不到
```

- `kb` 行 `source_type='drive_extracted'`，`folder_id=NULL`、`visibility=team` —— **全组可见**
- 机制源头：`create_file` 内 WP2（2026-09-02）「drive 内容索引 —— 解析原文→分块→embedding 入 `knowledge_chunks`」
- **对 `.key.json` 同样做了抽取**：5 条 kb 行各含 166 字符的密钥信封内容（`~ 'cipher|secret|password|key'` 命中）
- **已进入语义检索**：`knowledge_chunks` 里有 **5 条**对应 chunk，即这些内容**可被 RAG 语义搜索命中**
- **严重性倒挂**：容器本体是 AES-256-GCM 加密的，但**它的钥匙躺在一条全组可见、全文可检索、已向量化的明文行里**。即使把 drive 行刷成 private，kb 孪生行仍是 team

## 四、缓解事实（决定优先级，不改变严重性）

- 受影响行 `created_by=1458` = `cismoke`（演练账号），**无任何真实用户备份处于暴露中**，当前无实际泄露
- 但零感托管备份即将随 v1.3.2 分发给组员 —— **必须在分发前堵上**

## 五、验收结论

| 维度 | 结论 |
|---|---|
| 代码交付质量 | **通过**。最小改动、结构性零回归、23/23 复现、透明度诚实（发现 1 主动上报未擅动） |
| 工单前提 | **证伪**。`backups/` 目录在生产中不存在 |
| 安全目标 | **未达成**。本单未堵上任何真实暴露面，且暴露出执行端未察觉的第二条泄露面 |

**ZB-1 不可按「已完成」结项。** 需用户拍板后续路径（见下），已另立工单跟进。
本单已落地的成果（11 处 private 写路径闸 + 保留区判定 + 迁移 140）**予以保留**，它们是新方案的必要地基，不是白做。

## 六、给后续方案的硬约束

1. 桌面端与服务端**必须同时改**：只改一端，保留区规则照样接不住
2. **必须一并处理 `kb` 镜像行**，否则堵了 drive 漏了孪生，等于没堵
3. 迁移需覆盖**根目录存量**（drive 行 2829–2844 + kb 行 11 条）
4. 建议方向：备份形态（`.mnbbak` / `.key.json`）**本就不该进知识库抽取链路**——加密容器无法被检索，抽取既无功能价值又是泄露源；跳过它同时解决安全与冗余

## 七、遗留物（执行端报备，待裁决）

cismoke 名下 3 个 private 探针（2845/2846/2849）+ `backups/`、`zb1-open` 文件夹 + `zb1probe` 账号（1459）。
其中 **`zb1probe` 账号与 `backups/` 文件夹是 ZB-1 的验证基座**，在漏洞真正堵上前建议保留以便复验。
