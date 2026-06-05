<template>
  <div class="settings-view">
    <header class="header">
      <div class="header-left">
        <h2>个人设置</h2>
        <p>管理你的个人信息和偏好</p>
      </div>
    </header>

    <div class="settings-container">
      <div class="settings-section">
        <h3>个人信息</h3>
        <div class="settings-form">
          <div class="form-group">
            <label>头像</label>
            <div class="avatar-upload">
              <div class="avatar-preview">
                <span>{{ userInitial }}</span>
              </div>
              <button class="btn btn-secondary btn-small">更换头像</button>
            </div>
          </div>
          <div class="form-group">
            <label>用户名</label>
            <input type="text" class="input" :value="username" />
          </div>
          <div class="form-group">
            <label>邮箱</label>
            <input type="email" class="input" placeholder="请输入邮箱" />
          </div>
          <button class="btn btn-primary">保存修改</button>
        </div>
      </div>

      <div class="settings-section">
        <h3>安全设置</h3>
        <div class="settings-form">
          <div class="form-group">
            <label>当前密码</label>
            <input type="password" class="input" placeholder="请输入当前密码" />
          </div>
          <div class="form-group">
            <label>新密码</label>
            <input type="password" class="input" placeholder="请输入新密码" />
          </div>
          <div class="form-group">
            <label>确认新密码</label>
            <input type="password" class="input" placeholder="请再次输入新密码" />
          </div>
          <button class="btn btn-secondary">修改密码</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const username = computed(() => userStore.username)
const userInitial = computed(() => userStore.userInitial)
</script>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.header {
  margin-bottom: 8px;
}

.header-left h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-left p {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.settings-container {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.settings-section {
  background: white;
  border-radius: var(--radius-lg);
  padding: 32px;
  border: 1px solid var(--color-border);
}

.settings-section h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 24px;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 480px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.avatar-upload {
  display: flex;
  align-items: center;
  gap: 16px;
}

.avatar-preview {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-full);
  background: linear-gradient(135deg, var(--color-accent), #FFB347);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 28px;
  font-weight: 600;
}
</style>
