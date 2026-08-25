<template>
  <div class="migration-center" data-testid="migration-center">
    <header class="migration-center__header">
      <h1>迁移中心</h1>
      <p class="migration-center__hint">
        网页端是只读来源。导入的 <code>.mbrp</code> 包会写入本地工作区，可以编辑但不影响网页。
      </p>
    </header>

    <section class="migration-center__section">
      <h2>1. 预检</h2>
      <div class="migration-center__row">
        <input
          type="text"
          data-testid="package-path"
          placeholder="/absolute/path/to/snapshot.mbrp"
          v-model="packagePath"
        />
        <button data-testid="preflight-btn" :disabled="!packagePath || loading" @click="runPreflight">
          预检
        </button>
      </div>
      <pre v-if="preflightResult" data-testid="preflight-result">{{ preflightSummary }}</pre>
    </section>

    <section class="migration-center__section">
      <h2>2. 导入</h2>
      <button data-testid="import-btn" :disabled="loading" @click="runImport">
        导入到本地工作区
      </button>
      <pre v-if="importResult" data-testid="import-result">{{ importSummary }}</pre>
    </section>

    <section class="migration-center__section">
      <h2>3. 历史记录</h2>
      <ul data-testid="run-list">
        <li v-for="run in runs" :key="run.run_id ?? run.runId ?? String(run.id ?? '')">
          {{ run.snapshot_id ?? run.snapshotId ?? run.id }} — {{ run.status ?? 'pending' }}
        </li>
        <li v-if="!runs.length">暂无记录</li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

interface ResultLike {
  ok: boolean
  code?: string
  message?: string
  runId?: string
  filesWritten?: number
}

interface WindowMigration {
  preflight: (packagePath: string) => Promise<ResultLike>
  import: (packagePath: string, snapshotId: string) => Promise<ResultLike>
  runs: () => Promise<unknown>
}

interface MigrationBridge {
  migration?: WindowMigration
}

function getMigration(): WindowMigration | undefined {
  return (globalThis as unknown as MigrationBridge).window?.migration
}

const packagePath = ref<string>('')
const preflightResult = ref<ResultLike | null>(null)
const importResult = ref<ResultLike | null>(null)
const runs = ref<Array<Record<string, unknown>>>([])
const loading = ref(false)

const preflightSummary = computed(() => {
  const r = preflightResult.value
  if (!r) return ''
  if (r.ok) return '✓ 包校验通过'
  return '✗ ' + (r.code ?? 'ERROR') + ': ' + (r.message ?? '')
})

const importSummary = computed(() => {
  const r = importResult.value
  if (!r) return ''
  if (r.ok) return '✓ 导入成功（runId: ' + (r.runId ?? '?') + '，文件: ' + (r.filesWritten ?? 0) + '）'
  return '✗ ' + (r.code ?? 'ERROR') + ': ' + (r.message ?? '')
})

async function runPreflight(): Promise<void> {
  if (!packagePath.value) return
  loading.value = true
  try {
    const w = getMigration()
    if (!w) {
      preflightResult.value = { ok: false, code: 'NO_BRIDGE', message: '迁移桥接未注入' }
      return
    }
    preflightResult.value = await w.preflight(packagePath.value)
  } finally {
    loading.value = false
  }
}

async function runImport(): Promise<void> {
  if (!packagePath.value) return
  loading.value = true
  try {
    const w = getMigration()
    if (!w) {
      importResult.value = { ok: false, code: 'NO_BRIDGE', message: '迁移桥接未注入' }
      return
    }
    importResult.value = await w.import(packagePath.value, 'snap-' + Date.now())
  } finally {
    loading.value = false
  }
}

async function loadRuns(): Promise<void> {
  const w = getMigration()
  if (!w) return
  const list = await w.runs()
  runs.value = Array.isArray(list) ? (list as Array<Record<string, unknown>>) : []
}

onMounted(loadRuns)

defineExpose({ packagePath, runPreflight, runImport, loadRuns, preflightResult, importResult, runs })
</script>

<style scoped>
.migration-center { padding: 1.5rem; max-width: 960px; }
.migration-center__header h1 { margin: 0 0 0.5rem; font-size: 1.5rem; }
.migration-center__hint { color: #555; font-size: 0.9rem; }
.migration-center__section { margin-top: 1.5rem; padding: 1rem; border: 1px solid #e5e7eb; border-radius: 8px; background: #fafafa; }
.migration-center__row { display: flex; gap: 0.5rem; align-items: center; }
input[type="text"] { flex: 1; padding: 0.4rem 0.6rem; border: 1px solid #ccc; border-radius: 4px; }
button { padding: 0.4rem 1rem; border: 0; border-radius: 4px; background: #2563eb; color: white; cursor: pointer; }
button:disabled { background: #cbd5e1; cursor: not-allowed; }
pre { margin: 0.75rem 0 0; padding: 0.5rem; background: #f1f5f9; border-radius: 4px; font-family: ui-monospace, monospace; font-size: 0.85rem; }
ul { list-style: none; padding: 0; margin: 0.5rem 0 0; }
li { padding: 0.35rem 0; border-bottom: 1px solid #e5e7eb; font-size: 0.9rem; }
li:last-child { border-bottom: 0; }
</style>
