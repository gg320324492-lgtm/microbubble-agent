# ZB-1 执行报告：备份隐私隔离——backups/ 保留区复活 private(2026-09-29)

## 结论

按定案路线交付:服务端依**目标文件夹路径**判定备份保留区(不信任客户端),保留区内强制 `visibility='private'`;读取/写路径审计完成,**4 条绕过面补齐**(写路径扁平化时删掉的门禁,仅对 private 形态恢复);迁移 `140_backup_reserved_private` up/down 双跑实证;双账号(cismoke=1458 / zb1probe=1459)HTTP 实证全过,区外零回归。**容器测试库 23/23 新增用例 + 回归 49/49 全绿。**

- 服务端 commit:**`40b4b9883`**(app + 迁移 + 测试,post-commit hook 已推 origin)
- **⚠️ 单列待裁决(重要)**:当前真实漏洞形态未被本单封死,见「五、待裁决」

## 一、Part A:保留区判定 + 豁免

- `BACKUP_RESERVED_ROOT_NAME = 'backups'`(具名常量,注明与桌面端 `auto-provision.ts CLOUD_BACKUP_ROOT` 对齐)
- 纯函数 `is_backup_reserved_root_name`(strip+lower 归一,**整名相等**不做前缀匹配)+ `DriveService._is_backup_reserved_folder`(parent 链上溯到根,深度上限 16 防环)
- `create_file`:保留区内**强制 private**(客户端传 team/private 均不影响——桌面端备份上传本就不传 visibility,实测 `transfer.ts` 未带该字段);区外「private 退役改写 team + is_team_shared 恒 True」逐字保留
- `create_instant_upload`:同款豁免(秒传路径不漏网)
- chunked complete:`complete_chunked_upload` L2681 复用 `self.create_file`(代码走查确认),同一收口点自动覆盖;另有专测以 create_file 为被测对象佐证
- 保留区父文件夹不存在时服务端**不创建**(工单 5),实测中由驱动按桌面端未来行为以 API 建(`POST /folders name='backups'`)

## 二、Part B:读取/操作路径审计表(本单核心证据)

闸 = `_can_see_file`(private 仅 owner)/ `visibility_see_cond`(SQL 同义)/ 版本服务内联同义检查。

| # | 路径 | 服务入口 | 是否过闸 | 结论 |
|---|------|---------|---------|------|
| 1 | 文件列表 `GET /drive/files`(含搜索分支) | `list_files→_list_files_impl` | ✅ `visibility_see_cond` 在过滤链 | 过闸 |
| 2 | 文件详情 `GET /files/{id}` | `get_file` | ✅ 非 owner private → None(连文件名都不展示) | 过闸 |
| 3 | 下载/直链/Range `GET /files/{id}/download` | 端点 L1226 先 `svc.get_file` | ✅ | 过闸 |
| 4 | 批量下载 `POST /files/batch-download` | 逐文件 `get_file`(L1366) | ✅ | 过闸 |
| 5 | 预览 `GET /files/{id}/preview` | L3712 `get_file` | ✅ | 过闸 |
| 6 | 缩略图 `GET /files/{id}/thumbnail` | L3536 `get_file` | ✅ | 过闸 |
| 7 | pptx 逐页 ×2 | L1717/L1775 `get_file` | ✅ | 过闸 |
| 8 | docx 逐页+pdf ×3 | L1848/L1904/L1924 `get_file` | ✅ | 过闸 |
| 9 | pdf 逐页 ×2 | L1974/L2030 `get_file` | ✅ | 过闸 |
| 10 | xlsx 预览 | L2150 `get_file` | ✅ | 过闸 |
| 11 | zip 列表 | L2269 `get_file` | ✅ | 过闸 |
| 12 | csv 预览 | L2415 `get_file` | ✅ | 过闸 |
| 13 | pptx 结构 | L2485 `get_file` | ✅ | 过闸 |
| 14 | 文件锁 POST/DELETE/GET | L708/L767/L803 `get_file` | ✅ | 过闸 |
| 15 | 秒传 hash_lookup | 命中行 `_can_see_file` | ✅ | 过闸 |
| 16 | 版本列表/版本下载 | `list_versions` L2134 `_can_see_file`;`drive_version_service` 列表 403/下载 403(内联同义) | ✅ | 过闸 |
| 17 | 回收站列表 | `list_trash→_list_files_impl`(docstring 自述仅 `visibility_see_cond`) | ✅ | 过闸 |
| 18 | 搜索(文件名 ILIKE/trgm) | `list_files` search 分支 → 同 impl 同闸 | ✅ 不泄露文件名/摘要 | 过闸 |
| 19 | 语义检索/RAG/知识图谱 | `knowledge_service` 多处硬过滤 `storage_mode='kb' AND visibility IN(team,public)`;chunk 层 `visibility!='private' OR created_by=me`;drive 行不入 embedding 索引 | ✅ private 备份行不可达 | 过闸 |
| 20 | 收藏列表 | `list_starred→_list_files_impl` | ✅ | 过闸 |
| 21 | 通知(评论/提及携带附件时) | notifications L328 `_can_see_file` | ✅ | 过闸 |
| 22 | mobile-feed | `list_files` | ✅ | 过闸 |
| 23 | 协同文档 WS(drive_collab) | `check_file_owner_or_folder_admin` 规则含「任何在册成员」= 恒真 | ⚠️ 形态无关(见单列 3) | 观察项 |
| — | **以下为写/操作路径(审计发现原无闸,ZB-1 补齐)** | | | |
| 24 | `PUT /files/{id}`(改名/移动/**改 visibility**) | `update_file` | ❌→✅ **补闸**(非 owner private → None) | 已补齐 |
| 25 | 软删 `DELETE /files/{id}` | `soft_delete_file` | ❌→✅ **补闸**(False) | 已补齐 |
| 26 | 恢复 `POST /files/{id}/restore` | `restore_file` | ❌→✅ **补闸** | 已补齐 |
| 27 | extract-to-kb(公开发布到知识库) | `extract_to_kb` | ❌→✅ **补闸** | 已补齐 |
| 28 | 分享链接创建(「分享即公开」翻转 visibility=public) | `create_share_link` | ❌→✅ **补闸**(非 owner None) | 已补齐 |
| 29 | 收藏/取消(触发对 owner 的通知回显) | `toggle_star_file` | ❌→✅ **补闸** | 已补齐 |
| 30 | `PUT /files/{id}/visibility`(翻公开) | `update_visibility` | ❌→✅ **补闸** | 已补齐 |
| 31 | 新版本注入 / 版本恢复 | `create_version`/`restore_version` | ❌→✅ **补闸(404)** | 已补齐 |
| 32 | 批量软删/恢复/移动/改可见性 | batch ×4 | ❌→✅ **补闸(private 非 owner 静默入 skipped)** | 已补齐 |
| 33 | 彻底删除 单/批 | `permanent_delete(_batch)` | ❌→✅ **补闸**(回收站列表本就隐身,直连 id 也隐身) | 已补齐 |
| 34 | 「分享中」清单 `GET /shares/active`(**返回 token**) | 端点内联 SQL | ❌→✅ **补闸**(`or_(created_by=me, visibility!=private)`) | 已补齐 |
| 35 | 分块上传 init/chunk/status/complete | 会话按 `user_id` 绑定;complete 走 `create_file` | ✅(+Part A 豁免) | 过闸 |
| 36 | 存储统计/配额 | 按 `created_by=user` 聚合 | ✅ | 过闸 |

**审计结论:全部路径过闸或已补齐,无「已知问题」遗留。** 补闸语义统一为「private 行对非 owner = 隐身」(与 get_file 一致);因 private 行只存在于保留区(133 已清零存量 + 本单后仅保留区产生),**区外 team/public 行为逐字不变**(回归 49/49 含扁平化断言佐证)。

## 三、Part C:迁移 140

- `140_backup_reserved_private`,`down_revision='139_drop_wechat_fields'`(容器 `alembic heads` 实测确认)
- 递归 CTE 圈保留区子树(顶层名归一='backups' 的根 + 全部存活后代)→ 区内 `storage_mode='drive'` 行(含软删)刷 private;**区外一行不碰**
- `downgrade()`:区内 private 刷回 team;局限(无法区分本迁移刷成的 private 与假设的存量 private,后者当前库不存在)已写 docstring
- up/down 实际输出:见「四、4」

## 四、Part D:部署与双账号实证(全部真实 HTTP,本地栈 :8000)

**部署**:代码 bind-mount(`./app:/app/app`)→ 清 `__pycache__` → `docker compose restart app celery-worker celery-meeting-worker celery-beat`;worker `inspect ping` pong ✓。**实际重启容器清单:app / celery-worker / celery-meeting-worker / celery-beat(deploy-auto.sh 不重启 Python,手动执行)**。

**迁移前后对照(driver 真实请求/响应,存档 `assets/2026-09-29-ZB1/`)**:

1. **迁移前(漏洞在证)**:B(zb1probe,1459,由 cismoke 经 `POST /members` 创建)对 A(cismoke,1458)的:
   - 真实演练 key.json(id=2842)**直接下载 = 200**;搜索 `workbench-20260929` 命中 **8 行**
   - 规范探针(backups/ 内,`zb1-probe-pre.mnbbak`+`.key.json`,id 2845/2846):搜索可见 ×2、下载 **200 ×2**
2. **迁移 up**(`139→140`,实际输出已存档):2845/2846 → private;**2841/2842(根目录)仍 team**(见待裁决)
3. **迁移后(旧代码未重启即验,纯迁移效果)**:B → 2845 **404**、2846 **404**;A → 2845 **200**
4. **部署后(新代码)**:
   - A 上传新容器到 backups/**不传 visibility** → 响应 `visibility: "private"`(**服务端强制生效**)
   - B:搜索 `zb1-` **零命中**;新文件下载 **404**;旧探针下载 **404 ×2**
   - A:新/旧下载 **200 ×2**
5. **down/up 可逆**:`downgrade -1`(实际输出存档)→ 2845/2846 翻回 team,B 重见 + key 下载 **200**;再 `upgrade head` → private 恢复,终态 `current = 140_backup_reserved_private (head)`
6. **区外零回归**:A 上传普通 csv 到区外文件夹 → `visibility: "team"`,B 搜索可见 + 下载 **200**

## 五、待裁决(发现,未动手)

1. **【关键】当前真实备份形态不在保留区判定范围内,漏洞对既有备份仍敞开**:实测桌面端 `uploadFile`(ipc.ts L1834)把 `backups/<user>/x.mnbbak` **拆出文件名后丢弃目录信息**,`remoteDrive.upload` 不传 folder_id → 服务端落**根目录**、folder_id=NULL。ZB 演练产物(id 2841/2842,created_by=1458)即此形态,迁移后仍 team(见四.2),B 仍可见可下。两个修法都触碰本单红线,请总指挥裁决:
   - **建议 a(推荐)**:桌面端 `uploadFile` 补 ensure `backups/` 文件夹 + 传 `folder_id`(一行级改动,碰 apps/desktop 红线);同时建议迁移 141 把「根目录 `*.mnbbak`/`*.key.json` 且 created_by=备份使用者」的存量行刷 private
   - 建议 b:服务端补「根目录 + 备份文件名形态」判定——违背「不信任客户端命名」精神,不推荐
2. **owner 对自己 private 备份创建分享链接**:沿用既有「分享即公开」语义(翻 visibility=public),会把备份暴露全组。建议后续禁用保留区文件的分享入口(本单未动,属产品行为变更)
3. **drive_collab 协同闸恒真**:`check_file_owner_or_folder_admin` 规则含「任何在册成员」,协同文档不设 private 防线;但备份容器/key.json 不会是协同文档,形态无交集。建议另开小单收敛
4. `_validate_visibility_inherits` docstring(「folder=team → 文件可以是 private/team/public」)与代码(`VISIBILITY_ORDER` 禁止 team 文件夹放 public,实测 batch_update_visibility 跳过)矛盾——陈旧文档,建议另行修正

## 六、测试与验收清单

- 新增 `tests/test_zb1_backup_privacy.py` **23 用例全绿**(容器测试库,单实例,双 TEST_DB env):保留区五类边界/嵌套豁免/根+子目录/key.json 形态/秒传豁免/chunked 收口/区外 private 退役零回归/private 十余写路径闸(非 owner 隐身+owner 正常)/区外 team 对 B 可见可下
- 回归:`test_single_team_workspace` + `test_drive_service` + `trash_chunk_e2e` + `ownership` + `folder_restore` **49/49 全绿**(「任何成员可删/改 team 文件」的扁平化语义不受影响)
- `cismoke` 未删未改密(仅作为 A 登录+建 B+上传探针);用户真实数据零接触(探针全部为自造内容,归 cismoke 名下 private)
- 遗留物:cismoke 名下 3 个 private 探针文件(2845/2846/2849)+ backups/、zb1-open 文件夹 + zb1probe 账号(1459)——均为审计痕迹,保留待总指挥裁决是否清理

## 七、交付

- 父仓库:`40b4b9883`(app/services/drive_service.py、app/api/v1/drive_files.py、alembic 140、tests、transfer.ts 注释更正)
- 指挥部:本报告 + 证据 `assets/2026-09-29-ZB1/`(驱动脚本 + pre/post/downgrade-check 三份结果 JSON + probe-ids)
- 演练战报「发现 1」状态:按工单由总指挥验收时落笔
