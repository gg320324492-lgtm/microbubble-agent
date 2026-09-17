// 通知触发判定（M4）— 纯函数：窗口可见性与设置共同决定是否弹原生通知
export function shouldNotify(input: {
  windowVisible: boolean
  enabled: boolean
  alreadyShownOnce?: boolean
}): boolean {
  if (input.windowVisible) return false
  if (!input.enabled) return false
  if (input.alreadyShownOnce) return false
  return true
}
