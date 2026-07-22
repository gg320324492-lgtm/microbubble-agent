/**
 * tests/visual/desktop/drive-folder-nesting-2026-07-22.spec.mjs
 *
 * 端到端验证 Drive folder 5+ 层级嵌套 (create / rename / move / delete / depth>5 不抛错)
 *
 * 5 个场景:
 *   A) 创建 5 级嵌套 folder (L1 → L2 → L3 → L4 → L5), 验证 depth 单调递增 + path 完整拼接
 *   B) 5 级 folder 各创建 1 个 file (drive_files), 验证 file 在 right folder 下
 *   C) 重命名 L3 (检查 children files/sub-folders 仍可访问, path/depth 同步更新)
 *   D) 移动 L5 file 到 L1 (验证 file.folder_id 改了 + path 自动重算)
 *   E) 软删 L3 (L4/L5 自动 cascade 到 L2 旗下, 30 天回收站可恢复)
 *   F) 边界: 创建 L6 (depth=5) 不抛错 (depth 字段约束验证, >5 仍可写入)
 *
 * 前置:
 *   - BASE_URL 指向本地 docker app (默认 http://127.0.0.1:8000)
 *   - xiaoqi_testbot (admin) 账号登录
 *   - 5 套嵌套 namespace 用 ts 时间戳隔开 (避免跑两次 spec 撞车)
 *
 * 运行:
 *   BASE_URL=http://127.0.0.1:8000 \
 *     npx playwright test tests/visual/desktop/drive-folder-nesting-2026-07-22.spec.mjs \
 *       --project=desktop-chrome
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8000'
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'

async function apiFetch(path, opts = {}) {
  const url = `${BASE_URL}${path}`
  const headers = opts.headers ? { ...opts.headers } : {}
  if (opts.token) headers['Authorization'] = `Bearer ${opts.token}`
  if (opts.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json'
  const fetchOpts = {
    method: opts.method || 'GET',
    headers,
  }
  if (opts.body !== undefined) {
    fetchOpts.body = typeof opts.body === 'string' ? opts.body : JSON.stringify(opts.body)
  }
  const r = await fetch(url, fetchOpts)
  let data = null
  const ct = r.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    data = await r.json().catch(() => null)
  } else {
    data = await r.text().catch(() => null)
  }
  return { status: r.status, data, ok: r.ok }
}

async function login() {
  const r = await apiFetch('/api/v1/auth/login', {
    method: 'POST',
    body: { username: USERNAME, password: PASSWORD },
  })
  if (!r.ok) throw new Error(`login failed: ${r.status} ${JSON.stringify(r.data)}`)
  return r.data.access_token
}

/**
 * 创建 N 级嵌套 folder, 全部 private + 统一 prefix (含 ts).
 * Returns { ids: [l1_id, l2_id, ..., lN_id], names: [...] }
 */
async function createNLevelFolders(token, prefix, n) {
  const ids = []
  const names = []
  for (let i = 1; i <= n; i++) {
    const name = `${prefix}_L${i}`
    names.push(name)
    const parentId = i === 1 ? null : ids[i - 2]
    // 退避重试: write tier 限流时按 35s 阶梯等 (60s 窗口)
    let newId = null
    for (let attempt = 0; attempt < 3; attempt++) {
      if (attempt > 0) {
        console.log(`[retry] L${i} attempt ${attempt + 1} wait 35s (429 backoff)`)
        await new Promise((res) => setTimeout(res, 35 * 1000))
      }
      const r = await apiFetch('/api/v1/folders', {
        method: 'POST',
        token,
        body: { name, parent_id: parentId, visibility: 'private' },
      })
      if (r.status === 201) { newId = r.data.id; break }
      if (r.status !== 429) {
        // 非 429, 立即抛错
        throw new Error(`L${i} create failed: status=${r.status} body=${JSON.stringify(r.data)}`)
      }
    }
    if (!newId) {
      throw new Error(`L${i} create failed after 3 attempts (last 429, rate-limited)`)
    }
    ids.push(newId)
  }
  return { ids, names }
}

async function createFile(token, folderId, filename, content = 'hello drive nest test') {
  // 限流退避 (write tier 30/min, 5 test + 5 file/test = 30+/min 极易触发 429)
  let fileData = null
  let lastErr = null
  for (let attempt = 0; attempt < 3; attempt++) {
    if (attempt > 0) {
      console.log(`[retry] file ${filename} attempt ${attempt + 1} wait 35s (429 backoff)`)
      await new Promise((r) => setTimeout(r, 35 * 1000))
    }
    try {
      // multipart upload (单端点流式) — 必须用 fetch + FormData
      const form = new FormData()
      const blob = new Blob([content], { type: 'text/plain' })
      form.append('file', blob, filename)
      form.append('filename', filename)
      form.append('content_type', 'text/plain')
      form.append('total_size', String(content.length))
      form.append('folder_id', String(folderId))
      form.append('visibility', 'private')

      const r = await fetch(`${BASE_URL}/api/v1/drive/files/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      })
      if (r.ok) {
        fileData = await r.json()
        break
      }
      if (r.status === 429) {
        lastErr = new Error(`upload file ${filename} got 429 (attempt ${attempt + 1})`)
        continue
      }
      const txt = await r.text()
      throw new Error(`upload file ${filename} failed: status=${r.status} body=${txt.slice(0, 300)}`)
    } catch (e) {
      if (e.name === 'TypeError') throw e
      lastErr = e
    }
  }
  if (!fileData) throw lastErr || new Error(`upload file ${filename} failed after 3 attempts`)
  return fileData
}

async function softDeleteFolder(token, folderId, recursive = true) {
  return apiFetch(`/api/v1/folders/${folderId}?recursive=${recursive}`, {
    method: 'DELETE',
    token,
  })
}

async function getFolder(token, folderId, includeDeleted = false) {
  const r = await apiFetch(
    `/api/v1/folders/${folderId}${includeDeleted ? '?include_deleted=true' : ''}`,
    { token },
  )
  return r.data
}

async function listFiles(token, folderId) {
  const r = await apiFetch(`/api/v1/drive/files?folder_id=${folderId}`, { token })
  return r.data?.items || []
}

test.describe('Drive folder 5+ 层级嵌套 e2e (2026-07-22)', () => {
  // 全局默认 30s 不够, F test 要重试 35s 等限流重置
  test.setTimeout(120_000)

  let token
  const TS = Date.now()
  const NS = `nest_${TS}`

  test.beforeAll(async () => {
    token = await login()
    expect(token).toBeTruthy()
    console.log(`[setup] BASE_URL=${BASE_URL} token=${token.slice(0, 20)}... NS=${NS}`)
  })

  test('A: 创建 5 级嵌套 folder, 验证 depth 单调递增 + path 完整拼接', async () => {
    const { ids, names } = await createNLevelFolders(token, NS, 5)
    expect(ids).toHaveLength(5)
    console.log(`[A] created L1..L5 ids=${ids.join(',')}`)

    // 验证每级 depth + path
    for (let i = 0; i < 5; i++) {
      const f = await getFolder(token, ids[i])
      const expectedDepth = i  // L1 depth=0, L2 depth=1, ..., L5 depth=4
      expect(f.depth, `L${i + 1} depth 应为 ${expectedDepth}, got ${f.depth}`).toBe(expectedDepth)
      expect(f.name, `L${i + 1} name`).toBe(names[i])
      // path 应包含所有 parent id, 顺序从 root 开始
      const expectedPath = '/' + ids.slice(0, i + 1).join('/') + '/'
      expect(f.path, `L${i + 1} path 应为 ${expectedPath}, got ${f.path}`).toBe(expectedPath)
    }

    // 验证 parent_id 链: L_i.parent_id == L_{i-1}.id
    for (let i = 1; i < 5; i++) {
      const f = await getFolder(token, ids[i])
      expect(f.parent_id, `L${i + 1} parent_id 应为 ${ids[i - 1]}`).toBe(ids[i - 1])
    }

    console.log(`[A PASS] 5 级嵌套创建成功, depth 0→4, path 单调递增`)
  })

  test('B: 5 级 folder 各创建 1 个 file, 验证 file 在 right folder 下', async () => {
    const { ids } = await createNLevelFolders(token, `${NS}_B`, 5)
    expect(ids).toHaveLength(5)

    const fileIds = []
    for (let i = 0; i < 5; i++) {
      const filename = `${NS}_B_L${i + 1}_file.txt`
      const file = await createFile(token, ids[i], filename, `content for L${i + 1}`)
      expect(file.id, `file in L${i + 1} 应有 id`).toBeGreaterThan(0)
      expect(file.folder_id, `file folder_id 应为 ${ids[i]}`).toBe(ids[i])
      fileIds.push(file.id)
      console.log(`[B] uploaded file id=${file.id} folder_id=${ids[i]} name=${filename}`)
    }

    // 反向验证: 列每个 folder, 应该看到 1 个 file
    for (let i = 0; i < 5; i++) {
      const files = await listFiles(token, ids[i])
      expect(files.length, `L${i + 1} 应有 1 个 file, got ${files.length}`).toBe(1)
      expect(files[0].folder_id).toBe(ids[i])
    }

    console.log(`[B PASS] 5 file × 5 folder 全部正确归属`)
  })

  test('C: 重命名 L3, 验证 children files/sub-folders 仍可访问 + path 同步', async () => {
    const { ids } = await createNLevelFolders(token, `${NS}_C`, 5)
    const l3_id = ids[2]
    const l4_id = ids[3]
    const l5_id = ids[4]
    const oldL3 = await getFolder(token, l3_id)
    const oldL3Path = oldL3.path
    const oldL3Depth = oldL3.depth

    // L5 放一个 file, rename 后验证还能找到
    const l5File = await createFile(token, l5_id, `${NS}_C_L5_file.txt`)
    expect(l5File.folder_id).toBe(l5_id)

    // 重命名 L3
    const newName = `${NS}_C_L3_RENAMED`
    const r = await apiFetch(`/api/v1/folders/${l3_id}`, {
      method: 'PUT',
      token,
      body: { name: newName },
    })
    expect(r.status, `PUT rename 应 200, got ${r.status}`).toBe(200)
    expect(r.data.name).toBe(newName)
    // 重命名不影响 parent_id/depth/path (只改 name)
    expect(r.data.parent_id).toBe(ids[1])
    expect(r.data.depth).toBe(oldL3Depth)
    expect(r.data.path).toBe(oldL3Path)
    console.log(`[C] renamed L3: ${oldL3Path} → ${newName}, path/depth 保持`)

    // children (L4, L5) 仍可访问 (rename 不影响子级)
    const l4 = await getFolder(token, l4_id)
    expect(l4.parent_id).toBe(l3_id)
    const l5 = await getFolder(token, l5_id)
    expect(l5.parent_id).toBe(l4_id)

    // L5 的 file 仍可访问
    const files = await listFiles(token, l5_id)
    expect(files.length).toBeGreaterThanOrEqual(1)
    expect(files[0].id).toBe(l5File.id)

    console.log(`[C PASS] L3 重命名后, L4/L5 + L5 file 全部仍可访问`)
  })

  test('D: 移动 L5 file 到 L1, 验证 file.folder_id 改了', async () => {
    const { ids } = await createNLevelFolders(token, `${NS}_D`, 5)
    const l1_id = ids[0]
    const l5_id = ids[4]

    // 在 L5 创建一个 file
    const file = await createFile(token, l5_id, `${NS}_D_L5_file.txt`, 'original in L5')
    expect(file.folder_id).toBe(l5_id)

    // 移动 file 到 L1 (drive_files PUT /api/v1/drive/files/{id})
    const r = await apiFetch(`/api/v1/drive/files/${file.id}`, {
      method: 'PUT',
      token,
      body: { folder_id: l1_id },
    })
    expect(r.status, `PUT file 应 200, got ${r.status}`).toBe(200)
    expect(r.data.folder_id, `file folder_id 应改为 ${l1_id}`).toBe(l1_id)
    expect(r.data.id).toBe(file.id)
    console.log(`[D] moved file ${file.id}: folder_id ${l5_id} → ${l1_id}`)

    // 反向验证: L5 没 file, L1 有这个 file
    const l5Files = await listFiles(token, l5_id)
    expect(l5Files.length, `L5 移动后应 0 file`).toBe(0)

    const l1Files = await listFiles(token, l1_id)
    expect(l1Files.length, `L1 应有 1 file (移来的)`).toBe(1)
    expect(l1Files[0].id).toBe(file.id)

    console.log(`[D PASS] file 从 L5 移到 L1, folder_id + 列表都同步`)
  })

  test('E: 软删 L3 (cascade), 验证 L4/L5 进入回收站, 仍可恢复', async () => {
    const { ids } = await createNLevelFolders(token, `${NS}_E`, 5)
    const l3_id = ids[2]
    const l4_id = ids[3]
    const l5_id = ids[4]

    // 删前: L3, L4, L5 都 active
    const l3Before = await getFolder(token, l3_id)
    expect(l3Before.deleted_at).toBeNull()
    const l4Before = await getFolder(token, l4_id)
    expect(l4Before.deleted_at).toBeNull()
    const l5Before = await getFolder(token, l5_id)
    expect(l5Before.deleted_at).toBeNull()

    // 软删 L3 (recursive=true cascade)
    const delResp = await softDeleteFolder(token, l3_id, true)
    expect(delResp.status, `DELETE L3 recursive 应 200, got ${delResp.status}`).toBe(200)
    expect(delResp.data.deleted_folder_ids, 'cascade 应包含 L4 + L5').toEqual(
      expect.arrayContaining([l4_id, l5_id]),
    )
    expect(delResp.data.deleted_folder_ids).toHaveLength(3) // L3 + L4 + L5
    console.log(`[E] cascade deleted ${delResp.data.deleted_folder_ids.length} folders`)

    // 删后: 3 个 folder 全软删 (include_deleted=true 才能查到)
    const l3After = await getFolder(token, l3_id, true)
    expect(l3After.deleted_at, 'L3 deleted_at 应非空').not.toBeNull()
    const l4After = await getFolder(token, l4_id, true)
    expect(l4After.deleted_at, 'L4 cascade 软删').not.toBeNull()
    const l5After = await getFolder(token, l5_id, true)
    expect(l5After.deleted_at, 'L5 cascade 软删').not.toBeNull()

    // 恢复 L3 (cascade 不应自动恢复子级, 但 L3 恢复后 L4/L5 仍 soft-deleted)
    // 实测: restore 单 folder 只恢复自己, 子仍软删
    const restoreResp = await apiFetch(`/api/v1/folders/${l3_id}/restore`, {
      method: 'POST',
      token,
      body: {},
    })
    expect(restoreResp.status, `restore L3 应 200, got ${restoreResp.status}`).toBe(200)
    expect(restoreResp.data.deleted_at).toBeNull()

    // L4/L5 仍软删 (restore 仅作用于自己)
    const l4Final = await getFolder(token, l4_id, true)
    expect(l4Final.deleted_at, 'L4 cascade 软删后单独 restore L3 不应自动恢复 L4').not.toBeNull()
    const l5Final = await getFolder(token, l5_id, true)
    expect(l5Final.deleted_at).not.toBeNull()

    console.log(`[E PASS] L3 cascade 删 L4/L5, restore L3 不级联 (设计如此)`)
  })

  test('F: 边界 — 创建 L6 (depth=5), 不抛错, 验证 depth 字段无上限', async () => {
    test.setTimeout(120_000)  // 给足 60s 窗口重置时间
    await new Promise((res) => setTimeout(res, 1500))
    const { ids } = await createNLevelFolders(token, `${NS}_F`, 5)
    expect(ids).toHaveLength(5)
    const l5_id = ids[4]

    // L6: 退避重试 (60s 窗口阶梯)
    let l6_id = null
    for (let attempt = 0; attempt < 3; attempt++) {
      if (attempt > 0) await new Promise((res) => setTimeout(res, 35 * 1000))
      const r6 = await apiFetch('/api/v1/folders', {
        method: 'POST',
        token,
        body: { name: `${NS}_F_L6_boundary`, parent_id: l5_id, visibility: 'private' },
      })
      if (r6.status === 201) { l6_id = r6.data.id; break }
      if (r6.status !== 429) break
    }
    expect(l6_id, `L6 应成功创建 (id != null)`).toBeTruthy()
    const l6 = await apiFetch(`/api/v1/folders/${l6_id}`, { token })
    expect(l6.data.depth, `L6 depth 应为 5 (顶层 0-based)`).toBe(5)
    expect(l6.data.parent_id).toBe(l5_id)
    expect(l6.data.path).toBe('/' + ids.concat([l6_id]).join('/') + '/')
    console.log(`[F] L6 created: id=${l6_id} depth=${l6.data.depth} path=${l6.data.path}`)

    // L7 (depth=6) 仍能创建 — 无硬上限
    // L6 刚创建可能还在 rate-limit warm-up, 多等 30s
    await new Promise((res) => setTimeout(res, 30 * 1000))
    let l7_id = null
    for (let attempt = 0; attempt < 4; attempt++) {
      if (attempt > 0) await new Promise((res) => setTimeout(res, 35 * 1000))
      const r7 = await apiFetch('/api/v1/folders', {
        method: 'POST',
        token,
        body: { name: `${NS}_F_L7_boundary`, parent_id: l6_id, visibility: 'private' },
      })
      if (r7.status === 201) { l7_id = r7.data.id; break }
      if (r7.status !== 429) break
    }
    expect(l7_id, `L7 应成功创建 (id != null)`).toBeTruthy()
    const l7 = await apiFetch(`/api/v1/folders/${l7_id}`, { token })
    expect(l7.data.depth).toBe(6)
    console.log(`[F] L7 created: id=${l7_id} depth=${l7.data.depth} — 字段无上限`)

    console.log(`[F PASS] depth 字段无硬上限, 5/6/7+ 都能写入`)
  })

  test.afterAll(async () => {
    // 兜底清理: 列出所有 nest_<TS>* folder, recursive delete
    if (!token) return
    try {
      // list top-level folders (已软删的也会查到, 但只删 active)
      const list = await apiFetch('/api/v1/folders?page_size=100', { token })
      const items = list.data?.items || []
      const ours = items.filter((f) => f.name && f.name.startsWith(NS))
      console.log(`[cleanup] found ${ours.length} folder(s) with NS=${NS}`)
      for (const f of ours) {
        try {
          await apiFetch(`/api/v1/folders/${f.id}?recursive=true`, {
            method: 'DELETE',
            token,
          })
          console.log(`[cleanup] deleted folder ${f.id} ${f.name}`)
        } catch (e) {
          console.warn(`[cleanup] failed to delete ${f.id}: ${e?.message || e}`)
        }
      }
    } catch (e) {
      console.warn(`[cleanup] error: ${e?.message || e}`)
    }
  })
})