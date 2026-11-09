/**
 * routeViewKey.js — 给 App.vue 的 <component :is> 生成稳定的路由视图 key。
 *
 * 2026-11-09 P0（会议 273 播放中断事故）：
 * 原实现用 `route.fullPath` 当 key。会议/知识库/项目统计等页面把 TabStrip 状态
 * 同步到 `?tab=`（router.replace），query 一变 ⇒ key 变 ⇒ 整棵路由组件被 Vue
 * 强制卸载重建 ⇒ `<audio>`、播放器状态、滚动位置、内联编辑态一起销毁。
 * 用户看到的是「播放录音时点『会议纪要』，声音直接停了」。
 *
 * `?tab=` 只是同一个资源内部的视图状态，不是另一份资源，不该触发 remount。
 * 其余 query（resume / search / id / list / idx / from / assignee_id 等）和
 * hash 仍沿用旧行为：变化就重建，保证深链初始化语义不回归。
 *
 * 判据（类 20.220）：不能只看状态字段，要验副作用 —— 切 tab 后 `<audio>`
 * 仍是同一个 DOM 节点、paused=false、currentTime 继续增长。
 */

/** 仅忽略 tab；其它 query 键变动仍按旧语义触发 remount */
const IGNORED_QUERY_KEYS = new Set(['tab'])

function stableValue(value) {
  if (Array.isArray(value)) {
    return `[${value.map((v) => JSON.stringify(v ?? null)).join(',')}]`
  }
  return JSON.stringify(value ?? null)
}

function stableRecord(record, ignoredKeys = new Set()) {
  return Object.keys(record || {})
    .filter((k) => !ignoredKeys.has(k))
    .sort()
    .map((k) => `${k}:${stableValue(record[k])}`)
    .join('&')
}

/**
 * @param {object} route vue-router 的 route 对象（或形状相同的普通对象）
 * @returns {string} 稳定 key
 */
export function buildRouteViewKey(route = {}) {
  const path = route.path || ''
  const params = stableRecord(route.params)
  const query = stableRecord(route.query, IGNORED_QUERY_KEYS)
  const hash = route.hash || ''
  return `${path}|${params}|${query}|${hash}`
}

export default buildRouteViewKey
