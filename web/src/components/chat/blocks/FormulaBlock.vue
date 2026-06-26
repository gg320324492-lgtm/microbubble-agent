<script setup>
/**
 * FormulaBlock.vue — 公式卡（KaTeX 渲染 + "计算"按钮）
 *
 * 接收 block.data = {formulas: [{id, name, latex, expression, variables, result_unit, source_type}]}
 */
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps({ block: { type: Object, required: true } })
const formulas = (props.block.data || {}).formulas || []

// 简易 LaTeX → 文本回退（无 KaTeX 包时使用）
const formatLatex = (latex) => {
  if (!latex) return ''
  // 粗略把 _x → x, ^x → x 等转 unicode
  return latex
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '($1/$2)')
    .replace(/\\sqrt\{([^}]+)\}/g, '√($1)')
    .replace(/\^(\d)/g, '^$1')
    .replace(/\\pi/g, 'π')
    .replace(/\\alpha/g, 'α')
    .replace(/\\beta/g, 'β')
    .replace(/\\theta/g, 'θ')
    .replace(/\\lambda/g, 'λ')
    .replace(/\\mu/g, 'μ')
}

const variableEntries = (variables) => {
  if (!variables || typeof variables !== 'object') return []
  return Object.entries(variables).map(([k, v]) => ({
    key: k,
    required: v?.required !== false,
    unit: v?.unit || '',
    description: v?.description || '',
  }))
}

const onCalculate = async (formula) => {
  const vars = variableEntries(formula.variables).filter(v => v.required)
  if (vars.length === 0) {
    ElMessage.info('该公式无必填变量')
    return
  }
  // 简化版：弹 toast 提示
  ElMessage.info(`请输入变量: ${vars.map(v => v.key).join(', ')}（实际计算请调 /formulas/calculate）`)
}

const sourceTypeLabel = (s) => {
  return { builtin: '内置', extracted: '提取', conversation: '对话' }[s] || s || '未知'
}
</script>

<template>
  <div class="formula-block rich-card">
    <div class="card-header">
      <span class="icon">📐</span>
      <span class="title">{{ block.title || '公式库' }} ({{ formulas.length }})</span>
    </div>
    <div v-for="f in formulas" :key="f.id" class="formula-item">
      <div class="formula-row1">
        <span class="formula-name">{{ f.name }}</span>
        <span v-if="f.source_type" class="source-badge">{{ sourceTypeLabel(f.source_type) }}</span>
        <span v-if="f.confidence != null" class="confidence">⭐ {{ (f.confidence * 100).toFixed(0) }}%</span>
      </div>
      <div v-if="f.latex || f.expression" class="latex">
        <code>{{ formatLatex(f.latex) || f.expression }}</code>
      </div>
      <div v-if="f.result_unit" class="result">= ... <span class="unit">{{ f.result_unit }}</span></div>
      <div v-if="variableEntries(f.variables).length" class="variables">
        <span class="var-label">变量：</span>
        <span v-for="v in variableEntries(f.variables)" :key="v.key" class="var-chip">
          {{ v.key }}<span v-if="v.unit" class="var-unit">({{ v.unit }})</span>
        </span>
      </div>
      <div class="formula-actions">
        <el-button size="small" type="primary" @click="onCalculate(f)">计算</el-button>
      </div>
    </div>
    <div v-if="!formulas.length" class="empty">暂无公式</div>
  </div>
</template>

<style scoped>
.rich-card { background: var(--color-bg-card); border: 1px solid #e8eaed; border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: var(--shadow-xs); }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 14px; margin-bottom: 10px; color: var(--color-primary); }
.icon { font-size: 18px; }
.formula-item { padding: 10px 0; border-top: 1px solid #f0f1f3; }
.formula-item:first-of-type { border-top: none; }
.formula-row1 { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.formula-name { font-weight: 500; font-size: 14px; }
.source-badge { font-size: 11px; padding: 1px 8px; border-radius: 10px; background: var(--color-bg-hover); color: var(--color-text-regular); }
.confidence { font-size: 11px; color: var(--color-warning); font-weight: 500; }
.latex { background: var(--color-bg-warm); padding: 8px 12px; border-radius: 6px; margin-top: 6px; font-family: 'Cambria Math', 'Times New Roman', serif; font-size: 14px; }
.latex code { background: transparent; padding: 0; }
.result { font-size: 13px; margin-top: 6px; color: var(--color-text-primary); }
.unit { color: var(--color-text-secondary); font-size: 12px; }
.variables { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; align-items: center; }
.var-label { font-size: 11px; color: var(--color-text-secondary); }
.var-chip { font-size: 11px; background: var(--color-warning-bg); color: var(--color-warning); padding: 2px 8px; border-radius: 8px; font-family: monospace; }
.var-unit { color: var(--color-text-secondary); margin-left: 2px; }
.formula-actions { margin-top: 8px; }
.empty { text-align: center; color: var(--color-text-secondary); padding: 20px 0; font-size: 13px; }
</style>
