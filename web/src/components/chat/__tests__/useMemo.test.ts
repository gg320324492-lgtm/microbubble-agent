import { describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { useMemo } from '@/composables/useMemo'

describe('useMemo', () => {
  it('caches a derived value while dependencies stay equal', () => {
    const source = ref({ result: 1 })
    const unrelated = ref(0)
    const getter = vi.fn(() => JSON.stringify(source.value))
    const scope = effectScope()
    const memo = scope.run(() => useMemo(getter, () => [source.value]))!

    expect(memo.value).toBe('{"result":1}')
    expect(memo.value).toBe('{"result":1}')
    unrelated.value++
    expect(memo.value).toBe('{"result":1}')
    expect(getter).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('recomputes when a dependency changes', async () => {
    const source = ref({ result: 1 })
    const getter = vi.fn(() => JSON.stringify(source.value))
    const scope = effectScope()
    const memo = scope.run(() => useMemo(getter, () => [source.value]))!

    expect(memo.value).toBe('{"result":1}')
    source.value = { result: 2 }
    await nextTick()
    expect(memo.value).toBe('{"result":2}')
    expect(getter).toHaveBeenCalledTimes(2)
    scope.stop()
  })
})
