/**
 * useDriveDragMove.js — 网盘盘内拖拽移动 (批次③ B 三栏工作台 F8)
 *
 * 机制:
 * - 拖源 (DriveFileTable 行): dragstart 写 dataTransfer
 *   MIME 'application/x-drive-file-ids' → JSON ids (多选拖已选集合, 单选拖该行)。
 * - 落点 (FolderTree 节点 / 表格文件夹行 / 面包屑): dragover 判 types 含本 MIME
 *   才 preventDefault (与外部文件上传 drop 互斥 — 上传 drop 只认 'Files')。
 * - drop → 解析 ids → emit 给视图层调 moveFile/batchMove。
 *
 * MIME 常量单源, 拖源与落点都从这里 import, 防打错字静默失效。
 */
export const DRIVE_MOVE_MIME = 'application/x-drive-file-ids'

/** 从 DataTransfer 读取被拖文件 ids; 非本应用拖拽 (外部文件/其它 MIME) 返 null */
export function readDriveMovePayload(dataTransfer) {
  if (!dataTransfer) return null
  const types = dataTransfer.types ? Array.from(dataTransfer.types) : []
  if (!types.includes(DRIVE_MOVE_MIME)) return null
  try {
    const raw = dataTransfer.getData(DRIVE_MOVE_MIME)
    const ids = JSON.parse(raw)
    return Array.isArray(ids) && ids.length && ids.every((n) => Number.isInteger(n)) ? ids : null
  } catch {
    return null
  }
}

/** dragover 判定 + 视觉态回调: 返回 { ok } 供调用方 preventDefault */
export function isDriveMoveDragging(event) {
  const types = event?.dataTransfer?.types
  return !!types && Array.from(types).includes(DRIVE_MOVE_MIME)
}

/**
 * 给一个 DOM 元素挂"移动落点"行为的工具 (供非组件环境/调试用;
 * Vue 模板走 @dragover/@drop 时不需要它)。
 */
export function makeMoveDropTarget(el, { onDrop, onEnter, onLeave }) {
  const over = (e) => {
    if (!isDriveMoveDragging(e)) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    onEnter?.()
  }
  const leave = () => onLeave?.()
  const drop = (e) => {
    const ids = readDriveMovePayload(e.dataTransfer)
    if (!ids) return
    e.preventDefault()
    e.stopPropagation()
    onDrop?.(ids)
    onLeave?.()
  }
  el.addEventListener('dragover', over)
  el.addEventListener('dragleave', leave)
  el.addEventListener('drop', drop)
  return () => {
    el.removeEventListener('dragover', over)
    el.removeEventListener('dragleave', leave)
    el.removeEventListener('drop', drop)
  }
}
