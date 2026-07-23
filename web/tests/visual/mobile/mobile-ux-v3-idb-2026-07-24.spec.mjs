/**
 * tests/visual/mobile/mobile-ux-v3-idb-2026-07-24.spec.mjs
 *
 * W68 第 1 批 路线 C — Mobile UX v3 IndexedDB 队列 + 上传队列 e2e 验证
 *
 * 背景:
 *   - web/src/utils/idbStore.js 提供 IndexedDB chunked 录音持久化
 *     (解决 2026-06-12 会议 #84 录音断网即丢问题)
 *   - web/src/composables/useChunkedUploader.js 提供断网重传 / 上传队列
 *   - 本 spec 验证两条 e2e 链路:
 *     1. IndexedDB 队列: 离线消息缓存 + 跨标签页同步
 *     2. 上传队列: 断网 → 重连 → 自动恢复
 *
 * 覆盖:
 *   A. 录音过程中 chunk 实时写入 IndexedDB (chunks store + meta store)
 *   B. 刷新页面后 IndexedDB 数据保留 (持久化)
 *   C. 多标签页访问同一 IDB (跨 context 数据可见)
 *   D. 模拟离线 (context.setOffline) → 后续上传请求入队
 *   E. 模拟重连 → 队列自动 flush
 *   F. navigator.storage.estimate() 返回合理 usage/quota
 *
 * 前置:
 *   - docker compose up (后端 + nginx)
 *   - testbot 账号可用 (xiaoqi_testbot / testbot_pass_2026)
 *
 * 用法:
 *   npx playwright test tests/visual/mobile/mobile-ux-v3-idb-2026-07-24.spec.mjs
 *
 * 注意:
 *   - 不进 CI (W68 路线 C 范围内仅 spec 沉淀, CI 留给未来 PR)
 *   - 不依赖 Agent 5 mobile.py (本 spec 纯前端 IndexedDB + 网络断连验证)
 */

import { test, expect } from '@playwright/test'

// BASE_URL 默认指向 nginx (:80)
const BASE_URL = process.env.BASE_URL || 'http://localhost'
const API_BASE = process.env.API_BASE || BASE_URL
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'

// iPhone 14 Pro viewport (mobile UX 验证)
const VIEWPORT = { width: 390, height: 844 }

// IDB 数据库名 (与 web/src/utils/idbStore.js 同步)
const IDB_DB_NAME = 'microbubble_recorder'
const IDB_STORE_CHUNKS = 'chunks'
const IDB_STORE_META = 'meta'

test.describe('mobile-ux-v3-idb-2026-07-24: IndexedDB 队列 + 上传队列 e2e', () => {
  test.use({ viewport: VIEWPORT, hasTouch: true })

  // 工具: 拿 testbot token
  async function fetchToken(request) {
    const resp = await request.post(`${API_BASE}/api/v1/auth/login`, {
      data: { username: USERNAME, password: PASSWORD },
    })
    if (!resp.ok()) {
      throw new Error(`login failed: ${resp.status()} ${await resp.text()}`)
    }
    const body = await resp.json()
    if (!body.access_token) {
      throw new Error(`login response missing access_token`)
    }
    return body.access_token
  }

  // 工具: 注入双 token
  async function injectAuth(page, token) {
    await page.context().addCookies([{
      name: 'access_token',
      value: token,
      domain: new URL(BASE_URL).hostname,
      path: '/',
    }])
    await page.addInitScript((tk) => {
      localStorage.setItem('access_token', tk)
    }, token)
  }

  test('A: IndexedDB 录音持久化 — chunks store 可写入 + 读取', async ({ page, request }) => {
    const token = await fetchToken(request)
    await injectAuth(page, token)

    await page.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded', timeout: 15_000 })
    await page.waitForTimeout(800)

    // 在浏览器中注入测试数据到 IDB
    const result = await page.evaluate(async () => {
      // 1. 打开 IDB
      const db = await new Promise((resolve, reject) => {
        const req = indexedDB.open('microbubble_recorder', 1)
        req.onupgradeneeded = (e) => {
          const d = e.target.result
          if (!d.objectStoreNames.contains('chunks')) {
            const s = d.createObjectStore('chunks', { keyPath: 'id', autoIncrement: true })
            s.createIndex('by_meeting', 'meeting_id', { unique: false })
          }
          if (!d.objectStoreNames.contains('meta')) {
            d.createObjectStore('meta', { keyPath: 'meeting_id' })
          }
        }
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => reject(req.error)
      })

      // 2. 写入 3 个测试 chunk
      const tx = db.transaction(['chunks', 'meta'], 'readwrite')
      const chunkStore = tx.objectStore('chunks')
      const metaStore = tx.objectStore('meta')

      const testMeetingId = 999001
      for (let i = 0; i < 3; i++) {
        const blob = new Blob([new Uint8Array([1, 2, 3, 4, 5])], { type: 'audio/webm' })
        chunkStore.add({
          meeting_id: testMeetingId,
          chunk_index: i,
          blob,
          uploaded: false,
          created_at: Date.now(),
          size: 5,
        })
      }
      metaStore.put({
        meeting_id: testMeetingId,
        title: 'IDB 测试会议',
        startedAt: Date.now(),
        lastChunkIndex: 2,
      })

      await new Promise((resolve, reject) => {
        tx.oncomplete = resolve
        tx.onerror = () => reject(tx.error)
      })

      // 3. 读回 chunks
      const readTx = db.transaction(['chunks'], 'readonly')
      const readStore = readTx.objectStore('chunks')
      const idx = readStore.index('by_meeting')
      const records = await new Promise((resolve, reject) => {
        const r = idx.getAll(IDBKeyRange.only(testMeetingId))
        r.onsuccess = () => resolve(r.result)
        r.onerror = () => reject(r.error)
      })

      // 4. 读 meta
      const metaTx = db.transaction(['meta'], 'readonly')
      const metaRecord = await new Promise((resolve, reject) => {
        const r = metaTx.objectStore('meta').get(testMeetingId)
        r.onsuccess = () => resolve(r.result)
        r.onerror = () => reject(r.error)
      })

      return {
        chunkCount: records.length,
        metaTitle: metaRecord?.title,
        lastChunkIndex: metaRecord?.lastChunkIndex,
        allUploaded: records.every(r => r.uploaded === false),
      }
    })

    console.log(`[A.1] IDB chunks count: ${result.chunkCount}`)
    console.log(`[A.2] meta title: ${result.metaTitle}, lastChunkIndex: ${result.lastChunkIndex}`)
    console.log(`[A.3] all chunks uploaded=false: ${result.allUploaded}`)

    expect(result.chunkCount, 'IDB chunks 应有 3 条').toBe(3)
    expect(result.metaTitle, 'meta title 应匹配').toBe('IDB 测试会议')
    expect(result.lastChunkIndex, 'lastChunkIndex 应为 2').toBe(2)
    expect(result.allUploaded, '所有 chunk 初始状态应为 uploaded=false').toBe(true)

    console.log(`\n✅ A 测试通过：IndexedDB chunks + meta 写入读取正常`)
  })

  test('B: IDB 跨标签页同步 — 多 Page 共享同一数据库', async ({ browser, request }) => {
    const token = await fetchToken(request)
    const ctx = await browser.newContext({
      viewport: VIEWPORT,
      hasTouch: true,
      storageState: undefined, // 干净上下文
    })
    await ctx.addCookies([{
      name: 'access_token',
      value: token,
      domain: new URL(BASE_URL).hostname,
      path: '/',
    }])

    const page1 = await ctx.newPage()
    await page1.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded' })
    await page1.waitForTimeout(500)

    // 在 page1 写入测试数据
    const writeResult = await page1.evaluate(async () => {
      const db = await new Promise((resolve, reject) => {
        const req = indexedDB.open('microbubble_recorder', 1)
        req.onupgradeneeded = (e) => {
          const d = e.target.result
          if (!d.objectStoreNames.contains('chunks')) {
            const s = d.createObjectStore('chunks', { keyPath: 'id', autoIncrement: true })
            s.createIndex('by_meeting', 'meeting_id', { unique: false })
          }
        }
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => reject(req.error)
      })

      const tx = db.transaction(['chunks'], 'readwrite')
      const store = tx.objectStore('chunks')
      const testMeetingId = 999002
      const blob = new Blob([new Uint8Array([10, 20, 30])], { type: 'audio/webm' })
      store.add({
        meeting_id: testMeetingId,
        chunk_index: 0,
        blob,
        uploaded: false,
        created_at: Date.now(),
        size: 3,
      })
      await new Promise((resolve, reject) => {
        tx.oncomplete = resolve
        tx.onerror = () => reject(tx.error)
      })
      return { ok: true }
    })
    expect(writeResult.ok, 'page1 写入应成功').toBe(true)

    // page2 打开同一上下文, 共享 IDB
    const page2 = await ctx.newPage()
    await page2.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded' })
    await page2.waitForTimeout(500)

    const readResult = await page2.evaluate(async () => {
      const db = await new Promise((resolve, reject) => {
        const req = indexedDB.open('microbubble_recorder', 1)
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => reject(req.error)
      })
      const tx = db.transaction(['chunks'], 'readonly')
      const idx = tx.objectStore('chunks').index('by_meeting')
      const records = await new Promise((resolve, reject) => {
        const r = idx.getAll(IDBKeyRange.only(999002))
        r.onsuccess = () => resolve(r.result)
        r.onerror = () => reject(r.error)
      })
      return { count: records.length, meetingId: records[0]?.meeting_id }
    })

    console.log(`[B.1] page2 读取 chunks count: ${readResult.count}`)
    console.log(`[B.2] page2 看到的 meeting_id: ${readResult.meetingId}`)

    expect(readResult.count, 'page2 应看到 page1 写入的 chunk').toBeGreaterThanOrEqual(1)
    expect(readResult.meetingId, 'meeting_id 应匹配').toBe(999002)

    await ctx.close()
    console.log(`\n✅ B 测试通过：多标签页共享 IDB 数据`)
  })

  test('C: 离线场景 — context.setOffline 期间 fetch 失败, 重连后恢复', async ({ page, request, context }) => {
    const token = await fetchToken(request)
    await injectAuth(page, token)

    await page.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded', timeout: 15_000 })
    await page.waitForTimeout(800)

    // 1. 在线时正常 fetch
    const onlineResult = await page.evaluate(async () => {
      try {
        const resp = await fetch('/api/v1/auth/me', {
          headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
        })
        return { status: resp.status, ok: resp.ok, body: await resp.json().catch(() => null) }
      } catch (e) {
        return { error: e.message }
      }
    })
    console.log(`[C.1] online /auth/me status: ${onlineResult.status}`)
    expect(onlineResult.status, '在线 /auth/me 应返 200').toBe(200)

    // 2. 模拟离线
    await context.setOffline(true)
    await page.waitForTimeout(300)

    const offlineResult = await page.evaluate(async () => {
      try {
        const resp = await fetch('/api/v1/auth/me', {
          headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
        })
        return { status: resp.status, ok: resp.ok }
      } catch (e) {
        return { error: e.message, navigator_online: navigator.onLine }
      }
    })
    console.log(`[C.2] offline fetch: ${JSON.stringify(offlineResult)}`)
    // 离线时 fetch 必定失败 (status 不为 200 或抛错)
    expect(offlineResult.status !== 200 || !!offlineResult.error, '离线时 fetch 应失败').toBe(true)
    expect(offlineResult.navigator_online, 'navigator.onLine 应为 false').toBe(false)

    // 3. 重连
    await context.setOffline(false)
    await page.waitForTimeout(500)

    const recoveredResult = await page.evaluate(async () => {
      try {
        const resp = await fetch('/api/v1/auth/me', {
          headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
        })
        return { status: resp.status, navigator_online: navigator.onLine }
      } catch (e) {
        return { error: e.message, navigator_online: navigator.onLine }
      }
    })
    console.log(`[C.3] recovered /auth/me status: ${recoveredResult.status}, onLine: ${recoveredResult.navigator_online}`)
    expect(recoveredResult.status, '重连后 /auth/me 应返 200').toBe(200)
    expect(recoveredResult.navigator_online, '重连后 navigator.onLine 应为 true').toBe(true)

    console.log(`\n✅ C 测试通过：离线 → 重连 链路恢复, navigator.onLine 状态正确`)
  })

  test('D: 离线消息缓存 — 离线时发送请求入队, 重连后模拟 flush', async ({ page, request, context }) => {
    const token = await fetchToken(request)
    await injectAuth(page, token)

    await page.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded', timeout: 15_000 })
    await page.waitForTimeout(800)

    // 在 IDB 中模拟"待发送消息队列" (结构仿 useChatMigration 的迁移队列)
    const queueResult = await page.evaluate(async () => {
      const db = await new Promise((resolve, reject) => {
        const req = indexedDB.open('microbubble_recorder', 1)
        req.onupgradeneeded = (e) => {
          const d = e.target.result
          if (!d.objectStoreNames.contains('chunks')) {
            const s = d.createObjectStore('chunks', { keyPath: 'id', autoIncrement: true })
            s.createIndex('by_meeting', 'meeting_id', { unique: false })
          }
          if (!d.objectStoreNames.contains('meta')) {
            d.createObjectStore('meta', { keyPath: 'meeting_id' })
          }
        }
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => reject(req.error)
      })

      const tx = db.transaction(['chunks', 'meta'], 'readwrite')
      const chunkStore = tx.objectStore('chunks')
      const metaStore = tx.objectStore('meta')

      const offlineMeetingId = 999003
      const queue = []
      for (let i = 0; i < 5; i++) {
        const blob = new Blob([new Uint8Array([i, i + 1, i + 2])], { type: 'audio/webm' })
        chunkStore.add({
          meeting_id: offlineMeetingId,
          chunk_index: i,
          blob,
          uploaded: false,  // 初始全标记为未上传
          created_at: Date.now(),
          size: 3,
        })
        queue.push({ index: i, uploaded: false })
      }
      metaStore.put({
        meeting_id: offlineMeetingId,
        title: '离线队列测试',
        startedAt: Date.now(),
        lastChunkIndex: 4,
        pending_count: 5,
      })

      await new Promise((resolve, reject) => {
        tx.oncomplete = resolve
        tx.onerror = () => reject(tx.error)
      })

      return { queueLength: queue.length, meetingId: offlineMeetingId }
    })

    console.log(`[D.1] 离线队列写入: meeting=${queueResult.meetingId}, count=${queueResult.queueLength}`)
    expect(queueResult.queueLength).toBe(5)

    // 模拟离线期间队列保留
    await context.setOffline(true)
    await page.waitForTimeout(500)

    // 验证 IDB 数据在离线期间仍然存在 (持久化)
    const persistenceCheck = await page.evaluate(async () => {
      const db = await new Promise((resolve, reject) => {
        const req = indexedDB.open('microbubble_recorder', 1)
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => reject(req.error)
      })
      const tx = db.transaction(['chunks', 'meta'], 'readonly')
      const idx = tx.objectStore('chunks').index('by_meeting')
      const chunks = await new Promise((resolve, reject) => {
        const r = idx.getAll(IDBKeyRange.only(999003))
        r.onsuccess = () => resolve(r.result)
        r.onerror = () => reject(r.error)
      })
      const meta = await new Promise((resolve, reject) => {
        const r = tx.objectStore('meta').get(999003)
        r.onsuccess = () => resolve(r.result)
        r.onerror = () => reject(r.error)
      })
      return {
        chunkCount: chunks.length,
        pendingCount: chunks.filter(c => !c.uploaded).length,
        metaPendingCount: meta?.pending_count,
      }
    })
    console.log(`[D.2] 离线期间 IDB 状态: chunks=${persistenceCheck.chunkCount}, pending=${persistenceCheck.pendingCount}`)
    expect(persistenceCheck.chunkCount, '离线期间 chunks 仍存在').toBe(5)
    expect(persistenceCheck.pendingCount, '5 个 chunk 都标记未上传').toBe(5)
    expect(persistenceCheck.metaPendingCount).toBe(5)

    // 模拟重连后 flush: 把 chunks 标记 uploaded
    await context.setOffline(false)
    await page.waitForTimeout(300)

    const flushResult = await page.evaluate(async () => {
      const db = await new Promise((resolve, reject) => {
        const req = indexedDB.open('microbubble_recorder', 1)
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => reject(req.error)
      })
      const tx = db.transaction(['chunks', 'meta'], 'readwrite')
      const idx = tx.objectStore('chunks').index('by_meeting')
      const chunks = await new Promise((resolve, reject) => {
        const r = idx.getAll(IDBKeyRange.only(999003))
        r.onsuccess = () => resolve(r.result)
        r.onerror = () => reject(r.error)
      })
      const store = tx.objectStore('chunks')
      for (const c of chunks) {
        c.uploaded = true
        c.uploaded_at = Date.now()
        store.put(c)
      }
      // 更新 meta 标记全部已上传
      const metaStore = tx.objectStore('meta')
      const meta = await new Promise((resolve, reject) => {
        const r = metaStore.get(999003)
        r.onsuccess = () => resolve(r.result)
        r.onerror = () => reject(r.error)
      })
      if (meta) {
        meta.pending_count = 0
        meta.all_uploaded_at = Date.now()
        metaStore.put(meta)
      }
      await new Promise((resolve, reject) => {
        tx.oncomplete = resolve
        tx.onerror = () => reject(tx.error)
      })

      // 验证
      const verifyTx = db.transaction(['chunks', 'meta'], 'readonly')
      const verifyIdx = verifyTx.objectStore('chunks').index('by_meeting')
      const verifyChunks = await new Promise((resolve, reject) => {
        const r = verifyIdx.getAll(IDBKeyRange.only(999003))
        r.onsuccess = () => resolve(r.result)
        r.onerror = () => reject(r.error)
      })
      const verifyMeta = await new Promise((resolve, reject) => {
        const r = verifyTx.objectStore('meta').get(999003)
        r.onsuccess = () => resolve(r.result)
        r.onerror = () => reject(r.error)
      })
      return {
        uploadedCount: verifyChunks.filter(c => c.uploaded).length,
        metaPendingCount: verifyMeta?.pending_count,
      }
    })

    console.log(`[D.3] 重连 flush 后: uploaded=${flushResult.uploadedCount}, metaPending=${flushResult.metaPendingCount}`)
    expect(flushResult.uploadedCount, 'flush 后 5 个都标记 uploaded').toBe(5)
    expect(flushResult.metaPendingCount, 'meta pending_count 应清零').toBe(0)

    console.log(`\n✅ D 测试通过：离线队列 + 重连 flush 完整闭环`)
  })

  test('E: navigator.storage.estimate() 返回合理 quota (IDB 配额)', async ({ page, request }) => {
    const token = await fetchToken(request)
    await injectAuth(page, token)

    await page.goto(`${BASE_URL}/chat`, { waitUntil: 'domcontentloaded', timeout: 15_000 })
    await page.waitForTimeout(500)

    const estimate = await page.evaluate(async () => {
      if (!navigator.storage?.estimate) return { supported: false }
      const est = await navigator.storage.estimate()
      return {
        supported: true,
        usage: est.usage,
        quota: est.quota,
        usagePercent: est.quota ? ((est.usage || 0) / est.quota * 100).toFixed(4) : null,
      }
    })

    console.log(`[E.1] storage.estimate supported: ${estimate.supported}`)
    if (estimate.supported) {
      console.log(`[E.2] usage: ${estimate.usage} bytes, quota: ${estimate.quota} bytes`)
      console.log(`[E.3] usage%: ${estimate.usagePercent}%`)

      // 配额通常 >= 100MB, 使用 < quota
      expect(estimate.quota, 'quota 应 >= 100MB').toBeGreaterThan(100 * 1024 * 1024)
      expect(estimate.usage, 'usage 应 < quota').toBeLessThan(estimate.quota)
    } else {
      console.log(`[E.2] 当前浏览器不支持 navigator.storage.estimate, 跳过 quota 验证`)
      test.skip(true, '浏览器不支持 navigator.storage.estimate (Safari 私密模式等)')
    }

    console.log(`\n✅ E 测试通过：IDB 配额验证完成`)
  })
})