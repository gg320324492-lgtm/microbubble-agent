// ZB-2 Part D 七条终验 (真实 HTTP, A=cismoke B=zb1probe)
const BASE = 'http://localhost:8000/api/v1'
const out = {}
const login = async (u, p) => {
  const r = await fetch(BASE + '/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: u, password: p }) })
  const j = await r.json()
  return { token: j.access_token, id: j.user?.id }
}
const req = async (tok, method, path, opts = {}) => {
  const headers = { Authorization: 'Bearer ' + tok }
  let body
  if (opts.json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(opts.json) }
  if (opts.form) body = opts.form
  const r = await fetch(BASE + path, { method, headers, body })
  if (opts.raw) return { status: r.status }
  return { status: r.status, data: await r.json().catch(() => null) }
}
const search = async (tok, kw) => {
  const r = await req(tok, 'GET', `/drive/files?search=${encodeURIComponent(kw)}&include_subfolders=true&page_size=100`)
  return (r.data?.items ?? []).map((i) => ({ id: i.id, name: i.file_name, visibility: i.visibility }))
}

const A = await login('cismoke', 'CiSmoke2026')
const B = await login('zb1probe', 'Zb1Probe2026!')
out.a = A.id; out.b = B.id

// 找 backups/ 根
const tree = await req(A.token, 'GET', '/folders/tree?scope=all&max_depth=1')
const walk = (nodes) => { for (const n of nodes ?? []) { if (String(n.name).trim().toLowerCase() === 'backups') return n; const h = walk(n.children); if (h) return h } return null }
const root = walk(tree.data?.tree)

// #1 A 走真实上传 (multipart, folder_id=backups, 不传 visibility = 新桌面行为等价)
const form = new FormData()
form.append('file', new Blob([Buffer.from('MNBBK1-zb2-final-check-' + Date.now())]), `zb2-final.mnbbak.key.json`)
form.append('filename', `zb2-final.mnbbak.key.json`)
form.append('storage_mode', 'drive')
form.append('folder_id', String(root.id))
const up = await req(A.token, 'POST', '/drive/files/upload', { form })
out['#1_upload'] = { status: up.status, id: up.data?.id, visibility: up.data?.visibility, folderId: root.id }

// #2 B 对该文件: 列表/搜索不可见 + 直连下载 404
const kw = 'zb2-final'
const bSeen = await search(B.token, kw)
const bDl = await req(B.token, 'GET', `/drive/files/${up.data.id}/download`, { raw: true })
out['#2_B_view'] = { searchHits: bSeen.length, directDownload: bDl.status }

// #6 存量 2829-2844: B 不可见不可下 (抽 2841 容器 + 2842 key 代表)
const bListAll = await search(B.token, 'workbench-20260929')
const bDlOld = await req(B.token, 'GET', '/drive/files/2842/download', { raw: true })
out['#6_legacy_rows'] = { bSeenCount: bListAll.length, bDownloadKey2842: bDlOld.status }

// #7 区外零回归: A 上传普通 csv 到区外文件夹 → B 可见可下
const mkF = await req(A.token, 'POST', '/folders', { json: { name: `zb2-open-${Date.now()}`, parent_id: null, visibility: 'team' } })
const pf = new FormData()
pf.append('file', new Blob([Buffer.from('a,b\n1,2')]), 'zb2-open.csv')
pf.append('filename', 'zb2-open.csv')
pf.append('storage_mode', 'drive')
pf.append('folder_id', String(mkF.data.id))
const plain = await req(A.token, 'POST', '/drive/files/upload', { form: pf })
const pSeen = await search(B.token, 'zb2-open')
const pDl = await req(B.token, 'GET', `/drive/files/${plain.data.id}/download`, { raw: true })
out['#7_outside'] = { visibility: plain.data?.visibility, bSeen: pSeen.length, bDownload: pDl.status }

// A 自己: 新备份可见可下 (owner 语义)
const aSeen = await search(A.token, kw)
const aDl = await req(A.token, 'GET', `/drive/files/${up.data.id}/download`, { raw: true })
out['extra_A_view'] = { searchHits: aSeen.length, download: aDl.status }

console.log(JSON.stringify(out, null, 2))
