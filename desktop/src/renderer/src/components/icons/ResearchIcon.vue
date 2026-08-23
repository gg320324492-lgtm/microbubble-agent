<script setup lang="ts">
import { computed } from 'vue'
import { isResearchIconName, RESEARCH_ICONS, type ResearchIconName } from './research-icons'

interface Props {
  name: ResearchIconName
  size?: number | string
  color?: string
  label?: string
}

const props = withDefaults(defineProps<Props>(), {
  size: 20,
  color: undefined,
  label: undefined
})

const resolvedName = computed<ResearchIconName>(() =>
  isResearchIconName(String(props.name)) ? props.name : 'document'
)
const paths = computed(() => RESEARCH_ICONS[resolvedName.value])
const iconStyle = computed(() => props.color ? { color: props.color } : undefined)
</script>

<template>
  <svg
    :class="['research-icon', `research-icon--${resolvedName}`]"
    :width="size"
    :height="size"
    :style="iconStyle"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    :role="label ? 'img' : undefined"
    :aria-label="label"
    :aria-hidden="label ? undefined : 'true'"
    focusable="false"
  >
    <path v-for="path in paths" :key="path" :d="path" />
  </svg>
</template>

<style scoped>
.research-icon {
  display: inline-block;
  flex: 0 0 auto;
  vertical-align: -0.18em;
}
</style>
