<template>
  <el-dialog
    :model-value="modelValue"
    class="desktop-version-diff-dialog"
    width="min(1120px, 92vw)"
    top="6vh"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="handleClosed"
  >
    <template #header>
      <div class="dvd-dialog-heading">
        <span class="dvd-heading-mark" aria-hidden="true">Δ</span>
        <div>
          <h3>版本对比</h3>
          <p>{{ fileName || `文件 #${fileId}` }}</p>
        </div>
      </div>
    </template>

    <section class="dvd-version-picker" aria-label="选择要对比的版本">
      <div class="dvd-version-control">
        <span class="dvd-version-label">起始版本</span>
        <el-select
          v-model="fromVersion"
          class="dvd-version-select dvd-from-select"
          placeholder="选择旧版本"
          data-testid="diff-from-select"
          @change="onSelectionChange"
        >
          <el-option
            v-for="version in fromOptions"
            :key="version.id"
            :label="versionLabel(version)"
            :value="version.version_number"
          />
        </el-select>
      </div>

      <div class="dvd-direction" aria-hidden="true">
        <span class="dvd-direction-line"></span>
        <span class="dvd-direction-arrow">→</span>
      </div>

      <div class="dvd-version-control">
        <span class="dvd-version-label">目标版本</span>
        <el-select
          v-model="toVersion"
          class="dvd-version-select dvd-to-select"
          placeholder="选择新版本"
          data-testid="diff-to-select"
          @change="onSelectionChange"
        >
          <el-option
            v-for="version in toOptions"
            :key="version.id"
            :label="versionLabel(version)"
            :value="version.version_number"
          />
        </el-select>
      </div>
    </section>

    <div class="dvd-summary-strip" aria-live="polite">
      <template v-if="diffResult">
        <span class="dvd-summary-route">
          v{{ diffResult.from_version_number }} → v{{ diffResult.to_version_number }}
        </span>
        <span v-if="diffResult.is_text" class="dvd-summary-add">+{{ diffResult.additions || 0 }}</span>
        <span v-if="diffResult.is_text" class="dvd-summary-delete">−{{ diffResult.deletions || 0 }}</span>
        <span>{{ formatSignedSize(diffResult.size_delta) }}</span>
      </template>
      <span v-else>选择两个版本后自动生成对比</span>
    </div>

    <DesktopVersionDiffViewer
      :result="diffResult"
      :loading="loading"
      :error="error"
      :not-found="notFound"
      :can-retry="canCompare"
      :versions="versions"
      @retry="loadDiff"
    />

    <template #footer>
      <el-button class="dvd-close-btn" @click="closeDialog">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import DesktopVersionDiffViewer from '@/components/desktop/DesktopVersionDiffViewer.vue'
import {
  formatVersionSize,
  useVersionDiffDesktop,
  type DriveVersionOption,
} from '@/composables/useVersionDiffDesktop'

const props = defineProps<{
  modelValue: boolean
  fileId: number
  fileName?: string
  versions: DriveVersionOption[]
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const fromVersion = ref<number | null>(null)
const toVersion = ref<number | null>(null)
const { loading, error, notFound, diffResult, compareVersions, clearDiff } = useVersionDiffDesktop()

const sortedVersions = computed(() => [...props.versions].sort(
  (left, right) => left.version_number - right.version_number,
))
const fromOptions = computed(() => sortedVersions.value.filter(
  version => version.version_number !== toVersion.value,
))
const toOptions = computed(() => sortedVersions.value.filter(
  version => version.version_number !== fromVersion.value,
))
const canCompare = computed(() => (
  fromVersion.value !== null
  && toVersion.value !== null
  && fromVersion.value !== toVersion.value
))

watch(
  [() => props.modelValue, () => props.versions],
  ([visible]) => {
    if (visible) initialiseSelection()
  },
)

function initialiseSelection() {
  clearDiff()
  const values = sortedVersions.value
  if (values.length < 2) {
    fromVersion.value = values[0]?.version_number ?? null
    toVersion.value = null
    return
  }
  fromVersion.value = values[values.length - 2].version_number
  toVersion.value = values[values.length - 1].version_number
  void loadDiff()
}

function onSelectionChange() {
  clearDiff()
  if (canCompare.value) void loadDiff()
}

async function loadDiff() {
  if (!canCompare.value || fromVersion.value === null || toVersion.value === null) return
  await compareVersions(props.fileId, fromVersion.value, toVersion.value)
}

function handleClosed() {
  clearDiff()
}

function closeDialog() {
  emit('update:modelValue', false)
}

function versionLabel(version: DriveVersionOption) {
  const current = version.is_current ? ' · 当前' : ''
  return `v${version.version_number}${current}`
}

function formatSignedSize(bytes: number) {
  if (!bytes) return '大小未变化'
  const sign = bytes > 0 ? '+' : '−'
  return `${sign}${formatVersionSize(Math.abs(bytes))}`
}
</script>

<style scoped>
.dvd-dialog-heading,
.dvd-version-picker,
.dvd-version-control,
.dvd-summary-strip {
  display: flex;
  align-items: center;
}

.dvd-dialog-heading {
  gap: 12px;
}

.dvd-heading-mark {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md, 8px);
  color: var(--color-primary-dark);
  background: var(--color-primary-bg);
  border: 1px solid var(--color-primary-border);
  font: 700 20px/1 ui-monospace, SFMono-Regular, Consolas, monospace;
}

.dvd-dialog-heading h3,
.dvd-dialog-heading p {
  margin: 0;
}

.dvd-dialog-heading h3 {
  color: var(--color-text-primary);
  font-size: 18px;
}

.dvd-dialog-heading p {
  margin-top: 3px;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.dvd-version-picker {
  justify-content: center;
  gap: 20px;
  padding: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg, 12px);
  background: var(--color-bg-page);
}

.dvd-version-control {
  gap: 10px;
}

.dvd-version-label {
  color: var(--color-text-regular);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.dvd-version-select {
  width: 210px;
}

.dvd-direction {
  display: flex;
  align-items: center;
  width: 78px;
  color: var(--color-primary);
}

.dvd-direction-line {
  flex: 1;
  height: 1px;
  background: var(--color-primary-border);
}

.dvd-direction-arrow {
  font: 700 20px/1 ui-monospace, SFMono-Regular, Consolas, monospace;
}

.dvd-summary-strip {
  gap: 12px;
  min-height: 24px;
  padding: 10px 4px 8px;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.dvd-summary-route {
  color: var(--color-text-primary);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-weight: 700;
}

.dvd-summary-add {
  color: var(--color-success);
}

.dvd-summary-delete {
  color: var(--color-danger);
}

.dvd-close-btn {
  min-width: 92px;
}

@media (max-width: 760px) {
  .dvd-version-picker {
    align-items: stretch;
    flex-direction: column;
  }

  .dvd-version-control {
    justify-content: space-between;
  }

  .dvd-version-select {
    width: min(260px, 65vw);
  }

  .dvd-direction {
    display: none;
  }
}
</style>

<style>
[data-theme="dark"] .desktop-version-diff-dialog {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-base);
}
</style>
