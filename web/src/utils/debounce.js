// debounce.js — 通用防抖工具 (批次② ②-5 搜索接线新增)
//  trailing-edge: wait 毫秒内重复调用只保留最后一次; 返回的函数带 .cancel()

/**
 * @param {Function} fn 被防抖的函数
 * @param {number} wait 延迟毫秒
 * @returns {Function & { cancel: () => void }}
 */
export function debounce(fn, wait = 300) {
  let timer = null
  const debounced = function (...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn.apply(this, args)
    }, wait)
  }
  debounced.cancel = () => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }
  return debounced
}

export default debounce
