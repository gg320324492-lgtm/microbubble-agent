<template>
  <div class="member-view">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="24" :sm="12" :md="8">
          <el-input
            v-model="searchName"
            name="member-list-search"
            placeholder="搜索成员姓名"
            clearable
            @keyup.enter="fetchMembers"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :xs="12" :sm="12" :md="8">
          <el-select v-model="searchGrade" name="searchGrade" placeholder="年级" aria-label="年级筛选" clearable>
            <el-option label="教授" value="教授" />
            <el-option label="博士后" value="博士后" />
            <el-option label="博一" value="博一" />
            <el-option label="博二" value="博二" />
            <el-option label="研一" value="研一" />
            <el-option label="研二" value="研二" />
            <el-option label="研三" value="研三" />
          </el-select>
        </el-col>
        <el-col :xs="12" :sm="12" :md="8">
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            添加成员
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 成员卡片列表 -->
    <div class="member-grid">
      <el-card
        v-for="member in members"
        :key="member.id"
        class="member-card"
        shadow="hover"
      >
        <!-- 声纹状态徽章（右上角） -->
        <div class="voiceprint-badge">
          <el-tooltip
            v-if="member.voice_enrolled_at"
            :content="`已录入（${member.voice_sample_count || 0} 次采样，更新于 ${formatEnrollTime(member.voice_enrolled_at)}）`"
            placement="top"
          >
            <el-tag type="success" size="small" effect="dark">
              <el-icon><Microphone /></el-icon>
              声纹✓
            </el-tag>
          </el-tooltip>
          <el-tooltip v-else content="尚未录入声纹，会议中无法自动识别" placement="top">
            <el-tag type="info" size="small" effect="plain">
              <el-icon><Microphone /></el-icon>
              未录入声纹
            </el-tag>
          </el-tooltip>
        </div>

        <div class="member-avatar">
          <el-avatar v-if="member.avatar" :size="64" :src="member.avatar" :alt="`${member.name}的头像`" />
          <el-avatar v-else :size="64" :class="`avatar-color-${getAvatarIndex(member.name)}`" :alt="`${member.name}的头像`">
            {{ member.name.charAt(0) }}
          </el-avatar>
        </div>

        <div class="member-info">
          <h3 class="member-name">{{ member.name }}</h3>
          <el-tag size="small">{{ member.grade }}</el-tag>
          <div class="member-role">
            <el-tag :type="getRoleType(member.role)" size="small">
              {{ getRoleLabel(member.role) }}
            </el-tag>
          </div>
        </div>

        <div class="member-detail">
          <div class="detail-item">
            <el-icon><Location /></el-icon>
            <span>{{ member.research_area || '未设置' }}</span>
          </div>
          <div class="detail-item">
            <el-icon><Message /></el-icon>
            <span>{{ member.email || '未设置' }}</span>
          </div>
        </div>

        <div class="member-skills">
          <el-tag
            v-for="skill in displaySkills(member)"
            :key="skill"
            size="small"
            type="info"
            style="margin: 2px"
          >
            {{ skill }}
          </el-tag>
        </div>

        <div class="member-actions">
          <el-button
            :type="member.voice_enrolled_at ? 'default' : 'primary'"
            :plain="!member.voice_enrolled_at"
            size="small"
            @click="openEnrollDialog(member)"
          >
            <el-icon><Microphone /></el-icon>
            {{ member.voice_enrolled_at ? '更新声纹' : '录入声纹' }}
          </el-button>
          <el-button text type="primary" size="small" @click="editMember(member)">编辑</el-button>
          <el-button text size="small" @click="viewTasks(member)">查看任务</el-button>
        </div>
      </el-card>
    </div>

    <!-- 创建/编辑成员对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingMember ? '编辑成员' : '添加成员'"
      :width="isMobile ? '90vw' : '500px'"
      top="8vh"
    >
      <el-form :model="memberForm" label-width="80px">
        <el-form-item label="姓名" required>
          <el-input v-model="memberForm.name" name="member-form-name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="memberForm.grade" name="member-form-grade" placeholder="选择年级" aria-label="年级">
            <el-option label="教授" value="教授" />
            <el-option label="博士后" value="博士后" />
            <el-option label="博一" value="博一" />
            <el-option label="博二" value="博二" />
            <el-option label="研一" value="研一" />
            <el-option label="研二" value="研二" />
            <el-option label="研三" value="研三" />
          </el-select>
        </el-form-item>
        <el-form-item label="研究方向">
          <el-input v-model="memberForm.research_area" name="member-form-research-area" placeholder="如：气泡生成、水处理" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="memberForm.role" name="member-form-role" aria-label="角色">
            <el-option label="管理员" value="admin" />
            <el-option label="组长" value="leader" />
            <el-option label="成员" value="member" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="memberForm.email" name="member-form-email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机">
          <el-input v-model="memberForm.phone" name="member-form-phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="技能">
          <el-select
            v-model="memberForm.skills"
            name="member-form-skills"
            multiple
            filterable
            allow-create
            placeholder="输入技能标签"
            aria-label="技能标签"
          >
            <el-option label="NTA" value="NTA" />
            <el-option label="DLS" value="DLS" />
            <el-option label="Python" value="Python" />
            <el-option label="数据分析" value="数据分析" />
            <el-option label="文献调研" value="文献调研" />
            <el-option label="实验设计" value="实验设计" />
          </el-select>
        </el-form-item>
        <el-form-item label="个人简介">
          <el-input
            v-model="memberForm.bio"
            name="member-form-bio"
            type="textarea"
            :rows="2"
            placeholder="请输入个人简介"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveMember">{{ editingMember ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>

    <!-- 声纹录入弹窗 -->
    <VoiceprintEnrollDialog
      v-model="enrollDialogVisible"
      :member="enrollMember"
      @success="onEnrollSuccess"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone, Search, Plus, Location, Message } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useMemberStore } from '@/stores/member'
import VoiceprintEnrollDialog from '@/components/VoiceprintEnrollDialog.vue'
import { getDisplaySkills } from '@/utils/researchAreaSkills'

const router = useRouter()
const memberStore = useMemberStore()

// 年级排序（从高到低）。2026-06-30 修复：
//  - 新增博士年级（博三/博二/博一）位置 4-6，放在副教授/博士后之后、研三之前
//  - 同 grade 内按姓名拼音升序（localeCompare zh-CN）
//  - fallback 99 用于未知 grade，避免被排到首/末位，兜底按姓名拼音排
const GRADE_ORDER = {
  '教授': 1, '副教授': 2, '博士后': 3,
  '博三': 4, '博二': 5, '博一': 6,
  '研三': 7, '研二': 8, '研一': 9,
  '大四': 10, '大三': 11, '大二': 12, '大一': 13,
  '已毕业': 14
}
const members = computed(() => {
  return [...memberStore.members].sort((a, b) => {
    const orderA = GRADE_ORDER[a.grade] ?? 99
    const orderB = GRADE_ORDER[b.grade] ?? 99
    if (orderA !== orderB) return orderA - orderB
    // 同 grade 内按姓名拼音升序
    return (a.name || '').localeCompare(b.name || '', 'zh-CN')
    return a.name.localeCompare(b.name, 'zh-CN')
  })
})

const isMobile = ref(window.innerWidth <= 768)
const searchName = ref('')
const searchGrade = ref('')
const showCreateDialog = ref(false)
const editingMember = ref(null)
const enrollDialogVisible = ref(false)
const enrollMember = ref(null)

const memberForm = ref({
  name: '',
  grade: '',
  research_area: '',
  role: 'member',
  email: '',
  phone: '',
  skills: [],
  bio: ''
})

// 获取成员列表（使用 store）
const fetchMembers = () => {
  const params = {}
  if (searchName.value) params.name = searchName.value
  if (searchGrade.value) params.grade = searchGrade.value
  return memberStore.fetchMembers(params)
}

// 保存成员
const saveMember = async () => {
  if (!memberForm.value.name) {
    ElMessage.warning('请输入姓名')
    return
  }

  try {
    if (editingMember.value) {
      await axios.put(`/api/v1/members/${editingMember.value.id}`, memberForm.value)
      ElMessage.success('成员信息更新成功')
    } else {
      await axios.post('/api/v1/members', memberForm.value)
      ElMessage.success('成员添加成功')
    }
    showCreateDialog.value = false
    editingMember.value = null
    resetForm()
    fetchMembers()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

// 编辑成员
const editMember = (member) => {
  editingMember.value = member
  const { avatar: _avatar, ...rest } = member
  memberForm.value = { ...rest }
  showCreateDialog.value = true
}

// 查看成员任务
const viewTasks = (member) => {
  router.push({ path: '/tasks', query: { assignee_id: member.id } })
}

// 打开声纹录入弹窗
const openEnrollDialog = (member) => {
  enrollMember.value = member
  enrollDialogVisible.value = true
}

// 声纹录入成功后刷新成员列表
const onEnrollSuccess = async () => {
  await fetchMembers()
}

// 格式化声纹录入时间
const formatEnrollTime = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffSec = (now - d) / 1000
    if (diffSec < 60) return '刚刚'
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return ''
  }
}

// 重置表单
const resetForm = () => {
  memberForm.value = {
    name: '',
    grade: '',
    research_area: '',
    role: 'member',
    email: '',
    phone: '',
    skills: [],
    bio: ''
  }
}

// 辅助函数
const getAvatarIndex = (name) => {
  // v77 P2.6-D.3: 改用 .avatar-color-N 枚举 class（runtime-style-tokens.scss 定义 8 色）
  return name.charCodeAt(0) % 8
}

const getRoleType = (role) => {
  const map = { admin: 'danger', leader: 'warning', member: 'info' }
  return map[role] || 'info'
}

const getRoleLabel = (role) => {
  const map = { admin: '管理员', leader: '组长', member: '成员' }
  return map[role] || role
}

// v77 P2.6-D: 成员 skills 缺失时用 research_area 推断 fallback（最多 3 个标签）
const displaySkills = (member) => getDisplaySkills(member)

onMounted(() => {
  memberStore.refreshMembers()
})
</script>

<style scoped>
.member-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

.filter-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.member-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-4);
}

.member-card {
  text-align: center;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
  position: relative;
}

.voiceprint-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 1;
}

.voiceprint-badge .el-icon {
  margin-right: 2px;
  vertical-align: -2px;
}

.member-card:hover {
  /* 用 margin-top 代替 transform，避免创建 containing block 干扰 el-dialog 定位 */
  margin-top: -4px;
  box-shadow: var(--shadow-primary);
  border-color: var(--color-primary);
}

.member-avatar {
  margin-bottom: var(--space-4);
}

.member-info {
  margin-bottom: var(--space-4);
}

.member-name {
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
}

.member-role {
  margin-top: var(--space-2);
}

.member-detail {
  text-align: left;
  margin-bottom: var(--space-4);
}

.detail-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  border-bottom: 1px solid var(--color-border-light);
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-item .el-icon {
  color: var(--color-primary);
  flex-shrink: 0;
}

.member-skills {
  margin-bottom: var(--space-4);
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 4px;
  max-width: 100%;
}

.member-skills .el-tag {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-actions {
  display: flex;
  justify-content: center;
  gap: var(--space-3);
}

.member-actions .el-button {
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.member-actions .el-button:hover {
  transform: scale(1.02);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.member-avatar :deep(.el-avatar) {
  border-radius: var(--radius-xl) !important;
  box-shadow: var(--shadow-md);
  transition: all var(--duration-normal) var(--ease-out);
}

.member-avatar :deep(.el-avatar):hover {
  transform: scale(1.05);
  box-shadow: var(--shadow-primary);
}
</style>

<style>
/* v69 P1b: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
[data-theme="dark"] .member-card {
  background: var(--color-bg-card);
  border-color: var(--color-border);
  box-shadow: var(--shadow-sm);
}
[data-theme="dark"] .member-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
}
[data-theme="dark"] .detail-item {
  color: var(--color-text-regular);
  border-bottom-color: var(--color-border-light);
}
[data-theme="dark"] .member-actions .el-button:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
[data-theme="dark"] .member-avatar :deep(.el-avatar) {
  box-shadow: var(--shadow-md);
}
[data-theme="dark"] .member-avatar :deep(.el-avatar):hover {
  box-shadow: var(--shadow-primary);
}

/* v77 P2.6-D: ocean / forest 主题 chips 适配（成员 skills / grade） */
/* el-tag type=info 默认浅灰底+灰字在 ocean 主题下看不清 → 改为主题浅色 */
[data-accent="ocean"] .member-skills .el-tag,
[data-accent="ocean"] .member-info .el-tag {
  background: var(--color-primary-bg);
  border-color: var(--color-primary-border);
  color: var(--color-primary);
}
[data-accent="forest"] .member-skills .el-tag,
[data-accent="forest"] .member-info .el-tag {
  background: var(--color-primary-bg);
  border-color: var(--color-primary-border);
  color: var(--color-primary);
}
/* dark + ocean/forest 组合加深 */
[data-theme="dark"][data-accent="ocean"] .member-skills .el-tag,
[data-theme="dark"][data-accent="ocean"] .member-info .el-tag,
[data-theme="dark"][data-accent="forest"] .member-skills .el-tag,
[data-theme="dark"][data-accent="forest"] .member-info .el-tag {
  background: rgba(var(--color-primary-rgb), 0.18);
  border-color: rgba(var(--color-primary-rgb), 0.30);
}
</style>
// minor cleanup
