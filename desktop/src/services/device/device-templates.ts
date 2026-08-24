// Device Templates — 3 套预定义科研设备系统。

import type { DeviceType } from '../../shared/device/device-schema'

export type DeviceTemplateKind =
  | 'o3-mnb-reactor'
  | 'cfd-experiment'
  | 'water-treatment-monitoring'

export const DEVICE_TEMPLATE_KINDS: readonly DeviceTemplateKind[] = Object.freeze([
  'o3-mnb-reactor', 'cfd-experiment', 'water-treatment-monitoring'
])

export interface DeviceTemplateDevice {
  name: string
  type: DeviceType
  parameters: { name: string; value: number | string | boolean; unit: string }[]
}

export interface DeviceTemplate {
  kind: DeviceTemplateKind
  name: string
  description: string
  devices: DeviceTemplateDevice[]
}

const TEMPLATES: readonly DeviceTemplate[] = Object.freeze([
  Object.freeze({
    kind: 'o3-mnb-reactor',
    name: 'O3-MNB 反应器系统',
    description: '臭氧微纳米气泡反应器集成, 含泵 + 臭氧发生器 + pH/DO/温度传感器 + 主控制器',
    devices: [
      { name: 'main-pump', type: 'pump', parameters: [{ name: 'flow_rate', value: 1.5, unit: 'L/min' }] },
      { name: 'ozone-gen', type: 'ozone-generator', parameters: [{ name: 'ozone_dose', value: 5, unit: 'mg/L' }] },
      { name: 'reactor-vessel', type: 'reactor', parameters: [{ name: 'volume', value: 10, unit: 'L' }] },
      { name: 'ph-sensor', type: 'sensor', parameters: [{ name: 'ph', value: 7.0, unit: '' }] },
      { name: 'controller', type: 'controller', parameters: [{ name: 'mode', value: 'auto', unit: '' }] }
    ]
  }),
  Object.freeze({
    kind: 'cfd-experiment',
    name: 'CFD 实验系统',
    description: 'CFD 流场测量与验证, 含入口流量计 + 压力传感器 + 控制器',
    devices: [
      { name: 'inlet-flowmeter', type: 'sensor', parameters: [{ name: 'velocity', value: 1.0, unit: 'm/s' }] },
      { name: 'pressure-sensor-1', type: 'sensor', parameters: [{ name: 'pressure', value: 101325, unit: 'Pa' }] },
      { name: 'pressure-sensor-2', type: 'sensor', parameters: [{ name: 'pressure', value: 101300, unit: 'Pa' }] },
      { name: 'controller', type: 'controller', parameters: [{ name: 'mode', value: 'manual', unit: '' }] }
    ]
  }),
  Object.freeze({
    kind: 'water-treatment-monitoring',
    name: '水处理监控系统',
    description: '水处理多参数监测, 含 pH + 浊度 + 余氯 + 流量传感器',
    devices: [
      { name: 'ph-sensor', type: 'sensor', parameters: [{ name: 'ph', value: 7.2, unit: '' }] },
      { name: 'turbidity-sensor', type: 'sensor', parameters: [{ name: 'turbidity', value: 0.5, unit: 'NTU' }] },
      { name: 'chlorine-sensor', type: 'sensor', parameters: [{ name: 'chlorine', value: 0.5, unit: 'mg/L' }] },
      { name: 'flow-sensor', type: 'sensor', parameters: [{ name: 'flow_rate', value: 50, unit: 'L/min' }] }
    ]
  })
] as DeviceTemplate[])

export function getDeviceTemplate(kind: DeviceTemplateKind): DeviceTemplate {
  const t = TEMPLATES.find((x) => x.kind === kind)
  if (!t) throw new Error(`unknown device template kind: ${kind}`)
  return {
    ...t,
    devices: t.devices.map((d) => ({
      ...d,
      parameters: d.parameters.map((p) => ({ ...p }))
    }))
  }
}

export function listDeviceTemplates(): DeviceTemplate[] {
  return TEMPLATES.map((t) => ({
    ...t,
    devices: t.devices.map((d) => ({
      ...d,
      parameters: d.parameters.map((p) => ({ ...p }))
    }))
  }))
}

export const __testHelpers = { TEMPLATES, DEVICE_TEMPLATE_KINDS }