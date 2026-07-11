/**
 * tests/visual/desktop/drive-folder-cascade-delete-2026-07-11.spec.mjs
 *
 * 端到端验证 v2.16 (2026-07-11) — folder 级联软删除
 *
 * 用户决策: "有子文件夹的话也可以直接删除" — 旧 v2.14 路径遇到有子 folder
 *   时直接 422 "folder 下还有 N 个未删的子 folder, 请先清理", 用户体验差.
 *   v2.16 引入 ?recursive=true, frontend smart confirm 弹 2 按钮:
 *     取消 / 全部移入回收站 (30 天保留期可整体恢复).
 *
 * 关键断言:
 * 1) 右键 parent folder → 弹 FolderContextMenu
 * 2) 点「删除」→ 弹 cascade confirm (文案含 "全部移入回收站")
 * 3) 点「全部移入回收站」→ toast 成功 + 树重建 + DELETE 走 ?recursive=true
 * 4) 验证: GET /folders/tree 不再包含 parent (软删 30 天内进回收站)
 * 5) 验证: GET /folders/tree 也不再包含 child (级联)
 *
 * 前置:
 *   - BASE_URL 指向部署 (默认 https://agent.mnb-lab.cn)
 *   - TEST_TOKEN 通过 curl /auth/login (xiaoqi_testbot / testbot_pass_2026)
 *   - 父 folder `v216_cascade_test_parent` (id 725) + 子 folder `..._child` (id 726) 已存在
 *
 * 运行:
 *   TEST_TOKEN=$(curl -sk -X POST $BASE_URL/api/v1/auth/login \
 *     -H 'Content-Type: application/json' \
 *     -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' | jq -r .access_token) \
 *     npx playwright test tests/visual/desktop/drive-folder-cascade-delete-2026-07-11.spec.mjs
 */

import { test, expect } from '@playwright/test'
import axios from 'axios'

const BASE_URL = process.env.BASE_URL || 'https://agent.mnb-lab.cn'
const TEST_TOKEN = process.env.TEST_TOKEN || ''
const PARENT_NAME = 'v216_cascade_test_parent'
const CHILD_NAME = 'v216_cascade_test_child'

const api = () => axios.create({
  baseURL: BASE_URL,
  headers: { Authorization: `Bearer ${TEST_TOKEN}` },
  timeout: 15000,
})

function findByName(nodes, name) {
  for (const n of (nodes || [])) {
    if (n.name === name) return n
    if (n.children?.length) {
      const f = findByName(n.children, name)
      if (f) return f
    }
  }
  return null
}

async function ensureFolders() {
  /**
   * 幂等创建 parent + child. 若已存在直接 reuse.
   */
  const treeResp = await api().get('/api/v1/folders/tree')
  let parent = findByName(treeResp.data.tree || [], PARENT_NAME)

  if (!parent) {
    const parentResp = await api().post('/api/v1/folders', { name: PARENT_NAME, visibility: 'team' })
    parent = { id: parentResp.data.id }
  }

  // 找或创建 child
  let childId = null
  if (parent.children?.length) {
    const found = parent.children.find(c => c.name === CHILD_NAME)
    if (found) childId = found.id
  }
  if (!childId) {
    const childResp = await api().post('/api/v1/folders', {
      name: CHILD_NAME, parent_id: parent.id, visibility: 'team',
    })
    childId = childResp.data.id
  }
  return { parentId: parent.id, childId }
}

async function setupAuth(page) {
  await page.context().addCookies([{
    name: 'access_token', value: TEST_TOKEN,
    domain: new URL(BASE_URL).hostname, path: '/',
    httpOnly: false, secure: true, sameSite: 'None',
  }])
  await page.addInitScript((token) => {
    localStorage.setItem('access_token', token)
  }, TEST_TOKEN)
}

test.describe('drive-folder-cascade-delete-v2.16 端到端', () => {
  let parentId, childId

  test.beforeAll(async () => {
    if (!TEST_TOKEN) throw new Error('TEST_TOKEN env var required')
    const ids = await ensureFolders()
    parentId = ids.parentId
    childId = ids.childId
    console.log(`[setup] parent_id=${parentId} child_id=${childId}`)
    expect(parentId).toBeGreaterThan(0)
    expect(childId).toBeGreaterThan(0)
  })

  test('A: 父 folder 含 1 个子 folder, 右键级联删除 → 全部进回收站 (无 422)', async ({ page }) => {
    // === 拦截网络请求 ===
    const errors = []
    const folderRequests = []
    page.on('pageerror', (e) => errors.push(String(e)))
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(`[console.error] ${msg.text()}`)
    })
    page.on('request', (req) => {
      const m = req.url().match(/\/api\/v1\/folders\/(\d+)(?:\?[^/]*)?$/)
      if (m && req.method() === 'DELETE') {
        folderRequests.push({ url: req.url(), method: req.method(), params: new URL(req.url()).search })
      }
    })
    page.on('response', (resp) => {
      const m = resp.url().match(/\/api\/v1\/folders\/(\d+)/)
      if (m && resp.request().method() === 'DELETE') {
        folderRequests.push({ url: resp.url(), method: 'DELETE', status: resp.status() })
      }
    })

    await setupAuth(page)
    await page.goto(`${BASE_URL}/drive`, { waitUntil: 'networkidle' })
    // 等 Pinia store fetchTree 完成 + DOM 渲染
    await page.waitForTimeout(5000)

    // === 把 parent folder 滚到视图内 ===
    // 真实 class: folder-tree-node-name (无 drive- 前缀)
    const parentText = page.locator(`.folder-tree-node-name:has-text("${PARENT_NAME}")`).first()
    await expect(parentText).toHaveCount(1, undefined, { timeout: 10_000 })
    await parentText.scrollIntoViewIfNeeded()

    // 找到外层 row (用于右键点击)
    const parentRow = page.locator('.folder-tree-node-row', {
      has: page.locator(`.folder-tree-node-name:has-text("${PARENT_NAME}")`),
    }).first()

    // === 右键触发 contextmenu ===
    await parentRow.click({ button: 'right' })

    // === 等待 FolderContextMenu 弹窗 ===
    const menu = page.locator('.folder-context-menu')
    await expect(menu).toBeVisible({ timeout: 5000 })

    // === 点"删除"菜单项 ===
    const deleteOption = page.locator('.folder-context-menu-item:has-text("删除")').first()
    await expect(deleteOption).toBeVisible()
    await deleteOption.click()

    // === 验证 cascade confirm 弹出 ===
    const confirmDialog = page.locator('.el-message-box')
    await expect(confirmDialog).toBeVisible({ timeout: 5000 })
    const dialogText = await confirmDialog.innerText()
    console.log('[confirm dialog text]:', dialogText)

    // 文案必须含 "全部移入回收站" + 类似"级联"或 child 计数信息
    expect(dialogText, 'confirm 文案应含 "全部移入回收站"').toContain('全部移入回收站')
    // 至少提子项数量或级联相关
    expect(
      dialogText.includes('子 folder') || dialogText.includes('文件') || dialogText.includes('级联'),
      'confirm 文案应提子项统计'
    ).toBe(true)

    // === 点确认按钮 (「全部移入回收站」) ===
    const confirmBtn = confirmDialog.locator('.el-button--primary').first()
    await expect(confirmBtn).toBeVisible()
    await confirmBtn.click()

    // === 等 toast + fetchTree ===
    await page.waitForTimeout(3000)

    // === 关键断言 1: DELETE 走 ?recursive=true (后端走 cascade 路径) ===
    const deleteCalls = folderRequests.filter(c => c.method === 'DELETE')
    console.log('[DELETE calls captured]:', JSON.stringify(deleteCalls))
    const targetDelete = deleteCalls.find(c => c.url.includes(`/folders/${parentId}`))
    expect(targetDelete, `应触发 DELETE /folders/${parentId}`).toBeTruthy()
    expect(
      targetDelete.params || targetDelete.url,
      'URL 必须含 recursive=true 查询参数'
    ).toContain('recursive=true')

    // === 关键断言 2: 没有 422 错误冒泡 ===
    const has422 = errors.some(e => e.includes('422') || e.includes('Unprocessable Content'))
    expect(has422, `不应再出现 422 错误, console errors: ${errors.join('\n')}`).toBe(false)

    // === 关键断言 3: 后端 parent + child 都已软删 ===
    const parentAfter = await api().get(`/api/v1/folders/${parentId}?include_deleted=true`)
    expect(parentAfter.data.deleted_at, 'parent 应被软删 (deleted_at != null)').not.toBeNull()

    const childAfter = await api().get(`/api/v1/folders/${childId}?include_deleted=true`)
    expect(childAfter.data.deleted_at, 'child 应被级联软删').not.toBeNull()

    // === 关键断言 4: 验证 GET /folders/tree 已不含 parent (cascade 生效) ===
    // 软删后 list_folders 默认 include_deleted=False, 应已不在树中
    const treeAfter = await api().get('/api/v1/folders/tree')
    const hasParent = findByName(treeAfter.data.tree || [], PARENT_NAME)
    expect(hasParent, 'parent 应已从 active tree 消失 (进回收站)').toBeNull()

    console.log(`[E2E PASS] parent=${parentId} + child=${childId} 级联软删成功, recursive=true 生效, 0 个 422 错误`)
  })

  test('B: 父 folder 无子时, recursive 未传 → DELETE 默认路径 200/204 成功', async ({ page: _ }) => {
    // 单独验证旧路径 (无 children, recursive 不传) 仍能成功
    const createResp = await api().post('/api/v1/folders', {
      name: `v216_isolated_${Date.now()}`, visibility: 'team',
    })
    const isolatedId = createResp.data.id

    try {
      const resp = await api().delete(`/api/v1/folders/${isolatedId}`)
      expect([200, 204]).toContain(resp.status)
      console.log(`[B PASS] isolated folder ${isolatedId} 旧路径删除成功 (status=${resp.status})`)
    } finally {
      // 兜底清理 (若失败)
      try { await api().delete(`/api/v1/folders/${isolatedId}?recursive=true`) } catch (e) { /* ignore */ }
    }
  })
})
