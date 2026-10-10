# FIN-1 执行报告:发布前收尾(双端遗留项一次收干净)(2026-09-30)

## 结论

A 组 2 项(高/中风险)+ B 组 4 项 + C 组 2 项全部完成;D 组(不修项)**确认知悉,未动手**。桌面 gate **782/782**(基线 781 + B2 用例,≥781 达标);服务端容器测试 **41/41 安全族零额外 env 全绿**(zb1 23 + zb2 8 自洽化 + fin1 10)+ 回归 **82/82**(按 e2e 文件自身文档化条件)。

- 父仓库 commit:**`a513a97c5`**(服务端 A1/A2/C1 + 测试)+ **`09b224ea5`**(桌面 B1-B4/C2),均已推 origin

## A 组

### A1 · 备份形态禁止公开分享(四路径同口径)

拦截点全部复用 `drive_ingest_tasks.is_backup_artifact_name`(未另写判定);**仅文件名形态判定**,理由:迁移 141 后根目录残留形态已全 private,形态判定覆盖面最稳(保留区内外同名形态一视同仁);判定为文件名形态命中即拦,不看位置。

| 路径 | 拦截 | 用户可见性 |
|---|---|---|
| `create_share_link` | owner 也在内一律拒 | `DriveServiceError 400` → API 转错误信封(实测见下) |
| `update_visibility` → public | owner 也在内拒 | 400 `detail` 明文 |
| `update_file(visibility='public')` | owner 也在内拒(该路径可设 public,与上同漏洞面,单列说明) | 400(该方法既有风格即抛错) |
| `batch_update_visibility` → public | 备份形态静默入 skipped(批量语义) | 批量返回 skipped 列表 |

「分享即公开」(2026-09-05)对**非备份文件逐字不变**(专测:普通 team 文件分享照旧 200 + 翻 public)。拦截后文件 visibility 保持 private、不产生 share_token。

**双账号实证**(`a1-share-block-http.json`,真实 HTTP):owner 对自己 key.json(id 2846)分享 → **400** `备份文件不支持公开分享 (内容含备份密钥, 恢复请使用桌面端零感备份通道)`;update_visibility→public → **400**;update_file→public → **400**;对照普通 team 文件分享 → **200 + token**(已撤销)。

**超出工单点名两处的说明**:工单点名 create_share_link + update_visibility;update_file(visibility 参数)与 batch_update_visibility 是**同一漏洞面的另外两条用户可达通道**(owner 把备份翻 public),按 A1 拦截目标一并覆盖,未新增语义。

### A2 · 异步任务测试不连生产库

- `drive_ingest_tasks`:新增模块级 `_database_url_override`(生产恒 None → `settings.DATABASE_URL`,**行为逐字不变**)+ `_resolve_engine_url()`;任务引擎改用之
- `drive_index_service` 同类问题确认:**有**(task 经 `create_celery_engine_and_session()` 同样硬编码)→ 同款 `_index_db_url_override` 注入(None 走既有 celery_db 通道)
- **守卫测试 ×4**:`test_guard_injected_test_url_is_not_production`(注入后解析 URL ≠ 生产库,含 asyncpg 形态)、`test_guard_default_is_settings_url_documented`(默认= settings,契约固化)、`test_guard_conftest_test_url_differs_from_production`(conftest 测试 URL ≠ 生产)、`test_guard_index_service_override_attr`
- `test_zb2_backup_ingest_skip.py` **自洽化**:`_run_ingest_task_selfcontained()` 注入测试库后内联执行,零额外 env 全绿(实测)

**根因追加发现(已修)**:总指挥的「补 DATABASE_URL 指向测试库」还有更深一层——`tests/conftest.py` 的测试库默认 URL **硬编码旧密码 `microbubble2026`**,09-29 密钥轮换后已失效,这才是历次必须外部注入 env 的根因。修法:默认 URL 改为**从 `settings.DATABASE_URL` 派生**(只借凭据与主机,库名换 `microbubble_test`;轮换后的密码不含该子串,替换无歧义)——不连生产库(守卫测试断言),不硬编码凭据进公共仓库。conftest 铁律注释同步更新(「禁止回退」精化为「禁止连接生产库」;守卫双保险)。

## B 组

- **B1**:节流跳过日志改 `${Math.round(AUTO_CHECK_THROTTLE_MS / 3600000)}h` 引用常量(现输出 20h),文案永不再漂移
- **B2**:`releaseNotesLines`/`buildLatestYml` 入口归一——尾随 **2+** 换行 → 单个;**仅含换行视为空**(字段整体省略,空块标量无法表达);JSDoc 写明契约。测试固化 6 形态(总指挥实测的 4 个有损案例全部转绿)+ 往返断言
- **B3**:`normalizeBackupSegments` 拒单点 `.`(文件名段与目录段都拒)
- **B4**:`ensureRemoteFolderId` 在 `listFolders !ok` 时**显式返回失败**并向上传播到 `uploadFile`(备份以可感知失败结束,不再静默重复建夹);`ensureRemoteFolderPath` 失败链路同步重构

## C 组

- **C1**:`_validate_visibility_inherits` docstring 以代码实际行为为准重写(VISIBILITY_ORDER 严格比较;team 文件夹放 public 会被拒并计入 skipped),**行为零改动**
- **C2**:CHANGELOG v1.3.2 新增「备份隐私加固」段(私有目录/目录信息保留/不入知识库/可见性继承修正/公开分享拒绝/历史明文清除),措辞如实并注明「不声称覆盖产品其他面的安全问题」

## D 组确认知悉(未动手)

第六节各项(密钥轮换/自动清理/共享链接审计等)均未触碰。其中**备份密钥轮换不需要**已确认知悉:受影响 22 行全部 created_by=1458(cismoke 演练账号),真实组员从未产生过备份,明文已被迁移 141 物理删除。

## 验收对照

| 工单要求 | 状态 |
|---|---|
| A1 双账号实证(owner 拒 / 普通照旧) | ✅ `assets/2026-09-30-FIN1/a1-share-block-http.json` |
| A2 守卫测试 + zb2 零额外 env 全绿 | ✅ 41/41(未设任何 -e) |
| 桌面 gate ≥781 | ✅ **782/782** + typecheck 0 |
| 服务端 ZB-1/ZB-2 回归不破 | ✅ 41/41(含 zb1 联动更新)+ 82/82(按 e2e 文档化条件) |
| 每项改前/改后对照 + D 知悉 | ✅ 本报告各节 |

**联动更新说明(非回归)**:`test_zb1_backup_privacy.py` 中「owner 分享自己备份仍可用」断言按 FIN-1 A1 的新语义更新为「owner 也被拒且文件不翻 public」——正是本单要堵的洞,非测试破坏。

## 已知环境事实(单列,未动手)

`test_drive_to_kb_e2e.py` 自带硬编码 `localhost:5433`(docstring 明写「本地, 测试栈 DB localhost:5433」跑法),容器内直跑需 `TEST_DATABASE_URL` env——**属 A2 同类问题的第三实例**,但该文件把本地跑法文档化为设计意图,未在本单改;建议后续统一走 conftest 派生。

## 交付

- 父仓库:`a513a97c5`(服务端)+ `09b224ea5`(桌面端),已推 origin
- 指挥部:本报告 + `assets/2026-09-30-FIN1/`
- 总指挥独立复跑 gate 与服务端测试后 → R-12 v1.3.2 发布列车
