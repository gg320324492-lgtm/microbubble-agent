<!--
  CreateFolderDialog.vue — 课题组网盘 新建文件夹对话框 (批次⑩.8 档案系重绘, 2026-09-05)

  用户选型 DLG A 墨线极简:
  - 白卡墨线 12px 圆角 + mono 副标, 无渐变题头; 创建按钮 = 深青渐变 (珊瑚退役)
  - 可见性字段删除 (2026-09-05 用户拍板): 默认恒 team; 分享即公开 (后端 ⑩.7
    create/revoke/expiry 三点跟随), 撤销或过期自动回团队 — 手动选择已无意义
  - 「位置」显式展示: 右键哪个文件夹就建在哪个里面
  - 「团队共享盘展示」开关保留 (仅顶层创建时出现)

  字段: name (必填, 1-200); parentId (从父组件传入, 顶级 null)
  提交: emit('create', { name, parent_id, visibility: 'team', is_team_default })
-->
<template>
  <el-dialog
    v-model="visible"
    class="cfd-arch"
    width="420px"
    :close-on-click-modal="false"
    :show-close="true"
    @closed="resetForm"
    @open="onOpen"
  >
    <template #header>
      <div class="cfd-head">
        <div class="cfd-title">新建文件夹</div>
        <div class="cfd-sub">NEW FOLDER · MICROBUBBLE LAB DRIVE</div>
      </div>
    </template>

    <div class="cfd-body">
      <div class="cfd-fld">
        <label><em>*</em>名称 <span class="cfd-cnt">{{ form.name.length }} / 200</span></label>
        <input
          ref="nameInputRef"
          v-model="form.name"
          class="cfd-inp"
          :class="{ 'is-err': nameError }"
          placeholder="请输入文件夹名称"
          maxlength="200"
          @keydown.enter="onSubmit"
          @input="nameError = ''"
        />
        <div v-if="nameError" class="cfd-err">{{ nameError }}</div>
      </div>

      <div class="cfd-fld">
        <label>位置</label>
        <div class="cfd-loc">
          <svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>
          <span>{{ parentFolder ? parentFolder.name : '团队共享盘 · 顶层' }}</span>
        </div>
        <div v-if="parentFolder && parentFolder.depth >= 4" class="cfd-warn">
          已是 5 层结构, 此文件夹内不能再新建子文件夹
        </div>
      </div>

      <!-- 团队共享盘标识 (仅顶层创建时出现; 打勾后进团队共享盘列表) -->
      <div v-if="!parentFolder" class="cfd-fld cfd-team">
        <label>团队共享盘展示</label>
        <button
          type="button" class="cfd-switch" role="switch"
          :aria-checked="form.is_team_default"
          :class="{ 'is-on': form.is_team_default }"
          @click="form.is_team_default = !form.is_team_default"
        ><span class="cfd-knob"></span></button>
        <span class="cfd-team-hint">开启后自动列入团队共享盘页面</span>
      </div>
    </div>

    <template #footer>
      <div class="cfd-foot">
        <button type="button" class="cfd-btn ghost" @click="visible = false">取消</button>
        <button type="button" class="cfd-btn pri" :disabled="submitting" @click="onSubmit">
          {{ submitting ? '创建中…' : '创建' }}
        </button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  parentId: { type: [Number, null], default: null },
  parentFolder: { type: [Object, null], default: null }
})

const emit = defineEmits(['update:modelValue', 'create'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const submitting = ref(false)
const nameInputRef = ref(null)
const nameError = ref('')
const form = reactive({
  name: '',
  visibility: 'team',
  is_team_default: false
})

watch(visible, (v) => {
  if (v) nextTick(() => nameInputRef.value?.focus?.())
})

function resetForm() {
  form.name = ''
  form.visibility = 'team'
  form.is_team_default = false
  nameError.value = ''
}

async function onSubmit() {
  const name = form.name.trim()
  if (!name) {
    nameError.value = '请输入文件夹名称'
    nameInputRef.value?.focus?.()
    return
  }
  if (name.length > 200) {
    nameError.value = '长度 1-200 字符'
    return
  }
  submitting.value = true
  try {
    emit('create', {
      name,
      parent_id: props.parentId,
      visibility: 'team',  // 批次⑩.8: 恒 team — 公开属性改由分享行为驱动 (后端 ⑩.7)
      is_team_default: form.is_team_default
    })
  } finally {
    submitting.value = false
  }
}

defineExpose({ resetForm })
</script>

<script>
// 弹窗 teleport 到 body — 壳样式必须走非 scoped 块 (v60-v67 教训)
export default { name: 'CreateFolderDialog' }
</script>

<style>
/* ── 批次⑩.8 DLG A 壳: 白卡墨线 12px 圆角, 无 EP 默认题头底色 ── */
.cfd-arch {
  border-radius: 12px;
  border: 1px solid var(--color-border, #E5E1D8);
  box-shadow: 0 24px 64px rgba(10, 20, 16, .35);
  background: var(--color-bg-card, #fff);
  padding: 0;
  overflow: hidden;
}
.cfd-arch .el-dialog__header {
  padding: 18px 22px 0;
  margin-right: 0;
}
.cfd-arch .el-dialog__headerbtn {
  top: 16px; right: 16px;
  width: 28px; height: 28px; border-radius: 7px;
  transition: background .15s;
}
.cfd-arch .el-dialog__headerbtn:hover { background: var(--color-bg-page, #F2F0EB); }
.cfd-arch .el-dialog__body { padding: 4px 22px 18px; }
/* 页脚槽通栏: 暖纸底 + 顶部分隔线直达弹窗左右边缘 (批次⑩.8b 修 body 内嵌白边) */
.cfd-arch .el-dialog__footer {
  padding: 0;
  border-top: 1px solid var(--color-border, #E5E1D8);
  background: var(--color-bg-page, #F2F0EB);
}
</style>

<style scoped>
.cfd-head { display: flex; flex-direction: column; gap: 3px; }
.cfd-title { font-size: 15.5px; font-weight: 700; color: var(--color-text-primary); }
.cfd-sub { font-family: var(--font-mono, Consolas, monospace); font-size: 10px; letter-spacing: .14em; color: var(--color-text-placeholder); }

.cfd-body { padding-bottom: 6px; }
.cfd-fld { margin-bottom: 16px; }
.cfd-fld label { display: block; font-size: 12px; font-weight: 600; color: var(--color-text-primary); margin-bottom: 7px; }
.cfd-fld label em { font-style: normal; color: var(--color-danger); margin-right: 4px; }
.cfd-cnt { float: right; font-family: var(--font-mono, Consolas, monospace); font-size: 10.5px; color: var(--color-text-placeholder); font-weight: 400; }

.cfd-inp {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 9px 12px;
  font: inherit;
  font-size: 13px;
  color: var(--color-text-primary);
  background: var(--color-bg-card);
  outline: none;
  transition: border-color var(--duration-fast), box-shadow var(--duration-fast);
}
.cfd-inp::placeholder { color: var(--color-text-placeholder); }
.cfd-inp:focus { border-color: var(--color-primary); box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), .1); }
.cfd-inp.is-err { border-color: var(--color-danger); }
.cfd-err { margin-top: 6px; font-size: 11.5px; color: var(--color-danger); }

.cfd-loc {
  display: flex; align-items: center; gap: 6px;
  font-size: 12.5px; color: var(--color-text-regular);
  background: var(--color-bg-page);
  border: 1px solid var(--color-border);
  border-radius: 8px; padding: 8px 12px;
}
.cfd-loc svg { width: 13px; height: 13px; stroke: var(--color-primary); fill: none; stroke-width: 1.7; flex: none; }
.cfd-warn { margin-top: 6px; font-size: 11.5px; color: var(--color-warning); }

.cfd-team { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.cfd-team > label { margin-bottom: 0; }
.cfd-switch {
  flex: none; width: 36px; height: 20px; min-height: 0; border-radius: 9999px;
  border: 1px solid var(--color-border); background: var(--color-bg-page);
  position: relative; cursor: pointer; padding: 0;
  transition: background var(--duration-fast), border-color var(--duration-fast);
}
.cfd-switch .cfd-knob {
  position: absolute; top: 2px; left: 2px; width: 14px; height: 14px;
  border-radius: 50%; background: var(--color-bg-card); box-shadow: 0 1px 3px rgba(20,40,35,.25);
  transition: transform var(--duration-normal) var(--ease-out, ease);
}
.cfd-switch.is-on { background: var(--color-primary); border-color: var(--color-primary); }
.cfd-switch.is-on .cfd-knob { transform: translateX(16px); }
.cfd-team-hint { font-size: 11.5px; color: var(--color-text-secondary); }

.cfd-foot {
  display: flex; justify-content: flex-end; gap: 10px;
  padding: 13px 22px;
}
.cfd-btn { font: inherit; font-size: 13px; padding: 8px 18px; border-radius: 8px; cursor: pointer; transition: all .15s; }
.cfd-btn.ghost { border: 1px solid var(--color-border); background: var(--color-bg-card); color: var(--color-text-regular); }
.cfd-btn.ghost:hover { border-color: var(--color-primary-border); color: var(--color-primary-dark); }
.cfd-btn.pri {
  border: none; background: var(--gradient-cta-button, linear-gradient(135deg, #0E766E, #12897C));
  color: #fff; font-weight: 600;
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), .3);
}
.cfd-btn.pri:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(var(--color-primary-rgb), .32); }
.cfd-btn.pri:disabled { opacity: .6; cursor: default; transform: none; }
</style>
