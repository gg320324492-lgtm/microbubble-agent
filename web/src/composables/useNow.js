/**
 * useNow — 取当前时间的单一入口 (墙钟收敛)
 *
 * 背景: 应用代码里曾有 4 处墙钟源 (直接 `new Date()` / `dayjs()` 取当前时间),
 * 散落在 4 个文件, 没有统一入口, 测试无法注入固定时刻。
 *
 * 设计选择 (参照 `src/utils/timeDivider.ts:14` 的既有惯例):
 * `formatTimeDivider(date, now = new Date())` 用**可选参数做依赖注入**,
 * 缺省才落回真实墙钟 —— 本 composable 同风格, 保持一致。
 *
 * 关键约束: 视觉回归用容器级 `LD_PRELOAD=libfaketime` 冻结时钟,
 * **默认实现必须是真实墙钟**, 不能"强制注入无缺省"。
 *
 * @example
 * // 只取一次 (无定时器)
 * const { now } = useNow()
 *
 * // 每秒刷新, 组件卸载自动清理
 * const { now } = useNow(1000)
 *
 * // 测试注入固定时刻
 * const { now, tick } = useNow(0, () => new Date('2026-10-05T10:00:00'))
 *
 * @param {number} intervalMs tick 间隔 (毫秒); 0 = 不自动 tick, 只返回初始值
 * @param {() => Date} clock 可注入的时钟源; 缺省落回真实墙钟 `() => new Date()`
 * @returns {{ now: import('vue').Ref<Date>, tick: () => void }}
 *   now = 当前时刻 (ref, 初始值 = clock())
 *   tick = 手动刷新方法 (测试 / 用户交互触发时用)
 */
import { ref, onUnmounted } from 'vue'

export function useNow(intervalMs = 0, clock = () => new Date()) {
  // 初始值立刻取一次 —— 无论 intervalMs 是否为 0
  const now = ref(clock())

  let timer = null

  function tick() {
    now.value = clock()
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  // intervalMs > 0 才起定时器; = 0 完全不起 (避免"看一眼也要挂个 timer")
  if (intervalMs > 0) {
    timer = setInterval(tick, intervalMs)
  }

  // 防内存泄漏 / 测试挂起: 组件卸载必须清 timer
  onUnmounted(stop)

  return { now, tick }
}