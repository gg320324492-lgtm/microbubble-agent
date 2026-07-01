// useResumableUpload.js — v2 网盘 PR5 断点续传 session 持久化
// 2026-07-01

import { ref } from 'vue'

/**
 * 断点续传 session 持久化管理
 *
 * 数据存 localStorage, key = 'drive_resumable_uploads' (Array<SessionMeta>)
 * SessionMeta 包含 upload_id / file_name / file_size / total_chunks / created_at 等
 *
 * 设计:
 * - localStorage 单独 key (不放 chat_msgs_* 等其他 localStorage 旁边)
 * - 24h TTL: 启动时清过期 session (服务端也会清, 客户端兜底)
 * - 上限 10 个: 防 localStorage 撑爆 (5MB 限额)
 */
const STORAGE_KEY = 'drive_resumable_uploads'
const MAX_SESSIONS = 10
const TTL_MS = 24 * 60 * 60 * 1000  // 24h

export function useResumableUpload() {
  // === 内部 helpers ===
  function _loadAll() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return []
      const arr = JSON.parse(raw)
      return Array.isArray(arr) ? arr : []
    } catch (e) {
      console.warn('[ResumableUpload] 解析 localStorage 失败:', e)
      return []
    }
  }

  function _saveAll(sessions) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
    } catch (e) {
      // localStorage 满 / Safari 隐私模式等
      console.warn('[ResumableUpload] 写入 localStorage 失败:', e)
    }
  }

  function _purgeExpired() {
    const all = _loadAll()
    const now = Date.now()
    const valid = all.filter(s => (now - s.created_at) < TTL_MS)
    if (valid.length !== all.length) _saveAll(valid)
    return valid
  }

  // === 公开方法 ===

  /**
   * 保存 session (上传初始化时调)
   * 自动清过期 + 超 MAX_SESSIONS 时删最旧
   */
  function saveSession(meta) {
    const all = _purgeExpired()
    // 去重 (同一 upload_id 不重复存)
    const filtered = all.filter(s => s.upload_id !== meta.upload_id)
    filtered.push(meta)
    // 超上限删最旧
    if (filtered.length > MAX_SESSIONS) {
      filtered.sort((a, b) => a.created_at - b.created_at)
      filtered.splice(0, filtered.length - MAX_SESSIONS)
    }
    _saveAll(filtered)
  }

  /**
   * 列所有 active sessions (启动时 / 上传对话框打开时调)
   * 返回 [{ upload_id, file_name, file_size, total_chunks, age_hours }, ...]
   */
  function listSessions() {
    const all = _purgeExpired()
    const now = Date.now()
    return all.map(s => ({
      upload_id: s.upload_id,
      file_name: s.file_name,
      file_size: s.file_size,
      total_chunks: s.total_chunks,
      folder_id: s.folder_id,
      visibility: s.visibility,
      age_hours: ((now - s.created_at) / (1000 * 60 * 60)).toFixed(1),
    }))
  }

  /**
   * 删单个 session (上传完成 / 中止 / 24h 过期)
   */
  function removeSession(uploadId) {
    const all = _loadAll()
    const filtered = all.filter(s => s.upload_id !== uploadId)
    _saveAll(filtered)
  }

  /**
   * 清所有 sessions (调试 / 用户主动重置)
   */
  function clearAll() {
    localStorage.removeItem(STORAGE_KEY)
  }

  /**
   * 查单个 session
   */
  function getSession(uploadId) {
    return _loadAll().find(s => s.upload_id === uploadId) || null
  }

  return {
    saveSession,
    listSessions,
    removeSession,
    clearAll,
    getSession,
  }
}