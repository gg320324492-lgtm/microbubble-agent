// Command Pipeline — Phase 8-M1-F
// 写命令安全约束 + ACK 超时 + 审计日志.
// 5 类命令: set-setpoint / start / stop / calibrate / reset-alarm

import type { DatabaseService } from '../database.service'
import type { CommandAck, DeviceConfig, DeviceCommand } from './device-types'
import type { DeviceDriver } from './device-driver'

const ACK_TIMEOUT_MS = 5000

export interface CommandPipeline {
  execute(cmd: DeviceCommand, driver: DeviceDriver, config: DeviceConfig): Promise<CommandAck>
}

class CommandPipelineImpl implements CommandPipeline {
  constructor(private readonly getService: () => DatabaseService | null) {}

  async execute(cmd: DeviceCommand, driver: DeviceDriver, config: DeviceConfig): Promise<CommandAck> {
    const commandId = `cmd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    try {
      this.assertSafety(cmd, config)
    } catch (err) {
      const message = err instanceof Error ? err.message : '安全检查失败'
      this.audit(cmd, commandId, 'rejected', message)
      return { commandId, status: 'rejected', message, timestamp: Date.now() }
    }
    if (!driver.isConnected()) {
      const message = '设备未连接'
      this.audit(cmd, commandId, 'rejected', message)
      return { commandId, status: 'rejected', message, timestamp: Date.now() }
    }
    try {
      const ack = await this.withTimeout(driver.write(cmd.metric ?? 'setpoint', cmd.value ?? 0, commandId), ACK_TIMEOUT_MS)
      this.audit(cmd, commandId, ack.status, ack.message)
      return ack
    } catch (err) {
      const message = err instanceof Error ? err.message : '命令执行超时'
      const ack: CommandAck = { commandId, status: 'timeout', message, timestamp: Date.now() }
      this.audit(cmd, commandId, 'timeout', message)
      return ack
    }
  }

  private assertSafety(cmd: DeviceCommand, config: DeviceConfig): void {
    switch (cmd.kind) {
      case 'set-setpoint': {
        if (cmd.value === undefined || !Number.isFinite(cmd.value)) throw new Error('set-setpoint 缺少 value')
        if (config.alarmLow !== undefined && config.alarmLow !== null && cmd.value < config.alarmLow) {
          throw new Error(`setpoint ${cmd.value} 低于 alarm_low ${config.alarmLow}`)
        }
        if (config.alarmHigh !== undefined && config.alarmHigh !== null && cmd.value > config.alarmHigh) {
          throw new Error(`setpoint ${cmd.value} 高于 alarm_high ${config.alarmHigh}`)
        }
        break
      }
      case 'start': {
        const last = config.calibrationAt ?? 0
        const ageDays = (Date.now() - last) / 86_400_000
        if (!last || ageDays > 7) throw new Error('启动前需要 7 天内的标定')
        break
      }
      case 'stop':
        break
      case 'calibrate':
        break
      case 'reset-alarm': {
        if (!cmd.reason || cmd.reason.length < 10) throw new Error('reset-alarm reason 必须 ≥ 10 字符')
        if (!cmd.operator || cmd.operator.length < 1) throw new Error('reset-alarm 需 operator')
        break
      }
    }
  }

  private withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`命令超时 (>${ms}ms)`)), ms)
      p.then((v) => { clearTimeout(timer); resolve(v) }, (e) => { clearTimeout(timer); reject(e) })
    })
  }

  private audit(cmd: DeviceCommand, commandId: string, status: string, message: string): void {
    const svc = this.getService()
    if (!svc) return
    svc.audit.record({
      action: 'device.command',
      module: 'device',
      metadata: { deviceId: cmd.deviceId, kind: cmd.kind, status, commandId, message }
    })
  }
}

export function createCommandPipeline(getService: () => DatabaseService | null): CommandPipeline {
  return new CommandPipelineImpl(getService)
}
