<template>
  <div class="mobile-members-panel">
    <CardList
      :items="members"
      :field-config="memberFieldConfig"
      :avatar-field="(m) => m.id"
      :loading="loading"
      empty-icon="👥"
      empty-title="暂无成员"
      empty-hint="点击右上角 + 添加"
      @item-click="viewMember"
    >
      <template #item-actions="{ item }">
        <div class="member-actions">
          <button
            type="button"
            class="action-btn"
            :class="{ active: item.voice_enrolled_at }"
            @click.stop="handleVoiceprint(item)"
          >
            🎤 {{ item.voice_enrolled_at ? '已录入' : '录入声纹' }}
          </button>
        </div>
      </template>
    </CardList>

    <!-- 搜索 Sheet -->
    <MobileSearchSheet
      v-model="showSearch"
      v-model:keyword="searchKeyword"
      title="搜索成员"
      placeholder="搜索姓名..."
      :filters="searchFilters"
      v-model:filters="activeFilters"
      @confirm="onSearchConfirm"
      @reset="onSearchReset"
    />

    <!-- 声纹录入全屏流程 -->
    <VoiceprintEnrollFlow
      v-if="enrollingMember"
      v-model="showEnroll"
      :member="enrollingMember"
      @success="onEnrollSuccess"
    />

    <!-- 添加成员表单 Sheet -->
    <MobileFormSheet
      v-model:show="showCreate"
      v-model:form="createForm"
      title="添加成员"
      :fields="createFields"
      :submitting="creating"
      @submit="onCreateSubmit"
    />

    <!-- 成员详情 sheet -->
    <Teleport to="body">
      <Transition name="member-sheet">
        <div v-if="showDetail" class="sheet-overlay" @click.self="closeDetail">
          <div class="sheet-panel" :style="{ paddingBottom: 'calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))' }">
            <div class="sheet-handle" />
            <div v-if="detailMember" class="detail-content">
              <section class="hero-card">
                <div class="hero-avatar">{{ detailMember.name?.charAt(0) }}</div>
                <h2 class="hero-name">{{ detailMember.name }}</h2>
                <div class="hero-tags">
                  <el-tag size="small" :type="getRoleType(detailMember.role)">{{ getRoleLabel(detailMember.role) }}</el-tag>
                  <el-tag v-if="detailMember.grade" size="small" type="info">{{ detailMember.grade }}</el-tag>
                  <el-tag v-if="detailMember.voice_enrolled_at" size="small" type="success">🎤 已录入声纹</el-tag>
                  <el-tag v-else size="small" type="warning">未录入声纹</el-tag>
                </div>
              </section>

              <section class="info-card">
                <h3 class="info-title">基本信息</h3>
                <div class="info-row"><span class="info-label">研究方向</span><span class="info-value">{{ detailMember.research_area || '—' }}</span></div>
                <div class="info-row"><span class="info-label">邮箱</span><span class="info-value">{{ detailMember.email || '—' }}</span></div>
                <div class="info-row"><span class="info-label">手机</span><span class="info-value">{{ detailMember.phone || '—' }}</span></div>
              </section>

              <section v-if="detailMember.bio" class="info-card">
                <h3 class="info-title">个人简介</h3>
                <p class="bio-text">{{ detailMember.bio }}</p>
              </section>

              <section v-if="detailMember.skills?.length" class="info-card">
                <h3 class="info-title">技能</h3>
                <div class="skills-list">
                  <el-tag v-for="skill in detailMember.skills" :key="skill" size="small" type="info">{{ skill }}</el-tag>
                </div>
              </section>

              <section v-if="detailMember.voice_enrolled_at" class="info-card">
                <h3 class="info-title">声纹</h3>
                <div class="info-row"><span class="info-label">录入时间</span><span class="info-value">{{ formatDate(detailMember.voice_enrolled_at) }}</span></div>
                <div class="info-row"><span class="info-label">采样次数</span><span class="info-value">{{ detailMember.voice_sample_count || 1 }} 次</span></div>
              </section>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
/**
 * MobileMembersPanel.vue — v78 "团队协作" 移动端成员 tab
 *
 * 从原 web/src/views/mobile/MobileMemberView.vue 拆出 (2026-07-02):
 * - 保留: 卡片网格 + 搜索 + 声纹录入 + 添加表单
 * - 移除: 顶部 PageHeader (由父 MobileWorkspaceView 提供)
 * - 移除: 路由跳转 /mobile/members/:id (原路径不存在, v77 pre-existing bug)
 *   → 改为内嵌详情 sheet 弹层
 * - 接收 window event 'workspace:search-member' / 'workspace:create-member'
 */

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { ElMessage, ElTag } from 'element-plus'
import CardList from '@/components/mobile/CardList.vue'
import MobileSearchSheet from '@/components/mobile/MobileSearchSheet.vue'
import VoiceprintEnrollFlow from '@/components/mobile/VoiceprintEnrollFlow.vue'
import MobileFormSheet from '@/components/mobile/MobileFormSheet.vue'

const members = ref([])
const loading = ref(false)
const showSearch = ref(false)
const showCreate = ref(false)
const showEnroll = ref(false)
const enrollingMember = ref(null)
const showDetail = ref(false)
const detailMember = ref(null)

const searchKeyword = ref('')
const activeFilters = ref({ grade: '' })

const searchFilters = computed(() => [
  {
    key: 'grade',
    label: '年级',
    options: [
      { value: '', label: '全部' },
      { value: '教授', label: '教授' },
      { value: '博士后', label: '博士后' },
      { value: '博一', label: '博一' },
      { value: '博二', label: '博二' },
      { value: '研一', label: '研一' },
      { value: '研二', label: '研二' },
      { value: '研三', label: '研三' },
    ],
  },
])

const memberFieldConfig = computed(() => ({
  title: (m) => m.name,
  subtitle: (m) => `${m.role || ''} · ${m.grade || ''}`,
  badge: (m) => ({
    label: m.voice_enrolled_at ? '✓ 声纹' : '未录入',
    type: m.voice_enrolled_at ? 'success' : 'info',
  }),
  fields: (m) => [
    { key: 'email', label: '邮箱', value: m.email || '—' },
    { key: 'research', label: '方向', value: m.research_area || '—' },
  ],
}))

async function fetchMembers() {
  loading.value = true
  try {
    const params = {}
    if (searchKeyword.value) params.name = searchKeyword.value
    if (activeFilters.value.grade) params.grade = activeFilters.value.grade
    const res = await axios.get('/api/v1/members', { params })
    members.value = res.data?.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function onSearchConfirm({ keyword, filters }) {
  searchKeyword.value = keyword
  Object.assign(activeFilters.value, filters)
  fetchMembers()
}

function onSearchReset() {
  searchKeyword.value = ''
  activeFilters.value = { grade: '' }
  fetchMembers()
}

function viewMember(member) {
  detailMember.value = member
  showDetail.value = true
}

function closeDetail() {
  showDetail.value = false
  detailMember.value = null
}

function handleVoiceprint(member) {
  enrollingMember.value = member
  showEnroll.value = true
}

function onEnrollSuccess() {
  showEnroll.value = false
  enrollingMember.value = null
  fetchMembers()
}

// ====== 添加成员表单 ======
const createForm = ref({
  name: '',
  grade: '',
  research_area: '',
  role: 'member',
  email: '',
})
const creating = ref(false)

const createFields = computed(() => [
  { key: 'name', label: '姓名', type: 'input', required: true, placeholder: '请输入姓名' },
  {
    key: 'grade',
    label: '年级',
    type: 'select',
    options: [
      { value: '', label: '请选择' },
      { value: '教授', label: '教授' },
      { value: '副教授', label: '副教授' },
      { value: '博士后', label: '博士后' },
      { value: '博一', label: '博一' },
      { value: '博二', label: '博二' },
      { value: '研一', label: '研一' },
      { value: '研二', label: '研二' },
      { value: '研三', label: '研三' },
    ],
  },
  { key: 'research_area', label: '研究方向', type: 'input', placeholder: '如：气泡生成、水处理' },
  {
    key: 'role',
    label: '角色',
    type: 'radio',
    required: true,
    options: [
      { value: 'admin', label: '管理员' },
      { value: 'leader', label: '组长' },
      { value: 'member', label: '成员' },
    ],
  },
  { key: 'email', label: '邮箱', type: 'input', placeholder: 'example@mnb-lab.cn' },
])

async function onCreateSubmit(form) {
  if (!form.name) {
    ElMessage.warning('请输入姓名')
    return
  }
  creating.value = true
  try {
    await axios.post('/api/v1/members', form)
    ElMessage.success('成员添加成功')
    showCreate.value = false
    createForm.value = { name: '', grade: '', research_area: '', role: 'member', email: '' }
    fetchMembers()
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

function getRoleType(role) {
  const map = { admin: 'danger', leader: 'warning', member: 'info' }
  return map[role] || 'info'
}

function getRoleLabel(role) {
  const map = { admin: '管理员', leader: '组长', member: '成员' }
  return map[role] || role || '成员'
}

function formatDate(t) {
  if (!t) return ''
  // 简单格式: 2026-07-02 11:30
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ====== 接收父级 header 按钮事件 ======
function onWorkspaceSearchMember() { showSearch.value = true }
function onWorkspaceCreateMember() { showCreate.value = true }

onMounted(() => {
  fetchMembers()
  window.addEventListener('workspace:search-member', onWorkspaceSearchMember)
  window.addEventListener('workspace:create-member', onWorkspaceCreateMember)
})

onBeforeUnmount(() => {
  window.removeEventListener('workspace:search-member', onWorkspaceSearchMember)
  window.removeEventListener('workspace:create-member', onWorkspaceCreateMember)
})
</script>

<style scoped>
.mobile-members-panel {
  padding: 12px 16px;
}

.member-actions {
  margin-top: 6px;
}
.action-btn {
  width: 100%;
  padding: 8px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 12px;
  background: var(--color-bg-page);
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.action-btn.active {
  background: var(--color-success-bg);
  color: var(--color-success, #67C23A);
}
.action-btn:active { opacity: 0.7; }

/* ===== 详情 sheet ===== */
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}
.sheet-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 20px;
  max-height: 80vh;
  overflow-y: auto;
}
.sheet-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 16px;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 0 16px;
}

.hero-card {
  text-align: center;
  padding: 24px 16px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-lg);
  /* stylelint-disable-next-line color-named */
  color: white;
}
.hero-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  border: 2px solid rgba(255, 255, 255, 0.4);
  font-size: 28px;
  font-weight: var(--font-weight-semibold, 600);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
}
.hero-name {
  margin: 0 0 12px;
  font-size: 20px;
  font-weight: var(--font-weight-semibold, 600);
}
.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}
.hero-tags :deep(.el-tag) {
  background: rgba(255, 255, 255, 0.2);
  /* stylelint-disable-next-line color-named */
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.info-card {
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  padding: 16px;
}
.info-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-regular);
}
.info-row {
  display: flex;
  font-size: 13px;
  padding: 6px 0;
}
.info-label {
  flex: 0 0 80px;
  color: var(--color-text-secondary);
}
.info-value {
  flex: 1;
  color: var(--color-text-primary);
  overflow-wrap: anywhere;
}
.bio-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-primary);
  white-space: pre-wrap;
}
.skills-list {
  display: flex;
  flex-wrap: wrap;
}

.member-sheet-enter-active, .member-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.member-sheet-enter-active .sheet-panel, .member-sheet-leave-active .sheet-panel {
  transition: transform 0.3s var(--ease-sheet);
}
.member-sheet-enter-from, .member-sheet-leave-to { opacity: 0; }
.member-sheet-enter-from .sheet-panel, .member-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
[data-theme="dark"] .sheet-panel {
  background: var(--color-bg-card);
}
[data-theme="dark"] .info-card {
  background: var(--color-bg-page);
}
</style>