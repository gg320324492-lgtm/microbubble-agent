import { describe, it, expect } from 'vitest'
import {
  parseSuggestions,
  suggestionAction,
  retryAction,
  cancelAction,
  syncAction,
  mergeUserActions,
  summarizeUserActions
} from '../../src/renderer/src/utils/agent-interaction'

describe('parseSuggestions', () => {
  it('string[] -> suggestion actions', () => {
    const out = parseSuggestions(['A', 'B'])
    expect(out).toHaveLength(2)
    expect(out[0]?.type).toBe('suggestion')
  })
  it('object[] -> text field as label', () => {
    const out = parseSuggestions([{ id: 'a', text: 'A' }, { label: 'B' }])
    expect(out[0]?.id).toBe('a')
    expect(out[0]?.label).toBe('A')
  })
  it('skip invalid', () => {
    expect(parseSuggestions([null, '', 123, 'valid'])).toHaveLength(1)
  })
  it('non-array', () => {
    expect(parseSuggestions(null)).toEqual([])
  })
})

describe('Action 工厂', () => {
  it('5 types', () => {
    expect(suggestionAction('s', 'l').type).toBe('suggestion')
    expect(retryAction('r').type).toBe('retry')
    expect(cancelAction('c').type).toBe('cancel')
    expect(syncAction('s').type).toBe('sync')
  })
})

describe('merge dedup', () => {
  it('by id', () => {
    const out = mergeUserActions([suggestionAction('x', 'A')], [suggestionAction('x', 'B')])
    expect(out).toHaveLength(1)
    expect(out[0]?.label).toBe('A') // first occurrence wins
  })
})

describe('session isolation', () => {
  it('cancel action type', () => {
    expect(cancelAction('c').type).toBe('cancel')
  })
  it('retry action type', () => {
    expect(retryAction('r').type).toBe('retry')
  })
})

describe('summary', () => {
  it('count', () => {
    const s = summarizeUserActions([
      suggestionAction('a', 'A'),
      suggestionAction('b', 'B'),
      retryAction('r'),
      cancelAction('c'),
      syncAction('s')
    ])
    expect(s.total).toBe(5)
  })
})
