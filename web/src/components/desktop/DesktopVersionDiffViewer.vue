<template>
  <div class="dvd-content" data-testid="version-diff-content">
    <div v-if="loading" class="dvd-state dvd-loading" v-loading="true">
      <p>正在比对两个版本…</p>
    </div>

    <div v-else-if="error" class="dvd-state dvd-error" role="alert">
      <el-icon :size="34"><WarningFilled /></el-icon>
      <strong>{{ notFound ? '版本不存在' : '无法加载对比' }}</strong>
      <p>{{ error }}</p>
      <el-button type="primary" :disabled="!canRetry" @click="emit('retry')">重新加载</el-button>
    </div>

    <template v-else-if="result">
      <div v-if="result.is_text" class="dvd-text-diff" data-testid="unified-diff">
        <div class="dvd-pane-headings" aria-hidden="true">
          <span>FROM · v{{ result.from_version_number }}</span>
          <span>TO · v{{ result.to_version_number }}</span>
        </div>

        <div v-if="diffRows.length" class="dvd-code-frame" role="table" aria-label="Unified diff 变更行">
          <div
            v-for="(row, index) in diffRows"
            :key="`${index}-${row.fromText}-${row.toText}`"
            class="dvd-split-row"
            :class="`is-${row.kind}`"
            role="row"
          >
            <code v-if="row.kind === 'hunk'" class="dvd-hunk-line">{{ row.fromText }}</code>
            <template v-else>
              <code
                class="dvd-diff-cell is-from"
                :class="{ 'is-delete': row.kind === 'change' && row.fromText !== null }"
              >
                <span class="dvd-line-marker" aria-hidden="true">{{ row.kind === 'change' && row.fromText !== null ? '−' : ' ' }}</span>
                <span>{{ row.fromText ?? ' ' }}</span>
              </code>
              <code
                class="dvd-diff-cell is-to"
                :class="{ 'is-add': row.kind === 'change' && row.toText !== null }"
              >
                <span class="dvd-line-marker" aria-hidden="true">{{ row.kind === 'change' && row.toText !== null ? '+' : ' ' }}</span>
                <span>{{ row.toText ?? ' ' }}</span>
              </code>
            </template>
          </div>
        </div>

        <div v-else class="dvd-state dvd-empty-diff">
          <el-icon :size="32"><CircleCheck /></el-icon>
          <strong>两个版本内容一致</strong>
          <p>未检测到文本行变更。</p>
        </div>
      </div>

      <div v-else class="dvd-metadata-diff" data-testid="metadata-diff">
        <div class="dvd-binary-note">
          <el-icon :size="22"><Document /></el-icon>
          <div>
            <strong>此文件使用元数据对比</strong>
            <p>{{ metadataNote }}</p>
          </div>
        </div>

        <div class="dvd-meta-table" role="table" aria-label="二进制文件版本元数据对比">
          <div class="dvd-meta-row is-heading" role="row">
            <span role="columnheader">属性</span>
            <strong role="columnheader">v{{ result.from_version_number }}</strong>
            <strong role="columnheader">v{{ result.to_version_number }}</strong>
          </div>
          <div class="dvd-meta-row" role="row">
            <span role="rowheader">文件大小</span>
            <span>{{ formatVersionSize(result.from_meta.size) }}</span>
            <span :class="{ 'is-changed': result.size_delta !== 0 }">
              {{ formatVersionSize(result.to_meta.size) }}
            </span>
          </div>
          <div class="dvd-meta-row" role="row">
            <span role="rowheader">上传者</span>
            <span>{{ uploaderName(result.from_meta.uploader_id) }}</span>
            <span :class="{ 'is-changed': result.uploader_delta }">
              {{ uploaderName(result.to_meta.uploader_id) }}
            </span>
          </div>
          <div class="dvd-meta-row" role="row">
            <span role="rowheader">上传时间</span>
            <span>{{ formatDateTime(result.from_meta.created_at) }}</span>
            <span :class="{ 'is-changed': result.from_meta.created_at !== result.to_meta.created_at }">
              {{ formatDateTime(result.to_meta.created_at) }}
            </span>
          </div>
          <div class="dvd-meta-row" role="row">
            <span role="rowheader">版本备注</span>
            <span>{{ result.from_meta.comment || '—' }}</span>
            <span :class="{ 'is-changed': result.from_meta.comment !== result.to_meta.comment }">
              {{ result.to_meta.comment || '—' }}
            </span>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="dvd-state dvd-placeholder">
      <span class="dvd-placeholder-glyph" aria-hidden="true">±</span>
      <strong>等待选择版本</strong>
      <p>起始版本与目标版本不能相同。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck, Document, WarningFilled } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/format'
import {
  formatVersionSize,
  type DriveVersionOption,
  type VersionDiffResult,
} from '@/composables/useVersionDiffDesktop'

interface DiffRow {
  kind: 'hunk' | 'context' | 'change'
  fromText: string | null
  toText: string | null
}

const props = defineProps<{
  result: VersionDiffResult | null
  loading: boolean
  error: string | null
  notFound: boolean
  canRetry: boolean
  versions: DriveVersionOption[]
}>()

const emit = defineEmits<{
  (event: 'retry'): void
}>()

function normaliseUnifiedDiff(unified: string) {
  // Backend difflib currently joins lineterm="" header records without \n.
  // Insert only the structural boundaries so both canonical and compact output parse.
  return unified
    .replace(/^--- ([^\r\n]*?)\+\+\+ /, '--- $1\n+++ ')
    .replace(/(\+\+\+ [^\r\n]*?)(@@ )/, '$1\n$2')
    .replace(/(@@ [^@\r\n]* @@)(?=[+\- ])/g, '$1\n')
}

const diffRows = computed<DiffRow[]>(() => {
  const unified = props.result?.unified_diff
  if (!unified) return []

  const rows: DiffRow[] = []
  let pendingDeletes: string[] = []
  let pendingAdds: string[] = []
  let insideHunk = false

  function flushChanges() {
    const count = Math.max(pendingDeletes.length, pendingAdds.length)
    for (let index = 0; index < count; index += 1) {
      rows.push({
        kind: 'change',
        fromText: pendingDeletes[index] ?? null,
        toText: pendingAdds[index] ?? null,
      })
    }
    pendingDeletes = []
    pendingAdds = []
  }

  for (const line of normaliseUnifiedDiff(unified).split(/\r?\n/)) {
    if (line.startsWith('---') || line.startsWith('+++')) continue
    if (line.startsWith('@@')) {
      flushChanges()
      insideHunk = true
      rows.push({ kind: 'hunk', fromText: line, toText: line })
    } else if (!insideHunk) {
      continue
    } else if (line.startsWith('-')) {
      pendingDeletes.push(line.slice(1))
    } else if (line.startsWith('+')) {
      pendingAdds.push(line.slice(1))
    } else {
      flushChanges()
      const text = line.startsWith(' ') ? line.slice(1) : line
      if (text || rows.length) rows.push({ kind: 'context', fromText: text, toText: text })
    }
  }
  flushChanges()
  return rows
})

const metadataNote = computed(() => (
  props.result?.from_meta.warning
  || props.result?.to_meta.warning
  || 'PDF、图片和压缩包等二进制内容不做逐行解析。'
))

function uploaderName(id: number) {
  const version = props.versions.find(item => item.uploader_id === id)
  return version?.uploader_name || `用户 #${id}`
}
</script>

<style scoped>
.dvd-content {
  min-height: 370px;
  max-height: 54vh;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg, 12px);
  background: var(--color-bg-card);
}

.dvd-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 368px;
  gap: 9px;
  padding: 28px;
  box-sizing: border-box;
  color: var(--color-text-secondary);
  text-align: center;
}

.dvd-state p,
.dvd-binary-note p {
  margin: 0;
}

.dvd-state strong {
  color: var(--color-text-primary);
}

.dvd-loading,
.dvd-error {
  color: var(--color-danger);
}

.dvd-placeholder-glyph {
  color: var(--color-primary);
  font: 700 48px/1 ui-monospace, SFMono-Regular, Consolas, monospace;
}

.dvd-pane-headings {
  position: sticky;
  top: 0;
  z-index: 2;
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: var(--color-bg-page);
  border-bottom: 1px solid var(--color-border);
}

.dvd-pane-headings span {
  padding: 10px 16px;
  color: var(--color-text-secondary);
  font: 700 11px/1.4 ui-monospace, SFMono-Regular, Consolas, monospace;
  letter-spacing: 0.08em;
}

.dvd-pane-headings span:last-child {
  border-left: 1px solid var(--color-border);
  text-align: right;
}

.dvd-code-frame {
  min-width: 680px;
  padding: 8px 0;
}

.dvd-split-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 24px;
  color: var(--color-text-regular);
  font: 12px/24px ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
}

.dvd-split-row + .dvd-split-row {
  border-top: 1px solid var(--color-border-light);
}

.dvd-diff-cell {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  min-width: 0;
  padding: 0;
  color: inherit;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.dvd-diff-cell.is-to {
  border-left: 1px solid var(--color-border);
}

.dvd-diff-cell > span:last-child {
  padding: 0 12px;
}

.dvd-line-marker {
  color: var(--color-text-placeholder);
  border-right: 1px solid var(--color-border-light);
  text-align: center;
  user-select: none;
}

.dvd-diff-cell.is-add {
  color: var(--color-success);
  background: var(--color-success-bg);
}

.dvd-diff-cell.is-delete {
  color: var(--color-danger);
  background: var(--color-danger-bg);
}

.dvd-hunk-line {
  grid-column: 1 / -1;
  padding: 0 14px;
  color: var(--color-primary-dark);
  background: var(--color-primary-bg);
  white-space: pre-wrap;
}

.dvd-empty-diff {
  color: var(--color-success);
}

.dvd-metadata-diff {
  padding: 22px;
}

.dvd-binary-note {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 18px;
  color: var(--color-primary-dark);
  background: var(--color-primary-bg);
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-md, 8px);
}

.dvd-binary-note p {
  margin-top: 3px;
  color: var(--color-text-regular);
  font-size: 12px;
}

.dvd-meta-table {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
}

.dvd-meta-row {
  display: grid;
  grid-template-columns: minmax(120px, 0.75fr) repeat(2, minmax(180px, 1fr));
}

.dvd-meta-row + .dvd-meta-row {
  border-top: 1px solid var(--color-border-light);
}

.dvd-meta-row > * {
  min-width: 0;
  padding: 13px 16px;
  color: var(--color-text-regular);
  overflow-wrap: anywhere;
}

.dvd-meta-row > * + * {
  border-left: 1px solid var(--color-border-light);
}

.dvd-meta-row.is-heading {
  background: var(--color-bg-page);
}

.dvd-meta-row.is-heading > * {
  color: var(--color-text-primary);
}

.dvd-meta-row .is-changed {
  color: var(--color-primary-dark);
  background: var(--color-primary-bg);
  font-weight: 600;
}
</style>
