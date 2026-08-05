<template>
  <div class="dft-view">
    <el-card class="header-card card fade-slide-up stagger-1">
      <div class="header-row">
        <div>
          <h2 class="page-title">⚛️ DFT/MD 计算工作台</h2>
          <p class="page-subtitle">微纳米气泡智能计算 — Gaussian 16W · GROMACS · MACE · PySCF</p>
        </div>
        <div class="tool-health">
          <span class="label">工具状态:</span>
          <el-tag
            v-for="t in (tools?.tools || [])"
            :key="t.name"
            :type="t.available ? 'success' : 'info'"
            size="small"
            effect="light"
            class="tool-tag"
          >
            {{ t.name }}
            <el-icon v-if="t.available" class="check-icon"><Check /></el-icon>
          </el-tag>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="activeTab" class="dft-tabs fade-slide-up stagger-2">
      <!-- Tab 1: GROMACS MD (主推) -->
      <el-tab-pane label="🧪 GROMACS MD" name="gromacs">
        <el-card class="form-card card">
          <el-form :model="gromacsForm" label-width="160px" class="dft-form">
            <el-form-item label="分子 SMILES">
              <el-input
                v-model="gromacsForm.smiles"
                placeholder="例如: CCO (乙醇), O (水), CCCCCCCCCOS(=O)(=O)O[Na] (SDS)"
                clearable
              />
              <span class="form-hint">支持任意 SMILES 字符串</span>
            </el-form-item>
            <el-form-item label="分子数">
              <el-input-number v-model="gromacsForm.n_molecules" :min="1" :max="1000" />
              <span class="form-hint">盒子内分子数 (默认 100)</span>
            </el-form-item>
            <el-form-item label="盒子边长 (nm)">
              <el-input-number v-model="gromacsForm.box_nm" :min="1.0" :max="20.0" :step="0.5" />
              <span class="form-hint">立方盒子边长 (默认 3.0 nm)</span>
            </el-form-item>
            <el-form-item label="模拟时间 (ns)">
              <el-input-number v-model="gromacsForm.time_ns" :min="0.1" :max="100.0" :step="0.5" />
              <span class="form-hint">MD 模拟时长 (默认 1.0 ns)</span>
            </el-form-item>
            <el-form-item label="温度 (K)">
              <el-input-number v-model="gromacsForm.temperature_K" :min="100" :max="500" :step="10" />
              <span class="form-hint">NVT/NPT 目标温度 (默认 300 K)</span>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                class="btn btn-primary submit-btn"
                :loading="submitting === 'gromacs'"
                @click="onSubmitGromacs"
              >
                <el-icon><VideoPlay /></el-icon>
                提交 GROMACS MD
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- Tab 2: Gaussian 16W -->
      <el-tab-pane label="🔬 Gaussian 16W" name="gaussian">
        <el-card class="form-card card">
          <el-form :model="gaussianForm" label-width="160px" class="dft-form">
            <el-form-item label="分子 SMILES">
              <el-input v-model="gaussianForm.smiles" placeholder="例如: CCO" clearable />
            </el-form-item>
            <el-form-item label="泛函 (xc)">
              <el-select v-model="gaussianForm.xc">
                <el-option label="B3LYP (默认)" value="B3LYP" />
                <el-option label="M06-2X" value="M06-2X" />
                <el-option label="ωB97X-D" value="WB97XD" />
                <el-option label="CAM-B3LYP" value="CAM-B3LYP" />
              </el-select>
            </el-form-item>
            <el-form-item label="基组 (basis)">
              <el-select v-model="gaussianForm.basis">
                <el-option label="6-31G(d) (默认)" value="6-31G(d)" />
                <el-option label="6-311++G(d,p)" value="6-311++G(d,p)" />
                <el-option label="def2-TZVP" value="def2-TZVP" />
                <el-option label="cc-pVTZ" value="cc-pVTZ" />
              </el-select>
            </el-form-item>
            <el-form-item label="任务类型">
              <el-select v-model="gaussianForm.job">
                <el-option label="SP (单点)" value="sp" />
                <el-option label="Opt (几何优化)" value="opt" />
                <el-option label="Freq (频率)" value="freq" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                class="btn btn-primary submit-btn"
                :loading="submitting === 'gaussian'"
                @click="onSubmitGaussian"
              >
                <el-icon><VideoPlay /></el-icon>
                提交 Gaussian
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- Tab 3: MACE 快速优化 -->
      <el-tab-pane label="🚀 MACE 快速优化" name="mace">
        <el-card class="form-card card">
          <el-form :model="maceForm" label-width="160px" class="dft-form">
            <el-form-item label="分子 SMILES">
              <el-input v-model="maceForm.smiles" placeholder="例如: CCO" clearable />
            </el-form-item>
            <el-form-item label="模型">
              <el-select v-model="maceForm.model">
                <el-option label="small (最快)" value="small" />
                <el-option label="medium (推荐)" value="medium" />
                <el-option label="large (最精确)" value="large" />
              </el-select>
            </el-form-item>
            <el-form-item label="收敛力阈值 (eV/Å)">
              <el-input-number v-model="maceForm.fmax_ev_A" :min="0.01" :max="1.0" :step="0.01" />
            </el-form-item>
            <el-form-item label="最大优化步数">
              <el-input-number v-model="maceForm.max_steps" :min="10" :max="500" :step="50" />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                class="btn btn-primary submit-btn"
                :loading="submitting === 'mace'"
                @click="onSubmitMace"
              >
                <el-icon><VideoPlay /></el-icon>
                提交 MACE 优化 (GPU)
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- Tab 4: PySCF 纯开源 DFT -->
      <el-tab-pane label="🐍 PySCF" name="pyscf">
        <el-card class="form-card card">
          <el-form :model="pyscfForm" label-width="160px" class="dft-form">
            <el-form-item label="分子 SMILES">
              <el-input v-model="pyscfForm.smiles" placeholder="例如: CCO" clearable />
            </el-form-item>
            <el-form-item label="方法">
              <el-select v-model="pyscfForm.method">
                <el-option label="HF" value="HF" />
                <el-option label="B3LYP" value="B3LYP" />
                <el-option label="M06-2X" value="M06-2X" />
                <el-option label="ωB97X-D" value="WB97XD" />
                <el-option label="MP2" value="MP2" />
                <el-option label="CCSD" value="CCSD" />
              </el-select>
            </el-form-item>
            <el-form-item label="基组">
              <el-select v-model="pyscfForm.basis">
                <el-option label="6-31G*" value="6-31G*" />
                <el-option label="cc-pVDZ" value="cc-pVDZ" />
                <el-option label="cc-pVTZ" value="cc-pVTZ" />
                <el-option label="def2-TZVP" value="def2-TZVP" />
              </el-select>
            </el-form-item>
            <el-form-item label="操作">
              <el-select v-model="pyscfForm.operation">
                <el-option label="energy (单点)" value="energy" />
                <el-option label="optimize (几何优化)" value="optimize" />
                <el-option label="frequencies (频率)" value="frequencies" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                class="btn btn-primary submit-btn"
                :loading="submitting === 'pyscf'"
                @click="onSubmitPyscf"
              >
                <el-icon><VideoPlay /></el-icon>
                提交 PySCF (WSL)
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 任务状态面板 -->
    <el-card v-if="recentTasks.length" class="status-card card fade-slide-up stagger-3">
      <h3 class="section-title">📊 最近任务</h3>
      <el-table :data="recentTasks" stripe>
        <el-table-column prop="task_id" label="Task ID" width="280" />
        <el-table-column prop="tool" label="工具" width="120" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="submit_time" label="提交时间" width="200" />
        <el-table-column prop="result" label="结果">
          <template #default="{ row }">
            <span v-if="row.result">{{ formatResult(row) }}</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, VideoPlay } from '@element-plus/icons-vue'
import {
  fetchDftTools,
  submitGaussian,
  submitGromacs,
  submitMace,
  submitPyscf,
  fetchDftStatus,
} from '@/api/dft'

const activeTab = ref('gromacs')
const submitting = ref(null)
const tools = ref(null)
const recentTasks = ref([])

const gromacsForm = ref({
  smiles: 'CCO',
  n_molecules: 100,
  box_nm: 3.0,
  time_ns: 1.0,
  temperature_K: 300,
})

const gaussianForm = ref({
  smiles: 'CCO',
  xc: 'B3LYP',
  basis: '6-31G(d)',
  job: 'opt',
})

const maceForm = ref({
  smiles: 'CCO',
  model: 'medium',
  fmax_ev_A: 0.05,
  max_steps: 200,
})

const pyscfForm = ref({
  smiles: 'CCO',
  method: 'B3LYP',
  basis: '6-31G*',
  operation: 'energy',
})

let pollTimer = null

const statusTagType = (status) => {
  const map = {
    queued: 'info',
    running: 'warning',
    done: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const formatResult = (row) => {
  if (!row.result) return ''
  if (row.result.energy_hartree) return `E = ${row.result.energy_hartree.toFixed(6)} Hartree`
  if (row.result.energy_ev) return `E = ${row.result.energy_ev.toFixed(4)} eV`
  if (row.result.trajectory_path) return `轨迹: ${row.result.trajectory_path}`
  return JSON.stringify(row.result).slice(0, 80)
}

const loadTools = async () => {
  try {
    tools.value = await fetchDftTools()
  } catch (e) {
    console.error('Failed to load tools:', e)
  }
}

const onSubmitGromacs = async () => {
  submitting.value = 'gromacs'
  try {
    const resp = await submitGromacs(gromacsForm.value)
    if (resp.task_id) {
      recentTasks.value.unshift({
        task_id: resp.task_id,
        tool: 'gromacs',
        status: resp.status || 'queued',
        submit_time: new Date().toLocaleString(),
        result: null,
      })
      ElMessage.success(`GROMACS 任务已提交: ${resp.task_id}`)
      startPolling()
    }
  } catch (e) {
    ElMessage.error(`提交失败: ${e.message}`)
  } finally {
    submitting.value = null
  }
}

const onSubmitGaussian = async () => {
  submitting.value = 'gaussian'
  try {
    const resp = await submitGaussian(gaussianForm.value)
    if (resp.task_id) {
      recentTasks.value.unshift({
        task_id: resp.task_id,
        tool: 'gaussian',
        status: resp.status || 'queued',
        submit_time: new Date().toLocaleString(),
        result: null,
      })
      ElMessage.success(`Gaussian 任务已提交: ${resp.task_id}`)
      startPolling()
    }
  } catch (e) {
    ElMessage.error(`提交失败: ${e.message}`)
  } finally {
    submitting.value = null
  }
}

const onSubmitMace = async () => {
  submitting.value = 'mace'
  try {
    const resp = await submitMace(maceForm.value)
    if (resp.task_id) {
      recentTasks.value.unshift({
        task_id: resp.task_id,
        tool: 'mace',
        status: resp.status || 'queued',
        submit_time: new Date().toLocaleString(),
        result: null,
      })
      ElMessage.success(`MACE 任务已提交: ${resp.task_id}`)
      startPolling()
    }
  } catch (e) {
    ElMessage.error(`提交失败: ${e.message}`)
  } finally {
    submitting.value = null
  }
}

const onSubmitPyscf = async () => {
  submitting.value = 'pyscf'
  try {
    const resp = await submitPyscf(pyscfForm.value)
    if (resp.task_id) {
      recentTasks.value.unshift({
        task_id: resp.task_id,
        tool: 'pyscf',
        status: resp.status || 'queued',
        submit_time: new Date().toLocaleString(),
        result: null,
      })
      ElMessage.success(`PySCF 任务已提交: ${resp.task_id}`)
      startPolling()
    }
  } catch (e) {
    ElMessage.error(`提交失败: ${e.message}`)
  } finally {
    submitting.value = null
  }
}

const startPolling = () => {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    const tasks = recentTasks.value.filter((t) => t.status === 'queued' || t.status === 'running')
    for (const task of tasks) {
      try {
        const status = await fetchDftStatus(task.task_id)
        if (status.status !== task.status) {
          task.status = status.status
          if (status.status === 'done' || status.status === 'failed') {
            task.result = status.result || null
          }
        }
      } catch (e) {
        console.warn(`Status poll failed for ${task.task_id}:`, e)
      }
    }
    if (!recentTasks.value.some((t) => t.status === 'queued' || t.status === 'running')) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }, 3000)
}

onMounted(() => {
  loadTools()
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.dft-view {
  padding: 24px;
  max-width: 1280px;
  margin: 0 auto;
}

.header-card {
  margin-bottom: 16px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.page-title {
  margin: 0 0 4px 0;
  color: var(--color-primary, #FF7A5C);
  font-size: 24px;
  font-weight: 600;
}

.page-subtitle {
  margin: 0;
  color: var(--el-text-color-secondary, #909399);
  font-size: 14px;
}

.tool-health {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.tool-health .label {
  font-size: 13px;
  color: var(--el-text-color-secondary, #909399);
}

.tool-tag {
  font-family: monospace;
}

.check-icon {
  margin-left: 4px;
  font-weight: bold;
}

.dft-tabs {
  margin-bottom: 16px;
}

.form-card {
  margin-bottom: 16px;
}

.dft-form {
  max-width: 720px;
}

.form-hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}

.submit-btn {
  margin-top: 8px;
  min-width: 220px;
}

.status-card {
  margin-top: 16px;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-primary, #FF7A5C);
}

@media (max-width: 768px) {
  .dft-view {
    padding: 12px;
  }
  .header-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
