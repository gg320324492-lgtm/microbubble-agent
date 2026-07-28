/**
 * useChunkedUploader.js — W84 B-2 P1-1 兼容层 (thin-shell 委派)
 *
 * 派工依据 (W84 第 1 批 B-2):
 * - W82 A-2 Survey 3 §6 P1: chunked upload 3+ 套并存
 * - W84 B-2 P1-1 Step 1 兼容层: 通用 chunked upload 核心移到 useChunkedUploaderCore.js
 * - W82/W83 B-2 拦截铁律 (#16/#17): 分步走, 本批不改老调用方, 仅 reverse-export
 * - W85 后续 batch 再删老文件 (Step 2)
 *
 * 原始职责 (W68 Mobile UX v3.0):
 *   - uploadOne: 单片上传 (带指数退避)
 *   - uploadAll: 顺序批量上传 (保持 chunk_index 顺序)
 *   - enqueue: 入队 (网络恢复时自动触发)
 *   - online 事件监听: 浏览器从 offline 恢复时自动重传
 *
 * 兼容层 (W84 B-2):
 *   - 本文件 (useChunkedUploader.js) 改为 thin-shell 委派到 useChunkedUploaderCore.js
 *   - 保留原 export 路径 + 函数签名, 老调用方 (useChunkedRecorder.js) 无需改 import
 *   - 行为完全等价: module-level 单例状态由 core 维护 (isUploading / uploadQueue / online listener)
 *
 * 删除计划 (W85 后续 batch):
 *   - 派工 decide 是否替换 useChunkedRecorder.js 调用为 useChunkedUploaderCore 直接导入
 *   - 然后删除 useChunkedUploader.js (本 thin-shell)
 */

import { useChunkedUploaderCore } from './useChunkedUploaderCore'

// 委派: 老 API (uploadOne / uploadAll / enqueue / drainQueue) 转发到 core
// 注意: 保持函数引用相等性 (调用方可能在多处解构), 但这些是 module-level fns
// core 导出同名函数, 这里重新 re-export 确保 import 路径不变
export { uploadOne, uploadAll, enqueue, drainQueue } from './useChunkedUploaderCore'

// Composable 形式 (供组件内 reactive 使用)
export function useChunkedUploader() {
  return useChunkedUploaderCore()
}

export default useChunkedUploader
