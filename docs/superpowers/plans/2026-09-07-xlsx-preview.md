# XLSX 预览窗口（网盘右栏详情卡）实现计划 — 方案 D「横幅 + 前 8 行速览」

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 网盘右栏详情卡的 `.xlsx` 文件从「XLSX 无预览图」占位升级为真数据速览：深青横幅头（图标+统计）+ 工作表标签 + 表头 + 前 8 行单元格表格，全屏可滚动查看缓存全量行（≤200）。

**架构：** 后端照抄 `pptx-pages`/`docx-pages` 管线模式——`GET /api/v1/drive/files/{id}/xlsx-preview` 状态机端点（converting → ready/error），worker 线程用 openpyxl `read_only` 抽每表前 200 行 × 前 6 列写 `ready.json` 缓存，端点按 `max_rows` 切片返回。前端 `DriveDetailRail.vue` 新增 `excel` previewKind 分支，一次拉 `max_rows=200` 缓存，常态渲染切片、全屏渲染全量，零二次请求。

**技术栈：** FastAPI + openpyxl 3.1.2（已有）/ Vue 3 `<script setup>` + axios（已有），无新依赖。

**规格：** `docs/superpowers/specs/2026-09-07-xlsx-preview-design.md`（含四版选型原型 `docs/superpowers/mockups/2026-09-07-xlsx-preview-4ui.html`）

**关键既有代码位置（先读再改）：**
- `app/api/v1/drive_files.py:1543-1671` — pptx-pages 段（锁/worker/状态端点/页图端点全套模式，新代码紧随其后）
- `app/api/v1/drive_files.py:1817-1917` — pdf-pages 段（**新代码插在这段之后、`# === 批次⑩.17` 注释之前**）
- `web/src/components/drive/DriveDetailRail.vue:530-541` — `previewKind` computed
- `web/src/components/drive/DriveDetailRail.vue:543-555` — `stageHeight`
- `web/src/components/drive/DriveDetailRail.vue:860-876` — docx 轮询 watch 模式（前端轮询照抄此模式）
- `web/src/components/drive/DriveDetailRail.vue:234-239` — docx/pdf 分支结束 → 兜底占位（excel 分支插中间）

**本仓库纪律（CLAUDE.md）：**
- 改 `web/src/` 后必须 `cd web && npm run build` 并 `git add -f web/dist/` 提交，否则线上仍是旧版
- `deploy-auto.sh` 不重启 Python 后端——新端点上线需手动 `docker compose restart app`
- 测试跑法：`docker compose exec -T app pytest tests/test_xlsx_preview.py -v`（app 容器内 DB 主机名 `db` 可解析；本地直跑需 `TEST_DATABASE_URL` 指向可达库）

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `app/api/v1/drive_files.py` | 修改 | 新增 XLSX 预览段：常量 + `_xlsx_cache_key` / `_xlsx_cache_dir` / `_clip_cell` / `_xlsx_preview_worker` / `_slice_xlsx_sheets` + 端点 `get_xlsx_preview_status` |
| `tests/test_xlsx_preview.py` | 创建 | worker 解析规则（截断/裁剪/上限）、切片、端点状态机（400/缓存命中/error/key 轮换） |
| `web/src/components/drive/DriveDetailRail.vue` | 修改 | `excel` previewKind + 舞台高度 + coverUrl 跳过 + 模板分支 + 轮询状态 + `rf-xlsx-*` scoped 样式 |
| `web/dist/**` | 构建产物 | `npm run build` 后强制提交（仓库规则） |

后端 helper 全部模块级纯函数（缓存根目录 `_XLSX_PREVIEW_ROOT` 为模块全局，测试 monkeypatch 它），不新建 service 文件——`drive_files.py` 内 `*-pages` 各段均为同构自包含段，跟随现有模式。

---

### 任务 1：后端 — 解析 worker + 切片纯函数（TDD）

**文件：**
- 修改：`app/api/v1/drive_files.py`（在 pdf-pages 段之后插入，约 line 1917）
- 测试：`tests/test_xlsx_preview.py`（新建）

- [ ] **步骤 1.1：写失败的测试**

创建 `tests/test_xlsx_preview.py`：

```python
"""XLSX 预览 (2026-09-07 选型 D) — worker 解析规则 + 端点状态机测试

覆盖: worker 截断(200 行×6 列)/单元格 24 字符裁剪/空表/truncated 语义,
_slice_xlsx_sheets 切片, 端点 .xls 400/非 xlsx 400/缓存命中/误差文件,
updated_at 变化 → key 轮换。
不依赖 MinIO: worker 直接喂临时文件; 端点走 monkeypatch 的缓存根目录。
DB fixture: conftest db (TEST_DATABASE_URL)。
"""
import json
import uuid as _uuid
from datetime import timedelta

import pytest
from openpyxl import Workbook

from app.api.v1 import drive_files
from app.api.v1.drive_files import (
    _slice_xlsx_sheets,
    _xlsx_cache_key,
    _xlsx_preview_worker,
    get_xlsx_preview_status,
)
from app.models.knowledge import Knowledge
from app.models.member import Member


async def _mk_member(db, tag):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"xp_{tag}_{u}", name=tag, password_hash="h",
        role="member", grade="测试", is_active=True, wechat_id=f"wx_xp_{tag}_{u}",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _mk_file(db, owner, file_name, updated_at=None):
    k = Knowledge(
        content="", title=file_name, storage_mode="drive", file_name=file_name,
        file_path=f"drive-test/{file_name}", created_by=owner.id, visibility="team",
    )
    if updated_at is not None:
        k.updated_at = updated_at
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


def _write_xlsx(path, rows_by_sheet):
    wb = Workbook()
    for i, (name, rows) in enumerate(rows_by_sheet.items()):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = name
        for r in rows:
            ws.append(r)
    wb.save(path)


@pytest.mark.asyncio
async def test_xls_rejected_400(db):
    """.xls 老格式 → 400 (v1 不支持)"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "old.xls")
    with pytest.raises(Exception) as ei:
        await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert getattr(ei.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_non_xlsx_rejected_400(db):
    """非表格扩展名 → 400"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "doc.docx")
    with pytest.raises(Exception) as ei:
        await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert getattr(ei.value, "status_code", None) == 400


def test_worker_truncation_and_clipping(tmp_path):
    """worker: 30 行文件全量缓存, 7 列截前 6 列, 40 字符单元格裁到 24"""
    p = tmp_path / "in.xlsx"
    long_cell = "X" * 40
    _write_xlsx(p, {
        "数据": [["列A", "列B", "列C", "列D", "列E", "列F", "列G"]]
               + [[long_cell, j, "", None, 1.5, True, "g"] for j in range(29)],
        "空表": [],
    })
    cache_dir = tmp_path / "cache"
    _xlsx_preview_worker(1, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    s1, s2 = data["sheets"]
    assert s1["name"] == "数据"
    assert s1["total_rows"] == 30
    assert len(s1["rows"]) == 30
    assert all(len(r) == 6 for r in s1["rows"])          # 7 列 → 前 6 列
    assert s1["rows"][1][0] == "X" * 24                  # 单元格 24 字符裁剪
    assert s1["rows"][0][0] == "列A"
    assert s1["truncated"] is False                      # 30 行未超 200 缓存上限
    assert s2["rows"] == [] and s2["truncated"] is False  # 空表不算截断


def test_worker_caps_200_rows(tmp_path):
    """worker: 301 行文件只缓存前 200 行, truncated=True"""
    p = tmp_path / "big.xlsx"
    _write_xlsx(p, {"大表": [["h1", "h2"]] + [[i, i] for i in range(300)]})
    cache_dir = tmp_path / "cache"
    _xlsx_preview_worker(2, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    s = data["sheets"][0]
    assert len(s["rows"]) == 200
    assert s["total_rows"] == 301
    assert s["truncated"] is True


def test_slice_max_rows():
    """端点切片: max_rows 截 rows, truncated 按 total_rows 重算"""
    sheets = [{"name": "s", "total_rows": 260, "truncated": True,
               "rows": [[str(i)] for i in range(200)]}]
    cut = _slice_xlsx_sheets(sheets, 8)
    assert len(cut[0]["rows"]) == 8 and cut[0]["truncated"] is True
    cut_all = _slice_xlsx_sheets(sheets, 200)
    assert len(cut_all[0]["rows"]) == 200 and cut_all[0]["truncated"] is True
    exact = _slice_xlsx_sheets(
        [{"name": "e", "total_rows": 8, "truncated": False,
          "rows": [[str(i)] for i in range(8)]}], 200)
    assert exact[0]["truncated"] is False                # 8 行全量缓存 → 未截断


@pytest.mark.asyncio
async def test_endpoint_cache_hit(db, tmp_path, monkeypatch):
    """ready.json 已存在 → 直接切片返回, 不再触发 worker"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "exp.xlsx")
    root = tmp_path / "xr"
    monkeypatch.setattr(drive_files, "_XLSX_PREVIEW_ROOT", root)
    key = _xlsx_cache_key(f.updated_at)
    d = root / ("%d_%s" % (f.id, key))
    d.mkdir(parents=True)
    (d / "ready.json").write_text(json.dumps({"sheets": [{
        "name": "S", "total_rows": 260, "truncated": True,
        "rows": [[str(i)] for i in range(200)]}]}, ensure_ascii=False), encoding="utf-8")
    resp = await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert resp["status"] == "ready"
    assert len(resp["sheets"][0]["rows"]) == 8
    assert resp["sheets"][0]["name"] == "S"


@pytest.mark.asyncio
async def test_endpoint_error_file(db, tmp_path, monkeypatch):
    """error.txt 已存在 → status=error 带消息 (前端回落占位)"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "bad.xlsx")
    root = tmp_path / "xr"
    monkeypatch.setattr(drive_files, "_XLSX_PREVIEW_ROOT", root)
    d = root / ("%d_%s" % (f.id, _xlsx_cache_key(f.updated_at)))
    d.mkdir(parents=True)
    (d / "error.txt").write_text("BadZipFile: File is not a zip file", encoding="utf-8")
    resp = await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert resp["status"] == "error"
    assert "BadZipFile" in resp["message"]


@pytest.mark.asyncio
async def test_cache_key_rotates_with_updated_at(db):
    """updated_at 变化 → key 变化 → 旧缓存自动失效"""
    u = await _mk_member(db, "u")
    f1 = await _mk_file(db, u, "a.xlsx")
    f2 = await _mk_file(db, u, "b.xlsx", updated_at=f1.updated_at + timedelta(hours=1))
    assert _xlsx_cache_key(f1.updated_at) != _xlsx_cache_key(f2.updated_at)
```

- [ ] **步骤 1.2：运行测试验证失败**

运行：`docker compose exec -T app pytest tests/test_xlsx_preview.py -v`
预期：-collection error / ImportError：`cannot import name '_slice_xlsx_sheets'`（函数还不存在）

- [ ] **步骤 1.3：实现 worker 与纯函数**

在 `app/api/v1/drive_files.py` 的 pdf-pages 段之后（`get_pdf_page_image` 函数结束、`# === 批次⑩.17 自研 PPT 第三栏预览` 注释之前）插入：

```python
# === 批次⑩.65 XLSX 预览 (2026-09-07 选型 D): openpyxl 抽前 200 行×6 列 JSON → 前端横幅+速览 ===
# 与 pptx/docx-pages 同构状态机: converting(锁) → ready(ready.json) / error(error.txt)。
# 缓存固定抽满 200 行, 端点按 max_rows 切片 (前端常态 8 行/全屏 200 行共用一份缓存)。
_XLSX_PREVIEW_LOCKS: dict = {}
_XLSX_PREVIEW_ROOT = FsPath("/app/data/xlsx_preview")
_XLSX_CACHE_ROWS = 200
_XLSX_CACHE_COLS = 6
_XLSX_CELL_MAX_CHARS = 24


def _xlsx_cache_key(updated_at) -> str:
    return hashlib.md5(("v1:" + str(updated_at)).encode()).hexdigest()[:12]


def _xlsx_cache_dir(file_id: int, key: str) -> FsPath:
    return _XLSX_PREVIEW_ROOT / ("%d_%s" % (file_id, key))


def _clip_cell(v) -> str:
    if v is None:
        return ""
    return str(v)[:_XLSX_CELL_MAX_CHARS]


def _xlsx_truncated(total, n_rows: int) -> bool:
    if total is None:
        return True   # read_only 下行数未知 → 按未读全提示
    return total > n_rows and n_rows > 0   # 空表不算截断


def _xlsx_preview_worker(file_id: int, src_path: str, cache_dir: FsPath, key: str):
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        from openpyxl import load_workbook
        wb = load_workbook(src_path, read_only=True, data_only=True)
        sheets = []
        for ws in wb.worksheets:
            rows = []
            for row in ws.iter_rows(max_row=_XLSX_CACHE_ROWS, max_col=_XLSX_CACHE_COLS,
                                    values_only=True):
                rows.append([_clip_cell(c) for c in row])
            total = ws.max_row  # read_only 下可能为 None
            sheets.append({
                "name": ws.title,
                "total_rows": int(total) if total is not None else None,
                "truncated": _xlsx_truncated(total, len(rows)),
                "rows": rows,
            })
        wb.close()
        (cache_dir / "ready.json").write_text(
            json.dumps({"sheets": sheets}, ensure_ascii=False), encoding="utf-8")
        logger.info("[xlsx-preview] 解析完成 file=%d 工作表=%d", file_id, len(sheets))
    except Exception as e:
        logger.error("[xlsx-preview] file=%s 解析失败: %s", file_id, e)
        try:
            (cache_dir / "error.txt").write_text(str(e)[:500], encoding="utf-8")
        except Exception:
            pass
    finally:
        _XLSX_PREVIEW_LOCKS.pop(key, None)


def _slice_xlsx_sheets(sheets: list, max_rows: int) -> list:
    out = []
    for s in sheets:
        rows = s.get("rows") or []
        cut = rows[:max_rows]
        total = s.get("total_rows")
        out.append({
            "name": s.get("name"),
            "total_rows": total,
            "truncated": _xlsx_truncated(total, len(cut)),
            "rows": cut,
        })
    return out
```

- [ ] **步骤 1.4：运行测试验证部分通过**

运行：`docker compose exec -T app pytest tests/test_xlsx_preview.py -v`
预期：`test_worker_*` / `test_slice_*` PASS；`test_xls_rejected_400` / `test_non_xlsx_rejected_400` / `test_endpoint_*` FAIL（`get_xlsx_preview_status` 还不存在 → ImportError，若步骤 1.3 已让 import 成功则这 4 个 FAIL: function not defined）

- [ ] **步骤 1.5：Commit**

```bash
git add app/api/v1/drive_files.py tests/test_xlsx_preview.py
git commit -m "feat(drive): 批次⑩.65 XLSX 预览后端① — openpyxl worker(200行×6列/24字符) + 切片纯函数"
```

---

### 任务 2：后端 — 状态机端点（TDD）

**文件：**
- 修改：`app/api/v1/drive_files.py`（紧接任务 1 插入的函数之后）

- [ ] **步骤 2.1：确认任务 1 的端点测试仍在失败**

运行：`docker compose exec -T app pytest tests/test_xlsx_preview.py -v -k "endpoint or rejected"`
预期：FAIL（`get_xlsx_preview_status` 未定义）

- [ ] **步骤 2.2：实现端点**

紧接 `_slice_xlsx_sheets` 之后插入：

```python
@router.get("/files/{file_id}/xlsx-preview")
async def get_xlsx_preview_status(
    file_id: int,
    max_rows: int = Query(8, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """XLSX 数据速览: 轮询状态端点 (ready 时返回各工作表前 max_rows 行 JSON).

    缓存固定抽 200 行×6 列, 本端点按 max_rows 切片; .xls 老格式 v1 不支持。
    """
    svc = DriveService(db)
    f = await svc.get_file(file_id, current_user_id=current_user.id)
    if f is None:
        raise HTTPException(status_code=404, detail="file 不存在或无权访问")
    lname = (f.file_name or "").lower()
    if lname.endswith(".xls") and not lname.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="暂不支持 .xls 老格式，请另存为 .xlsx")
    if not lname.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx")
    if not f.file_path:
        raise HTTPException(status_code=404, detail="file 无 MinIO 对象")

    key = _xlsx_cache_key(f.updated_at)
    cache_dir = _xlsx_cache_dir(file_id, key)

    if (cache_dir / "ready.json").exists():
        try:
            data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
        except Exception:
            data = {"sheets": []}
        return {"status": "ready", "sheets": _slice_xlsx_sheets(data.get("sheets", []), max_rows)}
    if (cache_dir / "error.txt").exists():
        return {"status": "error",
                "message": (cache_dir / "error.txt").read_text(encoding="utf-8")[:200]}

    lock = _XLSX_PREVIEW_LOCKS.get(key)
    if lock is not None and lock.locked():
        return {"status": "converting"}

    lock = threading.Lock()
    _XLSX_PREVIEW_LOCKS[key] = lock
    lock.acquire()
    src = FsPath("/tmp") / ("xlsx_src_%d.xlsx" % file_id)
    if not src.exists():
        raw = await file_service.download_file(f.file_path)
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(raw)
    th = threading.Thread(target=_xlsx_preview_worker,
                          args=(file_id, str(src), cache_dir, key), daemon=True)
    th.start()
    return {"status": "converting"}
```

依赖核对：`Query` / `HTTPException` / `json` / `hashlib` / `threading` / `FsPath` / `file_service` / `DriveService` 均已在文件头部或 pptx 段 import，无需新增 import。

- [ ] **步骤 2.3：运行全部测试验证通过**

运行：`docker compose exec -T app pytest tests/test_xlsx_preview.py -v`
预期：9 个测试全部 PASS

- [ ] **步骤 2.4：Commit**

```bash
git add app/api/v1/drive_files.py
git commit -m "feat(drive): 批次⑩.65 XLSX 预览后端② — xlsx-preview 状态机端点 (.xls 400/缓存切片/converting 锁)"
```

---

### 任务 3：前端 — excel 类型接线（previewKind / 舞台高 / coverUrl 跳过）

**文件：**
- 修改：`web/src/components/drive/DriveDetailRail.vue`

- [ ] **步骤 3.1：previewKind 拆出 excel**

`previewKind` computed（约 line 530-541）中，在 `if (['ppt', 'pptx', 'xls', 'xlsx'].includes(e)) return 'office'` 一行**之前**加：

```js
  if (e === 'xlsx') return 'excel'   // 批次⑩.65 (选型 D): openpyxl JSON 速览 (xls 留 office 占位)
```

改后 office 分支实际只剩 `['ppt', 'xls']`。

- [ ] **步骤 3.2：舞台高度**

`stageHeight` 末尾的高度映射对象（约 line 554）加 `excel: 268`：

```js
  return { image: 220, video: 189, audio: 130, pdf: 470, text: 300, office: 220, excel: 268 }[previewKind.value] || 168
```

- [ ] **步骤 3.3：coverUrl 跳过名单**

coverUrl watch（约 line 520）的跳过行扩为：

```js
  if (['doc', 'docx', 'pdf', 'xlsx'].includes(extOf.value)) return  // 批次⑩.62 分页/⑩.65 excel 预览分支接管
```

- [ ] **步骤 3.4：构建验证**

运行：`cd web && npm run build`
预期：构建成功无报错（此时 excel 分支尚无模板，会落兜底占位——行为与改动前一致）

- [ ] **步骤 3.5：Commit**

```bash
git add web/src/components/drive/DriveDetailRail.vue web/dist
git commit -m "feat(drive): 批次⑩.65 XLSX 预览前端① — previewKind excel 接线 (舞台 268/cover 跳过)"
```

---

### 任务 4：前端 — excel 模板分支 + 轮询状态

**文件：**
- 修改：`web/src/components/drive/DriveDetailRail.vue`

- [ ] **步骤 4.1：模板分支**

在 docx/pdf 分支结束的 `</div>`（约 line 234）之后、`<!-- 兜底占位 -->` 之前插入：

```html
          <!-- 批次⑩.65 (2026-09-07 选型 D): XLSX 预览 — 深青横幅头 + 工作表标签 + 前 8 行速览 -->
          <div v-else-if="previewKind === 'excel'" class="rf-xlsx">
            <div v-if="xlsxStatus === 'idle' || xlsxStatus === 'loading'" class="rf-skel">
              <div class="rf-conv-t">正在解析 Excel 工作表…</div>
              <div class="rf-conv-s">首次约 1-3 秒 · 之后打开秒出</div>
              <div class="rf-skel-ttl" style="margin-top:18px"></div>
              <div class="rf-skel-ln" style="width:78%"></div>
            </div>
            <div v-else-if="xlsxStatus === 'error' || !xlsxActiveSheet" class="rail-cover-ph" :style="{ borderColor: typeColor }">
              <span class="rail-cover-abbr">{{ typeAbbr }}</span>
              <span class="rail-cover-hint">无预览图</span>
            </div>
            <template v-else>
              <div class="rf-xlsx-head">
                <span class="rf-xlsx-ico"><svg viewBox="0 0 24 24"><path d="M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm1 4v3h5V7H5zm7 0v3h7V7h-7zM5 12v3h5v-3H5zm7 0v3h7v-3h-7zM5 17v2h5v-2H5zm7 0v2h7v-2h-7z"/></svg></span>
                <div class="rf-xlsx-tt">
                  <div class="rf-xlsx-nm" :title="name">{{ name }}</div>
                  <div class="rf-xlsx-meta">{{ xlsxSheets.length }} 个工作表<template v-if="xlsxActiveSheet.total_rows"> · {{ xlsxActiveSheet.total_rows }} 行</template> · {{ fmtSize(file.file_size) }}</div>
                </div>
              </div>
              <div v-if="xlsxSheets.length > 1" class="rf-xlsx-tabs">
                <button
                  v-for="(s, i) in xlsxSheets" :key="'xTab' + i"
                  type="button" class="rf-xlsx-tab" :class="{ on: i === xlsxActive }"
                  :title="s.name" @click="xlsxActive = i"
                >{{ s.name }}</button>
              </div>
              <div class="rf-xlsx-gridwrap">
                <div v-if="!xlsxActiveSheet.rows.length" class="rf-xlsx-empty">空工作表</div>
                <table v-else class="rf-xlsx-grid">
                  <thead><tr><th v-for="(h, ci) in xlsxView.header" :key="'xh' + ci">{{ h }}</th></tr></thead>
                  <tbody>
                    <tr v-for="(r, ri) in xlsxView.body" :key="'xr' + ri">
                      <td v-for="(c, ci) in r" :key="'xc' + ci">{{ c }}</td>
                    </tr>
                  </tbody>
                </table>
                <div v-if="!pptFull" class="rf-xlsx-fade"></div>
              </div>
              <div class="rf-xlsx-foot">
                <template v-if="pptFull">全屏 · 已加载 {{ Math.max(0, xlsxActiveSheet.rows.length - 1) }} 行</template>
                <template v-else>仅预览前 {{ Math.min(8, Math.max(0, xlsxActiveSheet.rows.length - 1)) }} 行<template v-if="xlsxActiveSheet.truncated"> · 全屏查看更多</template></template>
              </div>
            </template>
          </div>
```

- [ ] **步骤 4.2：状态与轮询脚本**

`<script setup>` 中 docx 段之后（`onBeforeUnmount(() => { stopDocxPoll(); ... })` 之后、`prevDisabled` computed 之前）插入：

```js
/* ---- 批次⑩.65 (选型 D): XLSX 预览 — openpyxl JSON, 常态表头+前 8 行 / 全屏缓存全量 ---- */
const XLSX_RAIL_ROWS = 8
const xlsxStatus = ref('idle')   // idle | loading | ready | error
const xlsxSheets = ref([])
const xlsxActive = ref(0)
let xlsxPollTimer = null
let xlsxPollSeq = 0
const xlsxActiveSheet = computed(() => xlsxSheets.value[xlsxActive.value] || null)
const xlsxView = computed(() => {
  const s = xlsxActiveSheet.value
  if (!s || !s.rows?.length) return { header: [], body: [] }
  return {
    header: s.rows[0],
    body: pptFull.value ? s.rows.slice(1) : s.rows.slice(1, 1 + XLSX_RAIL_ROWS),
  }
})
function stopXlsxPoll() { if (xlsxPollTimer) { clearTimeout(xlsxPollTimer); xlsxPollTimer = null } }
function startXlsxPoll(fid) {
  stopXlsxPoll()
  const seq = ++xlsxPollSeq
  xlsxStatus.value = 'loading'
  const tick = async () => {
    if (seq !== xlsxPollSeq) return
    try {
      const resp = await axios.get(`/api/v1/drive/files/${fid}/xlsx-preview`, { params: { max_rows: 200 } })
      const st = resp.data?.status
      if (st === 'ready') {
        xlsxStatus.value = 'ready'
        xlsxSheets.value = resp.data.sheets || []
        xlsxActive.value = 0
        return
      }
      if (st === 'error') { xlsxStatus.value = 'error'; return }
      xlsxPollTimer = setTimeout(tick, 2000)
    } catch {
      xlsxPollTimer = setTimeout(tick, 2500)   // 瞬时网络错误重试 (同 docx 模式)
    }
  }
  tick()
}
watch([() => props.file?.id, previewKind], ([fid, kind]) => {
  stopXlsxPoll()
  xlsxSheets.value = []
  xlsxActive.value = 0
  if (kind === 'excel' && fid != null) startXlsxPoll(fid)
  else xlsxStatus.value = 'idle'
}, { immediate: true })
onBeforeUnmount(() => { stopXlsxPoll(); xlsxPollSeq++ })
```

注意：`ref / computed / watch / onBeforeUnmount` 该文件顶部均已 import，无需改动 import 语句（CLAUDE.md import 完整性规则——确认即可，不加重复）。

- [ ] **步骤 4.3：全屏翻页守卫核对**

`onFsWheel` / `onFsKeydown`（约 line 907-927）对 excel 无操作（`page.value` 走 docx 分支会读到 `docxImgTotalSafe`=1，不翻页）——**无需改动**，但读一遍确认无异常抛出。

- [ ] **步骤 4.4：构建验证**

运行：`cd web && npm run build`
预期：构建成功

- [ ] **步骤 4.5：Commit**

```bash
git add web/src/components/drive/DriveDetailRail.vue web/dist
git commit -m "feat(drive): 批次⑩.65 XLSX 预览前端② — excel 模板分支 + 200 行单请求轮询 (常态 8 行/全屏全量)"
```

---

### 任务 5：前端 — rf-xlsx-* 样式（含全屏滚动）

**文件：**
- 修改：`web/src/components/drive/DriveDetailRail.vue`（`<style scoped>` 末尾、`.rf-k1 .rf-k1-sub` 规则之后）

- [ ] **步骤 5.1：追加样式**

```css
/* ── 批次⑩.65 (选型 D): XLSX 预览 — 深青横幅头 (音频 C1 同族) + 工作表标签 + 速览表 ── */
.rf-xlsx { height: 100%; display: flex; flex-direction: column; box-sizing: border-box; background: var(--color-bg-card); }
.rf-xlsx-head { flex: none; display: flex; align-items: center; gap: 9px; background: linear-gradient(135deg, #0E766E, #0B655E); color: #fff; padding: 8px 11px; }
.rf-xlsx-ico { width: 26px; height: 26px; border-radius: 7px; background: rgba(255,255,255,.18); display: flex; align-items: center; justify-content: center; flex: none; }
.rf-xlsx-ico svg { width: 14px; height: 14px; fill: #fff; }
.rf-xlsx-tt { flex: 1; min-width: 0; }
.rf-xlsx-nm { font-size: 11px; font-weight: var(--font-weight-semibold); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rf-xlsx-meta { font-size: 9px; color: rgba(255,255,255,.7); margin-top: 1px; }
.rf-xlsx-tabs { flex: none; display: flex; gap: 4px; padding: 5.5px 8px; border-bottom: 1px solid var(--color-border); background: #FBFBF9; overflow-x: auto; }
.rf-xlsx-tab {
  flex: 1 0 auto; min-width: 0; font-size: 10px; padding: 3px 8px;
  border: none; background: none; cursor: pointer; font-family: inherit;
  color: var(--color-text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  border-radius: 6px; transition: all var(--duration-fast);
}
.rf-xlsx-tab:hover { color: var(--color-file-excel); }
.rf-xlsx-tab.on { color: var(--color-file-excel); font-weight: var(--font-weight-semibold); background: color-mix(in srgb, var(--color-file-excel) 10%, transparent); }
.rf-xlsx-gridwrap { flex: 1; min-height: 0; overflow: hidden; position: relative; }
.rf-xlsx-grid { width: 100%; border-collapse: collapse; font-size: 10.6px; }
.rf-xlsx-grid th {
  text-align: left; font-weight: var(--font-weight-semibold); color: var(--color-text-regular);
  background: #F6F7F5; padding: 4.5px 8px; border-bottom: 1px solid var(--color-border); white-space: nowrap;
}
.rf-xlsx-grid td {
  padding: 4px 8px; color: var(--color-text-regular); border-bottom: 1px solid #F4F5F2;
  white-space: nowrap; font-family: var(--font-family-mono, monospace); font-size: 10.2px;
}
.rf-xlsx-grid tbody tr:nth-child(even) td { background: #FAFBF9; }
.rf-xlsx-fade { position: absolute; left: 0; right: 0; bottom: 0; height: 30px; background: linear-gradient(rgba(255,255,255,0), #fff); pointer-events: none; }
.rf-xlsx-empty { padding: 26px 14px; text-align: center; font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.rf-xlsx-foot { flex: none; display: flex; align-items: center; justify-content: center; padding: 5px 10px; font-size: 10px; color: var(--color-text-secondary); border-top: 1px solid var(--color-border); background: #FBFBF9; }
/* 全屏放映: 表格滚动看缓存全量, 去渐隐, 字号放大 */
:is(.rf-stage):fullscreen .rf-xlsx-gridwrap { overflow-y: auto; }
:is(.rf-stage):fullscreen .rf-xlsx-grid { font-size: 12.5px; }
:is(.rf-stage):fullscreen .rf-xlsx-grid th,
:is(.rf-stage):fullscreen .rf-xlsx-grid td { padding: 6px 12px; }
```

- [ ] **步骤 5.2：构建验证**

运行：`cd web && npm run build`
预期：构建成功

- [ ] **步骤 5.3：Commit**

```bash
git add web/src/components/drive/DriveDetailRail.vue web/dist
git commit -m "feat(drive): 批次⑩.65 XLSX 预览前端③ — rf-xlsx-* 样式 (横幅头/标签/斑马表/全屏滚动去渐隐)"
```

---

### 任务 6：端到端验证（verification-before-completion）

**文件：** 无新改动（发现问题回改对应任务文件后重新 build）

- [ ] **步骤 6.1：重启后端加载新端点**

运行：`docker compose restart app`（CLAUDE.md 纪律：deploy-auto.sh 不重启 Python，新端点必须手动重启）
预期：容器重启完成，`docker compose logs app --tail 20` 无报错

- [ ] **步骤 6.2：后端冒烟**

```bash
docker compose exec -T app python -c "
from openpyxl import Workbook
wb = Workbook(); ws = wb.active; ws.title = 'Sheet1'
ws.append(['列A', '列B'])
for i in range(20): ws.append([i, i * 2])
wb.save('/tmp/smoke.xlsx'); print('ok')
"
```

运行：`cd web && npm run dev` 起前端（或已有 dev server）
浏览器登录 → 网盘 → 上传一个真实 .xlsx（含 2-3 个工作表、20+ 行）

- [ ] **步骤 6.3：浏览器黄金路径逐项验证**

1. 点中 .xlsx 行 → 舞台出现深青横幅头（工作表数/行数/大小）+ 标签 + 表头 + 8 行数据 + 渐隐 + 脚注「仅预览前 8 行」
2. 点第二个工作表标签 → 表格内容切换、active pill 变绿
3. 点「全屏放映」→ 表格可滚动查看全部缓存行、脚注变「全屏 · 已加载 N 行」；Esc 退出恢复 8 行视图
4. 点中其他类型文件（图片/audio/ppt）→ 各分支正常无回归；切回 xlsx 状态重置
5. DevTools Network：`xlsx-preview` 请求只发一个（max_rows=200），ready 后无轮询残留

- [ ] **步骤 6.4：错误回落验证**

上传一个改后缀为 .xlsx 的假文件（如把 .txt 改名）→ 点中 → 轮询后回落「XLSX 无预览图」占位，详情卡其余功能（下载/评论/版本）不受影响

- [ ] **步骤 6.5：构建产物提交**

```bash
cd web && npm run build
git add web/src/components/drive/DriveDetailRail.vue web/dist
git commit -m "feat(drive): 批次⑩.65 XLSX 预览收尾 — E2E 验证通过 + dist 构建"
```

（若 6.3/6.4 无回改，本步骤与任务 5.3 合并为一次提交即可——以实际改动为准。）

---

## 自检记录

- **规格覆盖度：** §3 端点/缓存/状态机 → 任务 1/2；§3.3 解析规则（200×6/24 字符/truncated）→ 任务 1 步骤 1.1 测试断言逐条对应；§4.1 类型/舞台/cover → 任务 3；§4.2 模板五要素 → 任务 4.1；§4.3 数据流/换文件重置/全屏 → 任务 4.2；§4.4 样式纪律 → 任务 5；§5 后端 7 项测试 → 任务 1+2（合并为 9 个用例，max_rows 默认/上限由 `Query(8, ge=1, le=200)` 框架层保证，非法值 FastAPI 自动 422，不单列）；§5 前端 5 项 → 任务 6.3/6.4。遗漏检查：无。
- **占位符扫描：** 无「待定/TODO/类似任务 N」；所有代码步骤含完整代码。
- **类型一致性：** `_xlsx_cache_key` / `_xlsx_cache_dir` / `_clip_cell` / `_xlsx_truncated` / `_xlsx_preview_worker` / `_slice_xlsx_sheets` / `get_xlsx_preview_status` 前后引用一致；前端 `xlsxStatus` / `xlsxSheets` / `xlsxActive` / `xlsxActiveSheet` / `xlsxView` / `startXlsxPoll` / `stopXlsxPoll` 模板与脚本一致；响应字段 `status/sheets[].name/total_rows/truncated/rows` 后端生产与前端消费一致。
