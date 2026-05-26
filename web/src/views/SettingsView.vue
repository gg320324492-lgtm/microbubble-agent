<template>
  <div class="settings-view fade-slide-up">
    <div class="settings-grid">
      <!-- 个人资料卡片 -->
      <el-card class="settings-card">
        <template #header>
          <div class="card-header">
            <el-icon><User /></el-icon>
            <span>个人资料</span>
          </div>
        </template>

        <div class="avatar-section">
          <el-avatar :size="80" :key="previewAvatarUrl" :src="previewAvatarUrl || userStore.userInfo?.avatar" icon="UserFilled" class="settings-avatar" />
          <label class="avatar-upload-btn">
            <input type="file" accept="image/*" hidden @change="handleAvatarUpload" />
            <el-icon><Camera /></el-icon>
            <span>更换头像</span>
          </label>
        </div>

        <el-form :model="form" label-width="80px" class="settings-form">
          <el-form-item label="姓名">
            <el-input v-model="form.name" placeholder="请输入姓名" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="form.email" placeholder="请输入邮箱" />
          </el-form-item>
          <el-form-item label="电话">
            <el-input v-model="form.phone" placeholder="请输入手机号" />
          </el-form-item>
          <el-form-item label="个人简介">
            <el-input v-model="form.bio" type="textarea" :rows="3" placeholder="介绍一下自己" />
          </el-form-item>

          <!-- 只读信息 -->
          <el-divider />
          <el-form-item label="角色">
            <el-tag :type="roleTagType">{{ form.roleLabel }}</el-tag>
          </el-form-item>
          <el-form-item label="年级">
            <span class="readonly-text">{{ form.grade || '未填写' }}</span>
          </el-form-item>
          <el-form-item label="研究方向">
            <span class="readonly-text">{{ form.research_area || '未填写' }}</span>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="savingProfile" @click="saveProfile">保存资料</el-button>
            <el-button @click="resetProfile">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 修改密码卡片 -->
      <el-card class="settings-card">
        <template #header>
          <div class="card-header">
            <el-icon><Lock /></el-icon>
            <span>修改密码</span>
          </div>
        </template>

        <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="80px">
          <el-form-item label="旧密码" prop="old_password">
            <el-input v-model="passwordForm.old_password" type="password" show-password placeholder="请输入旧密码" />
          </el-form-item>
          <el-form-item label="新密码" prop="new_password">
            <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="请输入新密码" />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirm_password">
            <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="savingPassword" @click="changePassword">修改密码</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const userInfo = computed(() => userStore.userInfo)

const roleMap = { admin: '管理员', leader: '组长', member: '成员' }
const roleTagMap = { admin: 'danger', leader: 'warning', member: '' }

const roleLabel = computed(() => roleMap[userInfo.value?.role] || '成员')
const roleTagType = computed(() => roleTagMap[userInfo.value?.role] || '')

const savingProfile = ref(false)
const savingPassword = ref(false)
const passwordFormRef = ref(null)
const avatarChanged = ref(false)
const avatarObjectName = ref('')
const previewAvatarUrl = ref(userInfo.value?.avatar || '')

// 当 MainLayout.onMounted 的 GET /auth/me 异步返回时，同步所有表单字段
watch(() => userStore.userInfo, (newInfo) => {
  if (!newInfo) return
  if (newInfo.avatar) {
    previewAvatarUrl.value = newInfo.avatar
    form.avatar = newInfo.avatar
  }
  form.name = newInfo.name || ''
  form.email = newInfo.email || ''
  form.phone = newInfo.phone || ''
  form.bio = newInfo.bio || ''
  form.grade = newInfo.grade || ''
  form.research_area = newInfo.research_area || ''
  form.roleLabel = roleMap[newInfo.role] || '成员'
})

const initForm = () => ({
  name: userInfo.value?.name || '',
  email: userInfo.value?.email || '',
  phone: userInfo.value?.phone || '',
  bio: userInfo.value?.bio || '',
  avatar: userInfo.value?.avatar || '',
  grade: userInfo.value?.grade || '',
  research_area: userInfo.value?.research_area || '',
  roleLabel: roleLabel.value
})

const form = reactive(initForm())

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const validateConfirmPassword = (_rule, value, callback) => {
  if (value !== passwordForm.new_password) {
    callback(new Error('两次输入的新密码不一致'))
  } else {
    callback()
  }
}

const passwordRules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

// 上传前压缩大图片（手机端网络不稳定，小文件成功率更高）
const compressImage = (file, maxWidth = 1024, quality = 0.8) => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      URL.revokeObjectURL(url)
      let { width, height } = img
      if (width > maxWidth) {
        height = Math.round((maxWidth / width) * height)
        width = maxWidth
      }
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0, width, height)
      canvas.toBlob((blob) => {
        if (!blob) return reject(new Error('图片压缩失败'))
        const name = file.name.replace(/\.[^.]+$/, '') || 'avatar'
        resolve(new File([blob], `${name}.jpg`, { type: 'image/jpeg' }))
      }, 'image/jpeg', quality)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片加载失败'))
    }
    img.src = url
  })
}

const handleAvatarUpload = async (e) => {
  const file = e.target.files[0]
  if (!file) return

  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 50MB')
    return
  }

  // 文件 >= 1MB 时先压缩再上传；HEIC 等不受支持的格式跳过压缩
  let uploadFile = file
  if (file.size >= 1024 * 1024) {
    try {
      uploadFile = await compressImage(file)
    } catch {
      // HEIC/WebP 等 Canvas 不支持的格式直接用原文件
    }
  }

  let objectName
  try {
    // 1. 上传文件到 MinIO
    const formData = new FormData()
    formData.append('file', uploadFile)
    formData.append('prefix', 'avatars')

    const res = await axios.post('/api/v1/upload', formData, {
      timeout: 60000
    })
    if (!res.data?.object_name) {
      ElMessage.error('上传返回数据异常')
      return
    }
    objectName = res.data.object_name

    // 2. 立即保存到后端（自动持久化）
    await axios.put('/api/v1/auth/profile', { avatar: objectName })
  } catch (err) {
    const detail = err.response?.data?.detail || err.message
    console.error('[头像上传失败]', { detail })
    ElMessage.error(`头像上传失败: ${detail}`)
    return
  }

  // 3. 获取完整 URL（容错：失败时用本地构建的兜底）
  let resolvedUrl
  try {
    const meRes = await axios.get('/api/v1/auth/me')
    resolvedUrl = meRes.data?.avatar
  } catch {
    // GET 失败不影响保存结果
  }
  resolvedUrl = resolvedUrl || `${window.location.origin}/minio/microbubble/${objectName}`

  // 4. 无论如何都更新 localStorage（防止刷新后回退）
  const stored = JSON.parse(localStorage.getItem('user_info') || '{}')
  stored.avatar = resolvedUrl
  localStorage.setItem('user_info', JSON.stringify(stored))

  // 5. 刷新 store
  userStore.loadFromStorage()

  // 6. 更新预览
  form.avatar = resolvedUrl
  previewAvatarUrl.value = resolvedUrl
  avatarObjectName.value = objectName
  avatarChanged.value = false

  ElMessage.success('头像已更新')
}

const saveProfile = async () => {
  savingProfile.value = true
  try {
    const payload = {
      name: form.name,
      email: form.email || undefined,
      phone: form.phone || undefined,
      bio: form.bio || undefined
    }
    // 只在用户新上传头像时发送 object_name，避免覆盖已存储的 object_name
    if (avatarChanged.value) {
      payload.avatar = avatarObjectName.value || undefined
    }

    const res = await axios.put('/api/v1/auth/profile', payload)
    const updated = res.data

    // 更新 localStorage
    const stored = JSON.parse(localStorage.getItem('user_info') || '{}')
    Object.assign(stored, {
      name: updated.name,
      email: updated.email,
      phone: updated.phone,
      bio: updated.bio,
      avatar: updated.avatar
    })
    localStorage.setItem('user_info', JSON.stringify(stored))

    // 刷新 userStore
    userStore.loadFromStorage()

    // 更新预览中的头像为后端解析后的完整 URL
    form.avatar = updated.avatar || form.avatar
    previewAvatarUrl.value = updated.avatar || previewAvatarUrl.value
    avatarChanged.value = false

    ElMessage.success('个人资料已保存')
  } catch (err) {
    const msg = err.response?.data?.detail || '保存失败'
    ElMessage.error(msg)
  } finally {
    savingProfile.value = false
  }
}

const resetProfile = () => {
  Object.assign(form, initForm())
  previewAvatarUrl.value = userInfo.value?.avatar || ''
}

const changePassword = async () => {
  if (!passwordFormRef.value) return
  try {
    await passwordFormRef.value.validate()
  } catch {
    return
  }

  savingPassword.value = true
  try {
    await axios.post('/api/v1/auth/change-password', {
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password
    })

    ElMessage.success('密码修改成功')
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
  } catch (err) {
    const msg = err.response?.data?.detail || '密码修改失败'
    ElMessage.error(msg)
  } finally {
    savingPassword.value = false
  }
}
</script>

<style scoped>
.settings-view {
  padding: 24px;
  max-width: 960px;
  margin: 0 auto;
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.settings-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.settings-card :deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-primary);
}

.avatar-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.settings-avatar {
  border: 3px solid var(--color-primary-bg);
  box-shadow: var(--shadow-primary);
}

.avatar-upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--color-primary);
  cursor: pointer;
  padding: 4px 12px;
  border: 1px dashed var(--color-primary);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast);
}

.avatar-upload-btn:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary-dark);
}

.settings-form {
  padding: 0 8px;
}

.readonly-text {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

@media (max-width: 768px) {
  .settings-view {
    padding: 12px;
  }

  .settings-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .settings-form :deep(.el-form-item__label) {
    width: 64px !important;
  }
}
</style>
