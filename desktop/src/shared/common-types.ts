// Phase 0 公共类型。
// 仅 ping/pong 形状；Phase 1+ 业务类型不在这里。

export interface PingRequest {
  message?: string
}

export interface PongResponse {
  success: boolean
  message: 'pong'
  timestamp: number
  echo?: string
}
