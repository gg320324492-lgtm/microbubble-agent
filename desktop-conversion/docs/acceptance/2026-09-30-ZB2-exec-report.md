# ZB-2 执行报告：堵死备份隐私漏洞(真实形态接保留区 + 备份形态跳过抽取)(2026-09-29/30)

## 结论

双端交付,漏洞闭环:桌面端备份上传不再丢弃目录信息(落 `backups/<user>/` 保留区);服务端备份形态**在任务入口跳过**知识库抽取与内容索引(密钥明文不再进 kb 行/chunks/向量索引);`private→team` 翻转**已修**(孪生继承源行);迁移 141 清除存量 kb 孪生 11 行 + chunks 11 条(含密钥明文)并把根目录存量备份行刷 private。**容器测试 8/8 新增 + 回归 62/62;桌面 gate 781/781;Part D 七条实证全过(含语义检索零泄露、全库 SQL 断言 0/0)。**

- commit:**`d357ad4b7`**(双端主交付)+ **`5e5d5d391`**(迁移 141 downgrade 修列);均已推 origin(首次 push 网络瞬断已补推)
- 迁移 revision:`141_zb2_backup_kb_purge`(down=`140_backup_reserved_private`),终态 current=141 head

## Part A:桌面端保留目录信息(apps/desktop/src/main/ipc.ts)

- `uploadFile`:解析 `remotePath` 目录段 → **find-or-create** 文件夹链(`listFolders(parent)` 精确匹配名 → `createFolder(name, parent)`,不硬编码 id)→ `remoteDrive.upload({..., parentId })`(与 1144 行普通上传同款;transfer.ts JSON/multipart 双通道均将 parentId 传为 `folder_id`,走查确认)
- 防穿越:目录段与文件名段内禁止 `\`、`..` 且非空(与 backup.service.ts `deleteLocalBackup` 同口径);空段跳过
- `listRemote`:按目录段 **resolve(只查不建)** → 文件夹内按名查;目录未建返回空 entries——`applyRetention` 语义正确(无可清理项)
- `deleteRemote`:同口径,保留区文件夹内精确删除(旧实现全局 keyword 搜有误删同名风险,一并修——同一 bug 的另一半)
- 备份容器格式 MNBBK1、`CLOUD_BACKUP_ROOT='backups'`、自动配置与触发逻辑零改动

## Part B:服务端跳过抽取 + 堵翻转

1. **跳过抽取(早于建孪生行)**:具名常量 `BACKUP_ARTIFACT_SUFFIXES = ('.mnbbak', '.key.json')` + 纯函数 `is_backup_artifact_name`(大小写不敏感后缀),在**两个异步任务入口**判定:
   - `auto_ingest_drive_file_task`(kb 孪生;覆盖 upload/chunked/version 三个入队点+未来调用方)→ 跳过并留日志(file_id+file_name+原因),返回 `{skipped: 'backup-artifact'}`
   - `index_drive_content_task`(drive 行 chunk/embedding——**key.json 的 chunk 会把密钥信封明文写进 knowledge_chunks**,这条不在工单原文但属同一泄露面)→ 同款跳过留日志
   - 选任务入口而非入队前的理由:任务入口是唯一汇聚点(3 个入队点全覆盖),对未来新调用方天然免疫
2. **private→team 翻转已修**:`_create_kb_row` 去掉翻转,孪生行继承源行 visibility。依赖排查:KB 读取侧(knowledge_service/hybrid_retriever/chunk 层)对非 team/public 硬过滤,private 孪生仅 owner 相关,无既有依赖;手动 extract 路径不经此行(目标 visibility 显式,语义=用户主动公开,不受影响)。**未采用"只做跳过"的降级选项**

## Part C:迁移 141(删除前清单已交总指挥过目)

- 删除前清单:`assets/2026-09-29-ZB2/partc-pre-delete-list.txt` —— **11 行**(2831/2832/2834/2836/2838/2840/2843/2844/2847/2848/2850,全 created_by=1458、全 team,content 52–166 字符),抽样实证 content 为密钥信封明文(`"key": "4wVnOR1zqx..."`);关联 `knowledge_chunks` **11 条**一并清除
- 只删 `source_type='drive_extracted'` 且备份形态的行;其他 drive_extracted 零触碰
- 归档表 `knowledge_zb2_removed_kb_rows` 记录 id/file_name/created_by/visibility(**不含 content 与 chunks**——密钥明文必须从库里消失,归档保留即违背目的)
- up 输出:`Running upgrade 140→141`;删后断言 kb 行=0、chunks=0
- down/up 双跑(实测):down 恢复占位行(首跑报 `created_at` NotNullViolation,TimestampMixin 无 server_default,补 `now()` 后通过——`5e5d5d391`);up 重新清除(kb_rows=0, archived=11),终态 current=141

## Part D:部署与七条实证(真实 HTTP,A=cismoke 1458 / B=zb1probe 1459)

**重启容器清单**:app / celery-worker / celery-meeting-worker / celery-beat(手动,docker compose restart;清 `__pycache__`;health 200;worker ping pong ✓)。

| # | 验证项 | 结果 |
|---|--------|------|
| 1 | A 走真实上传路径(folder_id=backups/,不传 visibility) | ✅ 201,`visibility: "private"`(服务端保留区强制;v1.3.2 桌面端将自动带 folder_id,服务端行为已就绪) |
| 2 | B 对新备份:列表/搜索不可见、直连下载 | ✅ 搜索 0 命中、下载 404 |
| 3 | **B 语义检索搜不到密钥** | ✅ 真实密钥片段查 → 命中 5 条全为无关普通文档;备份关键词查 → 同;RAG QA 问钥匙内容无泄露;**A(owner)查也 0 命中**(chunks 物理删除,非隐藏) |
| 4 | 全库 `drive_extracted AND *.key.json` 计数 | ✅ SQL = **0** |
| 5 | knowledge_chunks 备份形态密钥 chunk | ✅ SQL = **0** |
| 6 | 存量 2829–2844 | ✅ B 搜索 0 命中、key(2842)下载 404;迁移已刷 private(2841/2842 等实测) |
| 7 | 区外零回归 | ✅ 普通文件 team、B 可见(1)+可下(200) |

证据存档:`assets/2026-09-29-ZB2/`(partd-seven-checks.json / partd-semantic-check.json / partc-pre-delete-list.txt / 驱动脚本)。

## 测试与回归

- 新增 `tests/test_zb2_backup_ingest_skip.py` **8/8**:判定矩阵(形态/大小写/空白/近似名/空)、ingest 入口跳过(容器+key 两形态,断言不建孪生行)、private 继承、team 不变
- 回归 **62/62**:`drive_to_kb_e2e`(真抽取管线,证明跳过未伤正常入库)+ zb1(23)+ drive_service + drive_search + zb2
- 桌面:pnpm gate **781/781** + typecheck 0
- 「private 文件自动入库后孪生仍 private」新语义已由专测覆盖;手动 extract 保持显式公开语义不变(区分说明)

## 范围红线自查

ZB-1 的 11 处 private 写路径闸与保留区判定零改动;MNBBK1/自动配置/触发逻辑零改动;web/ 零改动;zb1probe、backups/ 文件夹、3 个探针文件全部保留;cismoke 未动;区外行为逐字不变;未新增依赖;未碰 .env/MinIO 凭证/nginx/docker-compose。

## 待总指挥

1. 独立复核(不采信报告)
2. v1.3.2 列车:CHANGELOG 追加「备份隐私加固」段(建议措辞:备份容器与钥匙改存私有目录、不再进入知识库与向量索引、历史已泄露密钥行已清除并更换——**提示:历史 key.json 明文已被读取过的话,轮换备份密钥属运维决策,不在本单**)
3. 演练战报「发现 1」状态回填
