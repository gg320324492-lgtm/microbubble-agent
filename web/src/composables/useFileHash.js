// useFileHash.js — 文件 hash 计算 composable (PR4 秒传前端核心)
// 2026-07-01

import { ref } from 'vue'

/**
 * 单文件 hash 计算 (流式, 不阻塞主线程)
 *
 * 用法:
 *   const { hash, progress, hashing, error, calc } = useFileHash()
 *   const h = await calc(file)  // 32/64 字符 hex
 *
 * 内部用 Web Worker + spark-md5 流式 4MB 切片 (1GB 文件 ~3-5s, 不卡 UI)
 *
 * 注意: worker 路径在 build 后会被 Vite 自动 inline 进 chunk, dev 模式走 dev server
 */
export function useFileHash() {
  const hash = ref('')
  const progress = ref(0)  // 0-100
  const hashing = ref(false)
  const error = ref(null)

  const calc = (file) => new Promise((resolve, reject) => {
    if (!file) {
      reject(new Error('no file'))
      return
    }
    // 重置状态
    hash.value = ''
    progress.value = 0
    hashing.value = true
    error.value = null

    let worker
    try {
      // Vite 8 标准 worker 写法: new URL + import.meta.url + type: 'module'
      worker = new Worker(
        new URL('../workers/hash.worker.js', import.meta.url),
        { type: 'module' },
      )
    } catch (e) {
      hashing.value = false
      error.value = `Worker 初始化失败: ${e.message}`
      reject(e)
      return
    }

    worker.onmessage = (e) => {
      const msg = e.data
      if (msg.type === 'progress') {
        progress.value = msg.pct
      } else if (msg.type === 'done') {
        hash.value = msg.hash
        progress.value = 100
        hashing.value = false
        worker.terminate()
        resolve(msg.hash)
      } else if (msg.type === 'error') {
        error.value = msg.message
        hashing.value = false
        worker.terminate()
        reject(new Error(msg.message))
      }
    }

    worker.onerror = (err) => {
      error.value = `Worker 错误: ${err.message}`
      hashing.value = false
      worker.terminate()
      reject(err)
    }

    worker.postMessage({ file })
  })

  return {
    hash,
    progress,
    hashing,
    error,
    calc,
  }
}