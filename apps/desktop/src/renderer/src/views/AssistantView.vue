<script setup lang="ts">
// AI 助手 — M0 占位（M1 交付对话+模型网关），展示工作台首页姿态
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const roadmap = [
  { m: 'M1', label: 'AI 对话 · 流式输出 · 自配模型 key' },
  { m: 'M2', label: '知识库 · 会议档案 · 网页端数据导入' },
  { m: 'M3', label: '实验 ELN · 稿件管理' },
  { m: 'M4', label: '托盘 · 原生通知 · 全局快捷键' }
]
</script>

<template>
  <div class="assistant">
    <section class="hero card">
      <div class="hero-head">
        <span class="hero-badge">M0</span>
        <h1>{{ auth.user?.displayName || auth.user?.username }}，工作台已就绪</h1>
      </div>
      <p>
        这是本地科研工作台的第一版骨架。你的账号与所有数据都存储在本机 SQLite
        数据库中，断开网络依然可以登录和使用。AI 对话将在 M1 里程碑接入。
      </p>
      <div class="hero-checks">
        <span>✓ 本地账号体系</span>
        <span>✓ SQLite 数据库</span>
        <span>✓ 断网可用</span>
        <span>✓ 数据不出本机</span>
      </div>
    </section>

    <section class="roadmap card">
      <h2>接下来做什么</h2>
      <ul>
        <li v-for="item in roadmap" :key="item.m">
          <span class="roadmap-m">{{ item.m }}</span>
          <span>{{ item.label }}</span>
        </li>
      </ul>
      <p class="roadmap-note">每个里程碑都按「断网可用」验收；本地做不好的功能会直接移出桌面端，保留在网页端。</p>
    </section>
  </div>
</template>

<style scoped>
.assistant {
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.hero {
  padding: var(--space-8);
  background: var(--gradient-paper-warm);
}
.hero-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.hero-badge {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}
.hero h1 {
  font-size: 22px;
  font-weight: var(--font-weight-semibold);
}
.hero p {
  margin-top: var(--space-3);
  color: var(--color-text-regular);
  line-height: 1.8;
}
.hero-checks {
  margin-top: var(--space-4);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--color-primary-dark);
}
.roadmap {
  padding: var(--space-6);
}
.roadmap h2 {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}
.roadmap ul {
  margin-top: var(--space-4);
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.roadmap li {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text-regular);
}
.roadmap-m {
  flex-shrink: 0;
  width: 40px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-full);
  background: var(--color-primary-bg);
  color: var(--color-primary-dark);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}
.roadmap-note {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px dashed var(--color-border);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
</style>
