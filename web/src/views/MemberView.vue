<template>
  <div class="member-view">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="8">
          <el-input
            v-model="searchName"
            placeholder="搜索成员姓名"
            clearable
            @keyup.enter="fetchMembers"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="8">
          <el-select v-model="searchGrade" placeholder="年级" clearable>
            <el-option label="教授" value="教授" />
            <el-option label="博士后" value="博士后" />
            <el-option label="博一" value="博一" />
            <el-option label="博二" value="博二" />
            <el-option label="研一" value="研一" />
            <el-option label="研二" value="研二" />
            <el-option label="研三" value="研三" />
          </el-select>
        </el-col>
        <el-col :span="8">
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
        <div class="member-avatar">
          <el-avatar :size="64" :style="{ background: getAvatarColor(member.name) }">
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
            v-for="skill in (member.skills || []).slice(0, 3)"
            :key="skill"
            size="small"
            type="info"
            style="margin: 2px"
          >
            {{ skill }}
          </el-tag>
          <el-tag
            v-if="(member.skills || []).length > 3"
            size="small"
            type="info"
            style="margin: 2px"
          >
            +{{ member.skills.length - 3 }}
          </el-tag>
        </div>

        <div class="member-actions">
          <el-button text type="primary" @click="editMember(member)">编辑</el-button>
          <el-button text @click="viewTasks(member)">查看任务</el-button>
        </div>
      </el-card>
    </div>

    <!-- 创建/编辑成员对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingMember ? '编辑成员' : '添加成员'"
      width="500px"
    >
      <el-form :model="memberForm" label-width="80px">
        <el-form-item label="姓名" required>
          <el-input v-model="memberForm.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="memberForm.grade" placeholder="选择年级">
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
          <el-input v-model="memberForm.research_area" placeholder="如：气泡生成、水处理" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="memberForm.role">
            <el-option label="管理员" value="admin" />
            <el-option label="组长" value="leader" />
            <el-option label="成员" value="member" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="memberForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机">
          <el-input v-model="memberForm.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="技能">
          <el-select
            v-model="memberForm.skills"
            multiple
            filterable
            allow-create
            placeholder="输入技能标签"
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const members = ref([])
const searchName = ref('')
const searchGrade = ref('')
const showCreateDialog = ref(false)
const editingMember = ref(null)

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

// 获取成员列表
const fetchMembers = async () => {
  try {
    const params = {}
    if (searchName.value) params.name = searchName.value
    if (searchGrade.value) params.grade = searchGrade.value
    const res = await axios.get('/api/v1/members', { params })
    members.value = res.data.items || []
  } catch (e) {
    console.error('获取成员失败:', e)
  }
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
  memberForm.value = { ...member }
  showCreateDialog.value = true
}

// 查看成员任务
const viewTasks = (member) => {
  router.push({ path: '/tasks', query: { assignee_id: member.id } })
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
const getAvatarColor = (name) => {
  const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399']
  const index = name.charCodeAt(0) % colors.length
  return colors[index]
}

const getRoleType = (role) => {
  const map = { admin: 'danger', leader: 'warning', member: 'info' }
  return map[role] || 'info'
}

const getRoleLabel = (role) => {
  const map = { admin: '管理员', leader: '组长', member: '成员' }
  return map[role] || role
}

onMounted(() => {
  fetchMembers()
})
</script>

<style scoped>
.member-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.member-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.member-card {
  text-align: center;
  transition: all 0.3s;
}

.member-card:hover {
  transform: translateY(-4px);
}

.member-avatar {
  margin-bottom: 16px;
}

.member-info {
  margin-bottom: 16px;
}

.member-name {
  font-size: 18px;
  color: #303133;
  margin-bottom: 8px;
}

.member-role {
  margin-top: 8px;
}

.member-detail {
  text-align: left;
  margin-bottom: 16px;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-size: 13px;
  color: #606266;
  border-bottom: 1px solid #f0f0f0;
}

.detail-item:last-child {
  border-bottom: none;
}

.member-skills {
  margin-bottom: 16px;
}

.member-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}
</style>
