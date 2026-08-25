<script setup lang="ts">
import { computed } from 'vue'
import type { DeviceStatusPanel } from '../../../../shared/control/experiment-control-schema'
import ReactorTwinPanel from './digital-twin/ReactorTwinPanel.vue'
import PumpTwinPanel from './digital-twin/PumpTwinPanel.vue'
import OzoneGeneratorTwinPanel from './digital-twin/OzoneGeneratorTwinPanel.vue'
import SensorTwinPanel from './digital-twin/SensorTwinPanel.vue'

const props = withDefaults(defineProps<{
  devices?: DeviceStatusPanel[]
  ariaLabel?: string
}>(), {
  devices: () => [] as DeviceStatusPanel[],
  ariaLabel: '数字孪生设备拓扑'
})

const isEmpty = computed(() => !props.devices || props.devices.length === 0)

const reactor = computed(() =>
  props.devices.find((device) => device.type === 'reactor')
)
const pump = computed(() =>
  props.devices.find((device) => device.type === 'pump')
)
const ozoneGenerator = computed(() =>
  props.devices.find((device) => device.type === 'ozone-generator')
)
const sensors = computed(() =>
  props.devices.filter((device) => device.type === 'sensor')
)
</script>

<template>
  <section class="scada-device-topology" aria-label="数字孪生设备拓扑">
    <button type="button" class="scada-device-topology__focusable" @keydown.enter.prevent aria-hidden="false"><span aria-hidden="true">.</span></button>
      <header class="scada-device-topology__head">
      <span class="scada-device-topology__title">设备拓扑</span>
      <span class="scada-device-topology__count">设备 {{ (devices ?? []).length }}</span>
    </header>

    <div v-if="!isEmpty" class="scada-device-topology__grid">
      <div class="scada-device-topology__lane scada-device-topology__lane--reactor">
        <ReactorTwinPanel :device="reactor" aria-label="反应器孪生面板" />
      </div>
      <div class="scada-device-topology__lane scada-device-topology__lane--pump">
        <PumpTwinPanel :device="pump" aria-label="泵孪生面板" />
      </div>
      <div class="scada-device-topology__lane scada-device-topology__lane--ozone">
        <OzoneGeneratorTwinPanel :device="ozoneGenerator" aria-label="臭氧发生器孪生面板" />
      </div>
      <div class="scada-device-topology__lane scada-device-topology__lane--sensor">
        <SensorTwinPanel :devices="sensors" aria-label="传感器孪生面板" />
      </div>
      <div class="scada-device-topology__signal" aria-hidden="true">
        <span class="scada-device-topology__signal-line"></span>
        <span class="scada-device-topology__signal-line"></span>
        <span class="scada-device-topology__signal-line"></span>
      </div>
    </div>

    <div v-else class="scada-device-topology__empty" role="status">暂无设备接入数据</div>
  </section>
</template>

<style scoped>
.scada-device-topology {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, var(--research-bg-scada-surface, #0f1722) 0%, var(--research-bg-scada-deep, #0a1118) 100%);
  color: var(--research-scada-text, #d6e4ee);
  border: 1px solid var(--research-scada-grid, #314347);
  border-radius: 12px;
  padding: 20px;
}
.scada-device-topology:focus-visible {
  outline: 2px solid var(--research-scada-accent, #38bdf8);
  outline-offset: 2px;
}
.scada-device-topology__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 16px;
}
.scada-device-topology__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--research-scada-text, #d6e4ee);
}
.scada-device-topology__count {
  font-size: 12px;
  color: var(--research-scada-muted, #94a3b8);
}
.scada-device-topology__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  position: relative;
}
.scada-device-topology__lane {
  min-width: 0;
}
.scada-device-topology__signal {
  position: absolute;
  inset: 40px 0 0 0;
  display: flex;
  justify-content: space-around;
  pointer-events: none;
}
.scada-device-topology__signal-line {
  width: 12%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--research-scada-grid, #314347), transparent);
}
.scada-device-topology__empty {
  text-align: center;
  padding: 32px;
  color: var(--research-scada-muted, #94a3b8);
  font-size: 13px;
}
@media (max-width: 1480px) {
  .scada-device-topology__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (min-width: 1720px) {
  .scada-device-topology__grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
@media (prefers-reduced-motion: reduce) {
  .scada-device-topology,
  .scada-device-topology * {
    transition: none !important;
  }
}
</style>