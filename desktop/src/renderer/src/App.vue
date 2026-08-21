<script setup lang="ts">
import PingTest from './components/PingTest.vue'
</script>

<template>
  <main class="app-root">
    <header class="app-header">
      <h1>MicroBubble Desktop</h1>
      <p class="app-subtitle">Phase 0 skeleton · Electron + Vue 3 + TypeScript</p>
    </header>
    <section class="app-content">
      <PingTest />
    </section>
  </main>
</template>

<style scoped>
.app-root {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #0f172a;
  color: #e2e8f0;
  padding: 2rem;
  box-sizing: border-box;
}
.app-header {
  margin-bottom: 2rem;
}
.app-header h1 {
  margin: 0;
  font-size: 1.6rem;
  font-weight: 600;
  color: #f97316;
}
.app-subtitle {
  margin: 0.4rem 0 0;
  font-size: 0.9rem;
  color: #94a3b8;
}
.app-content {
  flex: 1;
}
</style>
