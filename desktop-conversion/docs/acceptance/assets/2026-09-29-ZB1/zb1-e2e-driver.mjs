// ZB-1 Part D 双账号实证驱动 (对本地栈 http://localhost:8000, 真实后端)
// 用法: node zb1-e2e.mjs <pre|post|downgrade-check>
//   pre            — 迁移+部署前: A 上传探针到 backups/, B 可见可下 (漏洞在证)
//   post           — 迁移+部署后: B 不可见/404, A 可见可下, 区外零回归
//   downgrade-check — downgrade 后 B 重可见 / upgrade 后再隐身 (可逆实证)
import { writeFileSync } from 'node:fs'

const BASE = 'http://localhost:8000/api/v1'
const MODE = process.argv[2]
if (!MODE) {
  console.error('usage: node zb1-e2e.mjs <pre|post|downgrade-check>')
  process.exit(2)
}

const out = { mode: MODE, steps: [] }
const step = (name, data) => {
  out.steps.push({ name, ...(typeof data === 'object' ? data : { value: data }) })
  console.log(`[${name}]`, JSON.stringify(data))
}

async function api(method, path, { token, form, json, raw } = {}) {
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`
  let body
  if (form) {
    body = form
  } else if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  }
  const res = await fetch(BASE + path, { method, headers, body })
  const status = res.status
  if (raw) {
    const buf = Buffer.from(await res.arrayBuffer())
    return { status, size: buf.length, head: buf.subarray(0, 24).toString('hex') }
  }
  let data = null
  try { data = await res.json() } catch { /* 空 body */ }
  return { status, data }
}

async function login(username, password) {
  const r = await api('POST', '/auth/login', { json: { username, password } })
  if (r.status !== 200 || !r.data?.access_token) throw new Error(`login ${username} failed: ${r.status} ${JSON.stringify(r.data).slice(0, 200)}`)
  return { token: r.data.access_token, user: r.data.user }
}

// 在 A 的网盘找 backups/ 根 (tree scope=all); 不存在则建 (等价桌面端 ensure 行为)
async function findBackupsRoot(token) {
  const r = await api('GET', '/folders/tree?scope=all&max_depth=1', { token })
  const walk = (nodes) => {
    for (const n of nodes ?? []) {
      if (String(n.name ?? '').trim().toLowerCase() === 'backups') return n
      const hit = walk(n.children ?? [])
      if (hit) return hit
    }
    return null
  }
  const root = walk(r.data?.tree ?? r.data?.folders ?? r.data)
  if (root) return root
  const mk = await api('POST', '/folders', { token, json: { name: 'backups', parent_id: null, visibility: 'team' } })
  if (mk.status >= 300) throw new Error('create backups root failed: ' + JSON.stringify(mk.data).slice(0, 200))
  return mk.data
}

async function ensureSubfolder(token, parentId, name) {
  // 先建/复用 backups/ 下名为 name 的子目录 (幂等: 重名允许, 直接新建也能用)
  const r = await api('POST', '/folders', {
    token,
    json: { name, parent_id: parentId, visibility: 'team' }
  })
  return r.data
}

async function uploadFile(token, folderId, filename, bytes, { visibility } = {}) {
  const form = new FormData()
  form.append('file', new Blob([bytes]), filename)
  form.append('filename', filename)
  form.append('storage_mode', 'drive')
  if (folderId != null) form.append('folder_id', String(folderId))
  if (visibility) form.append('visibility', visibility)
  const r = await api('POST', '/drive/files/upload', { token, form })
  if (r.status !== 201) throw new Error(`upload ${filename} -> ${r.status} ${JSON.stringify(r.data).slice(0, 200)}`)
  return r.data
}

async function searchOne(token, keyword) {
  const r = await api('GET', `/drive/files?search=${encodeURIComponent(keyword)}&include_subfolders=true&page_size=50`, { token })
  return (r.data?.items ?? []).map((i) => ({ id: i.id, name: i.file_name, visibility: i.visibility }))
}

const KEY_BODY = Buffer.from(JSON.stringify({ v: 1, k: 'zb1-probe-key-' + MODE + '-' + Date.now() }))
const CONTAINER_BODY = Buffer.from('MNBBK1-zb1-probe-container-' + MODE + '-' + 'x'.repeat(200))

// ==========================================================================
if (MODE === 'pre') {
  const A = await login('cismoke', 'CiSmoke2026')
  step('A-login', { username: 'cismoke', id: A.user.id })

  // B 账号: 由 A 经 POST /members 创建 (扁平化: 任意成员可建); 已存在则复用
  const mk = await api('POST', '/members', {
    token: A.token,
    json: { username: 'zb1probe', name: 'ZB1 Probe', password: 'Zb1Probe2026!', grade: '测试', role: 'member' }
  })
  step('B-create', { status: mk.status, id: mk.data?.id ?? null, conflict: mk.status === 409 })
  const B0 = await login('zb1probe', 'Zb1Probe2026!')
  step('B-login', { id: B0.user.id })

  // 真实形态漏洞在证: ZB 演练产物 (根目录, 无 backups/ 文件夹) 当前 B 可见可下
  // (演练行 id 2841=容器 2842=key.json, created_by=1458, 根目录, team)
  const drillKey = await api('GET', '/drive/files/2842/download', { token: B0.token, raw: true })
  const drillSeen = await searchOne(B0.token, 'workbench-20260929')
  step('REAL-SHAPE-vuln-pre', {
    drillKeyDownloadByB: drillKey.status,
    drillRowsSeenByB: drillSeen.length,
    note: '演练产物在根目录(桌面端 uploadFile 丢弃目录信息), 非工单假设的 backups/ 文件夹'
  })

  // 规范形态: A 建 backups/ 根 (桌面端未来行为等价) + 上传探针
  const root = await findBackupsRoot(A.token)
  step('backups-root', { id: root.id, name: root.name })

  // A 上传 探针容器 + key.json 到 backups/ (不传 visibility = 桌面端同形态)
  const c = await uploadFile(A.token, root.id, `zb1-probe-${MODE}.mnbbak`, CONTAINER_BODY)
  const k = await uploadFile(A.token, root.id, `zb1-probe-${MODE}.mnbbak.key.json`, KEY_BODY)
  step('A-upload', { container: { id: c.id, visibility: c.visibility }, key: { id: k.id, visibility: k.visibility } })

  // B 视角 (漏洞在证): 搜索可见 + 直接下载 200
  const seenByB = await searchOne(B0.token, 'zb1-probe')
  const dlC = await api('GET', `/drive/files/${c.id}/download`, { token: B0.token, raw: true })
  const dlK = await api('GET', `/drive/files/${k.id}/download`, { token: B0.token, raw: true })
  step('B-view-_PRE-MIGRATION_', { searchSeen: seenByB, downloadContainer: dlC.status, downloadKey: dlK.status })

  // A 自己可见可下
  const seenByA = await searchOne(A.token, 'zb1-probe')
  const dlA = await api('GET', `/drive/files/${c.id}/download`, { token: A.token, raw: true })
  step('A-view', { searchSeen: seenByA.length, download: dlA.status })
  writeFileSync('C:/Users/pc/AppData/Local/Temp/zb1-e2e/probe-ids.json', JSON.stringify({ c: c.id, k: k.id }))
}

if (MODE === 'post') {
  const A = await login('cismoke', 'CiSmoke2026')
  const B = await login('zb1probe', 'Zb1Probe2026!')
  step('logins', { a: A.user.id, b: B.user.id })
  const root = await findBackupsRoot(A.token)

  // 新上传 (部署后代码): 不传 visibility → 服务端强制 private
  const c = await uploadFile(A.token, root.id, `zb1-post-${Date.now()}.mnbbak`, CONTAINER_BODY)
  step('A-upload-new', { id: c.id, visibility: c.visibility })

  const seenByB = await searchOne(B.token, 'zb1-')
  const dlNew = await api('GET', `/drive/files/${c.id}/download`, { token: B.token, raw: true })
  step('B-view', { searchSeen: seenByB, downloadNew: dlNew.status })

  // 旧探针 (迁移已刷 private) 同验
  const ids = JSON.parse(await import('node:fs').then((m) => m.readFileSync('C:/Users/pc/AppData/Local/Temp/zb1-e2e/probe-ids.json', 'utf8')))
  const dlOldC = await api('GET', `/drive/files/${ids.c}/download`, { token: B.token, raw: true })
  const dlOldK = await api('GET', `/drive/files/${ids.k}/download`, { token: B.token, raw: true })
  step('B-direct-download-old-probes', { container: dlOldC.status, key: dlOldK.status })

  // A 自己可见可下 (新旧都是)
  const dlNewA = await api('GET', `/drive/files/${c.id}/download`, { token: A.token, raw: true })
  const dlOldCA = await api('GET', `/drive/files/${ids.c}/download`, { token: A.token, raw: true })
  step('A-view', { newDownload: dlNewA.status, oldDownload: dlOldCA.status })

  // 区外零回归: A 上传普通文件到区外文件夹 → B 可见可下
  const mkF = await api('POST', '/folders', { token: A.token, json: { name: `zb1-open-${Date.now()}`, parent_id: null, visibility: 'team' } })
  const openFolder = mkF.data
  const plain = await uploadFile(A.token, openFolder.id, `zb1-open-${Date.now()}.csv`, Buffer.from('a,b\n1,2'))
  const plainSeenByB = await searchOne(B.token, 'zb1-open-')
  const dlPlain = await api('GET', `/drive/files/${plain.id}/download`, { token: B.token, raw: true })
  step('outside-zero-regression', {
    plainVisibility: plain.visibility,
    bSeen: plainSeenByB.map((x) => ({ id: x.id, visibility: x.visibility })),
    bDownload: dlPlain.status
  })
}

if (MODE === 'downgrade-check') {
  const A = await login('cismoke', 'CiSmoke2026')
  const B = await login('zb1probe', 'Zb1Probe2026!')
  const seenByB = await searchOne(B.token, 'zb1-probe')
  step('B-view', { searchSeen: seenByB.map((x) => ({ id: x.id, visibility: x.visibility })) })
  const ids = JSON.parse(await import('node:fs').then((m) => m.readFileSync('C:/Users/pc/AppData/Local/Temp/zb1-e2e/probe-ids.json', 'utf8')))
  const dl = await api('GET', `/drive/files/${ids.k}/download`, { token: B.token, raw: true })
  step('B-direct-download-key', { status: dl.status })
  void A
}

writeFileSync('C:/Users/pc/AppData/Local/Temp/zb1-e2e/result-' + MODE + '.json', JSON.stringify(out, null, 2))
console.log('RESULT-SAVED')
