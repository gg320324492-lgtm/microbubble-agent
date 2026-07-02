// useFolderDropZone.js — 课题组网盘 PR3.5 文件夹拖拽 composable
// 2026-07-01

import { ref, onBeforeUnmount } from 'vue'

/**
 * 文件夹拖拽 composable
 *
 * 浏览器支持情况:
 * - Chrome / Edge / Safari 14+: dataTransfer.items + webkitGetAsEntry (支持文件夹)
 * - Firefox: dataTransfer.files 仅文件 (不支持 webkitdirectory 拖拽)
 * - 降级: Firefox 拖拽走 f.name 作 relativePath (line 88)
 *
 * 数据流:
 * 1. onDrop 接收 DragEvent
 * 2. 检查 dataTransfer.items (webkitGetAsEntry 递归)
 * 3. emit('files-dropped', { entries: [{file, relativePath}] })
 * 4. 父组件 (DesktopDriveView / KnowledgeUploadDialog) 决定上传逻辑
 *
 * 状态:
 * - isDragging: 全局 dragover 状态 (用于显示高亮)
 * - dragDepth: 当前 dragenter 嵌套层级 (避免 dragenter/leave 计数错乱)
 *
 * 边界:
 * - PR3.5 只做拖拽检测 + 文件解析, 不调 API (上传留给 PR3.6 dialog)
 */
export function useFolderDropZone(options = {}) {
  const {
    onFilesDropped = () => {},
    accept = '*',  // '*' | '.pdf,.doc,.txt,...'
    multiple = true,
    disabled = false
  } = options

  // === 状态 ===
  const isDragging = ref(false)
  const dragDepth = ref(0)  // dragenter 嵌套深度 (防止 leave 子元素误触发)

  // === DOM 引用 ===
  let targetElement = null

  // === 事件 handlers ===
  function onDragEnter(e) {
    if (disabled) return
    if (!hasFiles(e)) return
    e.preventDefault()
    dragDepth.value += 1
    if (dragDepth.value === 1) {
      isDragging.value = true
    }
  }

  function onDragOver(e) {
    if (disabled) return
    if (!hasFiles(e)) return
    e.preventDefault()  // 必须 preventDefault 才能触发 drop
    e.dataTransfer.dropEffect = 'copy'
  }

  function onDragLeave(e) {
    if (disabled) return
    if (!hasFiles(e)) return
    e.preventDefault()
    dragDepth.value = Math.max(0, dragDepth.value - 1)
    if (dragDepth.value === 0) {
      isDragging.value = false
    }
  }

  function onDrop(e) {
    if (disabled) return
    if (!hasFiles(e)) return
    e.preventDefault()
    dragDepth.value = 0
    isDragging.value = false

    const items = e.dataTransfer.items
    if (items && items.length > 0) {
      // 优先用 webkitGetAsEntry 解析文件夹 (Chrome / Edge / Safari)
      parseDataTransferItems(items).then(entries => {
        if (entries.length > 0) {
          onFilesDropped({ entries, source: 'datatransfer-items' })
        }
      })
    } else {
      // Firefox 降级: dataTransfer.files (无 relativePath)
      const files = Array.from(e.dataTransfer.files || [])
      const entries = files.map(f => ({ file: f, relativePath: f.name }))
      if (entries.length > 0) {
        onFilesDropped({ entries, source: 'datatransfer-files' })
      }
    }
  }

  // === 工具函数 ===
  function hasFiles(e) {
    if (!e.dataTransfer) return false
    const types = e.dataTransfer.types
    if (!types) return false
    return Array.from(types).includes('Files')
  }

  /**
   * 解析 dataTransfer.items (支持 webkitGetAsEntry 递归)
   * 仅 Chromium / WebKit 支持, Firefox 不支持
   * 返回 [{file, relativePath}] 数组
   */
  async function parseDataTransferItems(items) {
    const entries = []

    // 转换为 FileSystemEntry 数组
    const fsEntries = []
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.kind !== 'file') continue
      const entry = item.webkitGetAsEntry?.()
      if (entry) fsEntries.push(entry)
    }

    // 递归遍历每个 entry
    for (const entry of fsEntries) {
      await traverseEntry(entry, '', entries)
    }

    return entries
  }

  /**
   * 递归遍历 FileSystemEntry
   * - file: 读 File 加入 entries
   * - directory: 递归读 children
   */
  function traverseEntry(entry, parentPath, entries) {
    return new Promise((resolve) => {
      const relativePath = parentPath ? `${parentPath}/${entry.name}` : entry.name

      if (entry.isFile) {
        entry.file((file) => {
          // ⚠️ 不能给 native File 赋值 webkitRelativePath: 它是 read-only native getter
          //   File 对象的 webkitRelativePath 仅由 `<input webkitdirectory>` 自动设置,
          //   拖拽场景浏览器不会设置. 我们的相对路径直接走 entry.relativePath 字段.
          entries.push({ file, relativePath })
          resolve()
        }, () => resolve())  // 读文件失败
      } else if (entry.isDirectory) {
        const reader = entry.createReader()
        const readBatch = () => {
          reader.readEntries(async (children) => {
            if (children.length === 0) {
              resolve()
              return
            }
            // 顺序遍历本批 children
            for (const child of children) {
              await traverseEntry(child, relativePath, entries)
            }
            // readEntries 一次最多返回 100 个, 递归继续读
            readBatch()
          }, () => resolve())
        }
        readBatch()
      } else {
        resolve()
      }
    })
  }

  // === 绑定/解绑 ===
  function bind(element) {
    if (!element) return
    targetElement = element
    element.addEventListener('dragenter', onDragEnter)
    element.addEventListener('dragover', onDragOver)
    element.addEventListener('dragleave', onDragLeave)
    element.addEventListener('drop', onDrop)
  }

  function unbind() {
    if (!targetElement) return
    targetElement.removeEventListener('dragenter', onDragEnter)
    targetElement.removeEventListener('dragover', onDragOver)
    targetElement.removeEventListener('dragleave', onDragLeave)
    targetElement.removeEventListener('drop', onDrop)
    targetElement = null
  }

  onBeforeUnmount(() => {
    unbind()
  })

  return {
    // 状态
    isDragging,
    dragDepth,
    // 方法
    bind,
    unbind,
    // 直接暴露 handlers (供需要更精细控制的场景)
    onDragEnter,
    onDragOver,
    onDragLeave,
    onDrop
  }
}