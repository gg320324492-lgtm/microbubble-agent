<template>
  <div class="mobile-member-view">
    <PageHeader title="成员管理" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action"
          aria-label="搜索"
          title="搜索"
          @click="showSearch = true"
        >🔍</button>
        <button
          type="button"
          class="header-action primary"
          aria-label="添加"
          title="添加"
          @click="showCreate = true"
        >+</button>
      </template>
    </PageHeader>

    <main
      class="member-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
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
    </main>

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
  </div>
</template>

<script setup>
/**
 * MobileMemberView.vue — 移动端成员管理
 *
 * PR #8b: CardList + 集成 PR #5 VoiceprintEnrollFlow
 */

import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import PageHeader from '@/components/mobile/PageHeader.vue'
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
const router = useRouter()

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
  // 跳到移动端成员详情页（新建 MobileMemberDetailView，简化版：头像/邮箱/方向/声纹状态）
  router.push(`/mobile/members/${member.id}`)
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

// ============================================================================
// 添加成员（showCreate + MobileFormSheet）
// ============================================================================
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
    // 重置表单
    createForm.value = { name: '', grade: '', research_area: '', role: 'member', email: '' }
    fetchMembers()
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  fetchMembers()
})
</script>

<style scoped>
.mobile-member-view {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.member-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
  margin-left: 4px;
}
.header-action:active { background: var(--color-primary-bg); }
.header-action.primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  /* stylelint-disable-next-line color-named */
  color: white;
  font-weight: 600;
  font-size: 22px;
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
</style>