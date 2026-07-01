/**
 * useMentionAutocomplete.test.js - v2 PR6-P4 mention autocomplete unit tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useMentionAutocomplete } from '../useMentionAutocomplete.js'

const MOCK_MEMBERS = [
  { id: 1,  username: 'wangtianzhi', wechat_id: 'WangTianZhi', name: '王天志', role: 'admin' },
  { id: 2,  username: 'zhaohangjia', wechat_id: 'nuyoah.',     name: '赵航佳', role: 'admin' },
  { id: 3,  username: 'dutonghe',    wechat_id: 'DuTongHe',   name: '杜同贺', role: 'member' },
  { id: 18, username: 'yangci',      wechat_id: 'LiuSu',       name: '杨慈', role: 'member' },
]

const wait = (ms = 200) => new Promise((r) => setTimeout(r, ms))

describe('useMentionAutocomplete - filterMembers behavior', () => {
  it('empty query returns all members', async () => {
    const ac = useMentionAutocomplete({ members: MOCK_MEMBERS })
    ac.refresh()
    await wait()
    expect(ac.candidates.value.length).toBe(4)
    expect(ac.isOpen.value).toBe(true)
  })

  it('exact match (wechat_id) ranked first', async () => {
    const ac = useMentionAutocomplete({ members: MOCK_MEMBERS })
    ac.query.value = 'nuyoah.'
    ac.refresh()
    await wait()
    const ids = ac.rawCandidates.value.map((c) => c.id)
    expect(ids[0]).toBe(2)
  })

  it('prefix match (lowercase input) matches case-different wechat_id', async () => {
    const ac = useMentionAutocomplete({ members: MOCK_MEMBERS })
    ac.query.value = 'wang'
    ac.refresh()
    await wait()
    const ids = ac.rawCandidates.value.map((c) => c.id)
    expect(ids).toContain(1)
  })

  it('Chinese name prefix match', async () => {
    const ac = useMentionAutocomplete({ members: MOCK_MEMBERS })
    ac.query.value = '王'
    ac.refresh()
    await wait()
    const ids = ac.rawCandidates.value.map((c) => c.id)
    expect(ids).toContain(1)
  })

  it('no match returns empty + dropdown closed', async () => {
    const ac = useMentionAutocomplete({ members: MOCK_MEMBERS })
    ac.query.value = 'zzzz_nomatch'
    ac.refresh()
    await wait()
    expect(ac.candidates.value).toEqual([])
    expect(ac.isOpen.value).toBe(false)
  })

  it('empty members list does not error', async () => {
    const ac = useMentionAutocomplete({ members: [] })
    ac.refresh()
    await wait()
    expect(ac.candidates.value).toEqual([])
    expect(ac.isOpen.value).toBe(false)
  })
})

describe('useMentionAutocomplete - state machine', () => {
  it('close() resets all state', () => {
    const ac = useMentionAutocomplete({ members: MOCK_MEMBERS })
    ac.query.value = 'wang'
    ac.triggerPos.value = 0
    ac.selectedIndex.value = 2
    ac.isOpen.value = true
    ac.close()
    expect(ac.isOpen.value).toBe(false)
    expect(ac.query.value).toBe('')
    expect(ac.triggerPos.value).toBe(-1)
    expect(ac.cursorPos.value).toBe(-1)
    expect(ac.selectedIndex.value).toBe(0)
  })

  it('selectCandidate invokes onSelect callback + closes dropdown', () => {
    const onSelect = vi.fn()
    const ac = useMentionAutocomplete({ members: MOCK_MEMBERS, onSelect })
    ac.setCandidates(MOCK_MEMBERS.map((m) => ({ member: m, score: 100, isExact: true })))
    ac.selectedIndex.value = 0
    ac.isOpen.value = true
    ac.triggerPos.value = 0
    ac.query.value = 'WangTianZhi'
    ac.selectCandidate(0)
    expect(onSelect).toHaveBeenCalledTimes(1)
    const [member, ctx] = onSelect.mock.calls[0]
    expect(member).toEqual(MOCK_MEMBERS[0])
    expect(ctx.triggerPos).toBe(0)
    expect(ctx.query).toBe('WangTianZhi')
    expect(ac.isOpen.value).toBe(false)
  })

  it('selectCandidate with empty candidates does not invoke callback', () => {
    const onSelect = vi.fn()
    const ac = useMentionAutocomplete({ members: MOCK_MEMBERS, onSelect })
    ac.setCandidates([])
    ac.isOpen.value = true
    ac.selectCandidate(0)
    expect(onSelect).not.toHaveBeenCalled()
  })
})

describe('useMentionAutocomplete - keyboard navigation', () => {
  let ac
  beforeEach(() => {
    ac = useMentionAutocomplete({ members: MOCK_MEMBERS })
    ac.setCandidates(MOCK_MEMBERS.slice(0, 3).map((m) => ({ member: m, score: 100, isExact: true })))
    ac.isOpen.value = true
    ac.selectedIndex.value = 0
  })

  it('moveDown cycles to last and wraps to 0', () => {
    ac.moveDown()
    ac.moveDown()
    ac.moveDown()
    expect(ac.selectedIndex.value).toBe(0)
  })

  it('moveUp from 0 wraps to last', () => {
    ac.moveUp()
    expect(ac.selectedIndex.value).toBe(2)
  })

  it('isOpen=false: handleKeydown returns false (does not intercept)', () => {
    ac.isOpen.value = false
    expect(ac.handleKeydown({ key: 'Enter', preventDefault: vi.fn() })).toBe(false)
  })

  it('ArrowDown in open state returns true + preventDefault called', () => {
    const ev = { key: 'ArrowDown', preventDefault: vi.fn() }
    const handled = ac.handleKeydown(ev)
    expect(handled).toBe(true)
    expect(ev.preventDefault).toHaveBeenCalled()
  })

  it('Enter in open state triggers selectCandidate', () => {
    const onSelect = vi.fn()
    const ac2 = useMentionAutocomplete({ members: MOCK_MEMBERS, onSelect })
    ac2.setCandidates(MOCK_MEMBERS.slice(0, 3).map((m) => ({ member: m, score: 100, isExact: true })))
    ac2.isOpen.value = true
    ac2.selectedIndex.value = 1
    ac2.triggerPos.value = 0
    ac2.query.value = 'WangTianZhi'
    const ev = { key: 'Enter', preventDefault: vi.fn() }
    ac2.handleKeydown(ev)
    expect(onSelect).toHaveBeenCalledWith(MOCK_MEMBERS[1], expect.anything())
  })

  it('Escape closes dropdown + preventDefault', () => {
    const ev = { key: 'Escape', preventDefault: vi.fn() }
    const handled = ac.handleKeydown(ev)
    expect(handled).toBe(true)
    expect(ev.preventDefault).toHaveBeenCalled()
    expect(ac.isOpen.value).toBe(false)
  })

  it('other keys (a / Backspace) are not intercepted', () => {
    expect(ac.handleKeydown({ key: 'a', preventDefault: vi.fn() })).toBe(false)
    expect(ac.handleKeydown({ key: 'Backspace', preventDefault: vi.fn() })).toBe(false)
  })
})

describe('useMentionAutocomplete - maxCandidates truncation', () => {
  it('returns at most maxCandidates entries', async () => {
    const bigList = Array.from({ length: 20 }, (_, i) => ({
      id: i + 1, username: `user${i}`, wechat_id: `user${i}`, name: `user${i}`, role: 'member',
    }))
    const ac = useMentionAutocomplete({ members: bigList, maxCandidates: 5 })
    ac.refresh()
    await wait()
    expect(ac.candidates.value.length).toBe(5)
  })
})
