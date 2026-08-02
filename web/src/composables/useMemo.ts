import { computed, type ComputedRef } from 'vue'

function shallowEqual(left: readonly unknown[], right: readonly unknown[]): boolean {
  return left.length === right.length && left.every((value, index) => Object.is(value, right[index]))
}

/**
 * Memoize a derived value with Vue's computed cache.
 * Without deps, Vue tracks getter dependencies automatically. Explicit deps are
 * for non-reactive closure inputs and are compared shallowly.
 */
export function useMemo<T>(getter: () => T, deps?: () => unknown[]): ComputedRef<T> {
  if (!deps) return computed(getter)

  let initialized = false
  let previousDeps: unknown[] = []
  let cachedValue: T

  return computed(() => {
    const nextDeps = deps()
    if (!initialized || !shallowEqual(previousDeps, nextDeps)) {
      cachedValue = getter()
      previousDeps = [...nextDeps]
      initialized = true
    }
    return cachedValue
  })
}

export default useMemo
