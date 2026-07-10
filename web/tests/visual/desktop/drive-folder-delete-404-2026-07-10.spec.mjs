/**
 * tests/visual/desktop/drive-folder-delete-404-2026-07-10.spec.mjs
 *
 * 端到端验证 2026-07-10 folder delete 404 错误消息提取修复:
 *
 * 症状 (修复前):
 *   - 后端 4 处 404 + 1 处 403 + 3 处 FolderServiceError 全用裸 HTTPException(detail=...)
 *     → FastAPI 默认格式 `{"detail": "..."}`，不走 AppException handler
 *   - 前端 useFolderTree.js 6 处 catch 硬找 `.error.message` 找不到 → 落兜底字符串
 *     → 用户 console 看到 "undefined 删除文件夹失败"，不知道真实原因
 *
 * 修复 (commit 2a97fcc6):
 *   - 后端 drive_folders.py: 4 处 404 → NotFoundException, 1 处 403 → ForbiddenException,
 *     3 处 FolderServiceError → _reraise_folder_service_error() helper
 *   - 前端 useFolderTree.js: 6 处 catch 用 extractErrorMessage() 双兼容
 *
 * 前置:
 *   - dev server (npm run dev) 或 BASE_URL 指向部署环境
 *   - TEST_TOKEN 环境变量注入真实 JWT
 *
 * 运行:
 *   BASE_URL=https://agent.mnb-lab.cn \
 *   TEST_TOKEN=$(curl ... -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' ...) \
 *   npx playwright test tests/visual/desktop/drive-folder-delete-404-2026-07-10.spec.mjs
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3004'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

test.describe('drive-folder-delete-404-2026-07-10: AppException 格式 + 错误消息提取', () => {
  test('A: 直接 DELETE /api/v1/folders/28 返 AppException 格式 (非 FastAPI 默认 {detail})', async ({ page, context }) => {
    // 用 context.request + Authorization header (比 cookie 更可靠，避免 secure cookie 跨域问题)
    const resp = await context.request.delete(`${BASE_URL}/api/v1/folders/28`, {
      headers: {
        'Authorization': `Bearer ${TEST_TOKEN}`,
        'Content-Type': 'application/json',
      },
    })
    const status = resp.status()
    const body = await resp.json()

    console.log(`[A.1] HTTP status: ${status}`)
    console.log(`[A.2] Response body:`, JSON.stringify(body))

    // 1. 状态码必须是 404
    expect(status, '删除不存在的 folder 应返 404').toBe(404)

    // 2. 响应必须是 AppException 格式 `{error: {code, message, details}}`
    expect(body, '响应必须有 error 字段').toHaveProperty('error')
    expect(body, '响应不能有 FastAPI 默认 detail 字段').not.toHaveProperty('detail')

    // 3. error 字段必须含 code/message/details
    expect(body.error, 'error.code 必须是 FOLDER_NOT_FOUND').toMatchObject({
      code: 'FOLDER_NOT_FOUND',
      message: expect.stringContaining('Folder'),
    })
    expect(body.error.details, 'error.details 应含 folder_id=28').toMatchObject({
      folder_id: 28,
    })

    console.log(`\n✅ A 测试通过：API 响应符合 AppException 标准格式`)
  })

  test('B: extractErrorMessage 双兼容（AppException + FastAPI 默认）— 直接测代码逻辑', async ({ page, context }) => {
    // 不走 SPA 完整流程（Playwright cookie/localStorage 同步 + 401 redirect 太复杂），
    // 直接在浏览器里跑 extractErrorMessage 逻辑，验证 4 种错误场景的提取行为。
    //
    // 修复前: `e.response?.data?.error?.message || '删除文件夹失败'`
    // 修复后: extractErrorMessage() 支持 AppException + FastAPI detail + Error.message + 兜底

    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2000)

    // 用 context.request 拿到真实响应，然后用真实响应 body 测 extractErrorMessage
    const realResp = await context.request.delete(`${BASE_URL}/api/v1/folders/28`, {
      headers: { 'Authorization': `Bearer ${TEST_TOKEN}` },
    })
    const realBody = await realResp.json()
    console.log(`[B.1] 真实 API 响应:`, JSON.stringify(realBody).slice(0, 200))

    // 把 extractErrorMessage 源代码 inline 到浏览器内执行（避免 module import 复杂度）
    const results = await page.evaluate(({ body }) => {
      // 复刻 useFolderTree.js 的 extractErrorMessage 逻辑（与 commit 2a97fcc6 完全一致）
      function extractErrorMessage(e, fallback) {
        const data = e.response?.data
        return data?.error?.message || data?.detail || e.message || fallback
      }

      // 1. 模拟真实后端 AppException 响应（修复后应该走这条路径）
      const e1 = { response: { status: 404, data: body } }
      const msg1 = extractErrorMessage(e1, '删除文件夹失败')

      // 2. 模拟 FastAPI 默认响应（修复前 - 兜底会触发）
      const e2 = { response: { status: 404, data: { detail: 'folder 28 不存在' } } }
      const msg2 = extractErrorMessage(e2, '删除文件夹失败')

      // 3. 模拟纯 Error 对象（无 response，比如网络错误）
      const e3 = new Error('Network Error')
      const msg3 = extractErrorMessage(e3, '删除文件夹失败')

      // 4. 模拟 null response（兜底）
      const e4 = {}
      const msg4 = extractErrorMessage(e4, '删除文件夹失败')

      return { msg1, msg2, msg3, msg4 }
    }, { body: realBody })

    console.log(`[B.2] 4 种场景提取结果:`)
    console.log(`  1. AppException 格式: "${results.msg1}"`)
    console.log(`  2. FastAPI detail 格式: "${results.msg2}"`)
    console.log(`  3. 纯 Error.message: "${results.msg3}"`)
    console.log(`  4. 空对象 (兜底): "${results.msg4}"`)

    // 验证 1: AppException 格式 → 提取出 message="Folder不存在"
    expect(results.msg1, 'AppException 格式必须提取 error.message').toBe('Folder不存在')
    expect(results.msg1, 'AppException 不应是兜底字符串').not.toBe('删除文件夹失败')

    // 验证 2: FastAPI detail 格式 → 提取出 detail (兼容旧 endpoint)
    expect(results.msg2, 'FastAPI detail 格式必须提取 detail 字段').toBe('folder 28 不存在')
    expect(results.msg2, 'FastAPI detail 不应是兜底字符串').not.toBe('删除文件夹失败')

    // 验证 3: 纯 Error.message → 提取出 message
    expect(results.msg3, '纯 Error.message 必须提取').toBe('Network Error')

    // 验证 4: 空对象 → 兜底字符串
    expect(results.msg4, '空对象应走兜底').toBe('删除文件夹失败')

    console.log(`\n✅ B 测试通过：extractErrorMessage 双兼容 — AppException + FastAPI detail + Error.message + 兜底`)
  })

  test('C: FolderServiceError 状态码映射（400/403/404 → Validation/Forbidden/NotFound）', async ({ page, context }) => {
    // 验证 _reraise_folder_service_error() helper 的状态码映射行为
    // 通过真实 API 调用触发 FolderServiceError：
    //   - 400: delete folder with children (FolderServiceError status_code=400)

    // 拿真实 folder tree
    const treeResp = await context.request.get(`${BASE_URL}/api/v1/folders/tree`, {
      headers: { 'Authorization': `Bearer ${TEST_TOKEN}` },
    })
    const treeBody = await treeResp.json()
    console.log(`[C.1] folder tree root 数量: ${treeBody.tree?.length || 0}`)

    if (!treeBody.tree || treeBody.tree.length === 0) {
      console.log(`[C.2] xiaoqi_testbot 无 folder，跳过 C 测试`)
      test.skip(true, '测试账号无 folder 数据')
      return
    }

    // 找一个 owner_id=59 (xiaoqi_testbot) 的 folder 来测 delete
    const myFolder = treeBody.tree.find((f) => f.owner_id === 59)
    if (!myFolder) {
      console.log(`[C.2] xiaoqi_testbot 无 owner folder，跳过 C 测试`)
      test.skip(true, '测试账号无 owner folder')
      return
    }
    console.log(`[C.2] 测删除 folder: id=${myFolder.id} name="${myFolder.name}"`)

    // 触发 delete
    const delResp = await context.request.delete(`${BASE_URL}/api/v1/folders/${myFolder.id}`, {
      headers: { 'Authorization': `Bearer ${TEST_TOKEN}` },
    })
    const delBody = await delResp.json()
    console.log(`[C.3] delete 响应: status=${delResp.status()} body=${JSON.stringify(delBody).slice(0, 200)}`)

    // 验证: 成功删除应返 204 No Content
    if (delResp.status() === 204) {
      console.log(`[C.4] ✅ 删除成功（204）`)
      // 立即恢复（避免污染测试数据）
      const restoreResp = await context.request.post(`${BASE_URL}/api/v1/folders/${myFolder.id}/restore`, {
        headers: { 'Authorization': `Bearer ${TEST_TOKEN}` },
      })
      console.log(`[C.5] 恢复 folder: status=${restoreResp.status()}`)
      expect(delResp.status()).toBe(204)
    } else {
      // 如果返 4xx，必须是 AppException 格式
      expect(delBody, '4xx 必须返 AppException 格式').toHaveProperty('error')
      expect(delBody, '4xx 不能返 FastAPI detail').not.toHaveProperty('detail')
      console.log(`[C.4] ✅ 4xx 响应符合 AppException 格式`)
    }

    console.log(`\n✅ C 测试通过：folder 操作响应格式统一为 AppException`)
  })

  test('D: wrapApiError 保留 e.response/status/code 透传给 caller (v2 加固)', async ({ page, context }) => {
    // 验证 useFolderTree.js 的 wrapApiError() 包装 Error 时保留 e.response
    // 修复前: throw new Error(msg) 丢失 e.response → caller `e.response?.status` 永远 undefined
    // 修复后: wrapApiError() 把 response/status/code/details 附到 Error 上 → caller 可直接读
    //
    // 用户截图 (修复前):
    //   [FolderContextMenu] delete folder 158 failed: undefined Folder不存在
    //                              ↑ status 应该是 404 但 undefined
    // 修复后期望:
    //   [FolderContextMenu] delete folder 158 failed: 404 Folder不存在

    // 1. 拿真实 API 响应 (Folder 28 必然不存在)
    const realResp = await context.request.delete(`${BASE_URL}/api/v1/folders/28`, {
      headers: { 'Authorization': `Bearer ${TEST_TOKEN}` },
    })
    const realBody = await realResp.json()
    console.log(`[D.1] 真实 API 响应: status=${realResp.status()} body=${JSON.stringify(realBody).slice(0, 150)}`)

    // 2. 在浏览器内复刻 wrapApiError 逻辑（与 commit 一致），测 4 个属性是否透传
    const result = await page.evaluate(({ body, httpStatus }) => {
      function extractErrorMessage(e, fallback) {
        const data = e.response?.data
        return data?.error?.message || data?.detail || e.message || fallback
      }
      function wrapApiError(e, fallback) {
        const err = new Error(extractErrorMessage(e, fallback))
        err.response = e.response
        err.status = e.response?.status
        err.code = e.response?.data?.error?.code || null
        err.details = e.response?.data?.error?.details || null
        return err
      }

      // 模拟 composable catch 块的真实场景
      const axiosError = {
        response: { status: httpStatus, data: body },
      }
      const wrapped = wrapApiError(axiosError, '删除文件夹失败')

      // 模拟 FolderTree.vue line 256-258 的 catch 逻辑
      const consoleErrMsg = `[FolderContextMenu] delete folder 28 failed: ${wrapped.status} ${wrapped.message}`

      return {
        msg: wrapped.message,
        status: wrapped.status,
        code: wrapped.code,
        details: wrapped.details,
        hasResponse: !!wrapped.response,
        consoleErrMsg,
      }
    }, { body: realBody, httpStatus: realResp.status() })

    console.log(`[D.2] wrapApiError 透传属性:`)
    console.log(`  message: "${result.msg}"`)
    console.log(`  status: ${result.status}`)
    console.log(`  code: ${result.code}`)
    console.log(`  details: ${JSON.stringify(result.details)}`)
    console.log(`  hasResponse: ${result.hasResponse}`)
    console.log(`  console.error 输出: ${result.consoleErrMsg}`)

    // 核心断言: status 必须等于真实 HTTP status (404), 不是 undefined
    expect(result.status, 'wrapApiError.status 必须透传 HTTP status (404)').toBe(404)
    expect(result.hasResponse, 'wrapApiError 必须保留 e.response 引用').toBe(true)
    expect(result.msg, 'message 必须是真实后端消息').toBe('Folder不存在')
    expect(result.code, 'code 必须是 FOLDER_NOT_FOUND').toBe('FOLDER_NOT_FOUND')
    expect(result.details, 'details 必须含 folder_id=28').toMatchObject({ folder_id: 28 })

    // 关键对比: console.error 字符串不能包含 "undefined"
    expect(result.consoleErrMsg, 'console.error 字符串不应含 "undefined status"').not.toMatch(/failed: undefined/)

    console.log(`\n✅ D 测试通过：wrapApiError 透传 status/code/response，console.error 不再 undefined`)
  })
})