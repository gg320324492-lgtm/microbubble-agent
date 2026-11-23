import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'
import { validateRecordingSession } from '../useRecordingSessionGuard'

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('validateRecordingSession', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('状态可录且心跳存活 → allowed', async () => {
    axios.get
      .mockResolvedValueOnce({ data: { status: 'recording' } })
      .mockResolvedValueOnce({ data: { alive: true, session_id: 's-1' } })

    const result = await validateRecordingSession(278)
    expect(result).toEqual({ allowed: true, status: 'recording', reason: 'ok' })
    expect(axios.get).toHaveBeenCalledWith('/api/v1/meetings/278/recording-heartbeat')
  })

  it('status=recording 但心跳已死 → 拒绝恢复旧会议', async () => {
    axios.get
      .mockResolvedValueOnce({ data: { status: 'recording' } })
      .mockResolvedValueOnce({ data: { alive: false } })

    const result = await validateRecordingSession(278)
    expect(result.allowed).toBe(false)
    expect(result.reason).toBe('recording_heartbeat_dead')
  })

  it('心跳存活但会议已完成 → 拒绝恢复终态会议', async () => {
    axios.get
      .mockResolvedValueOnce({ data: { status: 'completed' } })
      .mockResolvedValueOnce({ data: { alive: true } })

    const result = await validateRecordingSession(278)
    expect(result.allowed).toBe(false)
    expect(result.reason).toBe('meeting_not_recordable')
  })

  it('校验失败一律拒绝，不降级放行', async () => {
    axios.get.mockRejectedValue(new Error('401'))

    const result = await validateRecordingSession(278)
    expect(result.allowed).toBe(false)
    expect(result.reason).toBe('validation_failed')
  })
})
