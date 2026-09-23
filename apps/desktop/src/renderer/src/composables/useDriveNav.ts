// UI1-3 网盘：拖拽上传 + 文件夹导航的纯逻辑（可离线测）
//
// 拖拽与路径面包屑的判定若写在组件里就只能靠真机点，这里抽成纯函数。

/** 拖拽事件 → 是否有文件被拖入（含 items 兜底） */
export function hasDraggedFiles(
  dt: { types?: ArrayLike<string>; items?: ArrayLike<{ kind: string }> } | null | undefined
): boolean {
  if (!dt) return false
  if (dt.types && Array.from(dt.types).includes('Files')) return true
  if (dt.items) return Array.from(dt.items).some((i) => i.kind === 'file')
  return false
}

/** 拖拽高亮计数：enter/leave 会成对但可能嵌套，用计数避免闪烁 */
export function nextDragDepth(depth: number, kind: 'enter' | 'leave' | 'drop'): number {
  if (kind === 'drop') return 0
  if (kind === 'enter') return depth + 1
  return depth > 0 ? depth - 1 : 0
}

/** 是否应显示拖拽高亮 */
export function isDragActive(depth: number): boolean {
  return depth > 0
}

/** 从拖入的 FileList 中筛出可上传的本地路径（Electron 的 File 带 path） */
export function extractLocalPaths(files: { path?: string; name: string }[]): { path: string; name: string }[] {
  return files
    .filter((f) => typeof f.path === 'string' && f.path.length > 0)
    .map((f) => ({ path: f.path as string, name: f.name }))
}

/** 从拖入项中筛出目录（用于「拖文件夹」提示不支持） */
export function hasDirectoryOnly(files: { path?: string; name: string; type?: string }[]): boolean {
  return files.length > 0 && files.every((f) => !f.path && !f.type)
}

// ---------------------------------------------------------------- 面包屑

export interface Crumb {
  id: number | null
  name: string
}

export const ROOT_CRUMB: Crumb = { id: null, name: '网盘' }

/** 进入子文件夹（追加面包屑） */
export function enterFolder(crumbs: readonly Crumb[], folder: { id: number; name: string }): Crumb[] {
  return [...crumbs, { id: folder.id, name: folder.name }]
}

/** 点面包屑回退到第 index 级（0 = 根） */
export function goToCrumb(crumbs: readonly Crumb[], index: number): Crumb[] {
  if (index < 0) return [ROOT_CRUMB]
  return crumbs.slice(0, index + 1)
}

/** 当前目录 id（面包屑末级） */
export function currentFolderId(crumbs: readonly Crumb[]): number | null {
  return crumbs.length ? crumbs[crumbs.length - 1]!.id : null
}

/** 面包屑展示文本 */
export function crumbPath(crumbs: readonly Crumb[]): string {
  return crumbs.map((c) => c.name).join(' / ')
}

// ---------------------------------------------------------------- 搜索过滤

/** 本地过滤当前目录条目（服务端检索另走 keyword 参数） */
export function filterItems<T extends { fileName: string; title?: string }>(items: readonly T[], keyword: string): T[] {
  const k = keyword.trim().toLowerCase()
  if (!k) return [...items]
  return items.filter((i) => i.fileName.toLowerCase().includes(k) || (i.title ?? '').toLowerCase().includes(k))
}
