<template>
  <div class="mobile-file-request-view mg-page">
    <PageHeader title="文件请求" show-back @back="$router.back()" />
    <main class="request-main" :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }">
      <!--
        F1 修复 (批次②): router /drive/requests 的 mobile 组件此前是
        'MobileDriveTrashView' 占位 (回收站), 现接本组件。
        功能复用桌面同款 FileRequestListPanel (创建/关闭/复制链接/预览),
        外层套 mg 玻璃容器; panel 内部 el-* 组件保持现状 (移动端网盘区本就复用
        EP dialog 的先例, 如 MobileDriveView 分片上传)。
      -->
      <div class="request-panel mg-glass mg-rise">
        <FileRequestListPanel />
      </div>
    </main>
  </div>
</template>

<script setup>
// MobileFileRequestView.vue — 移动端文件请求管理薄包装 (批次② F1 新建)
import PageHeader from '@/components/mobile/PageHeader.vue'
import FileRequestListPanel from '@/components/drive/FileRequestListPanel.vue'
</script>

<style scoped>
.mobile-file-request-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.request-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}
:deep(.mobile-page-header) {
  background: var(--mg-glass-bg);
  -webkit-backdrop-filter: blur(24px);
  backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--mg-glass-border);
}
:deep(.header-title) { color: var(--mg-text-strong); }
:deep(.header-back) { color: var(--mg-text); }
.request-panel {
  border-radius: var(--mg-radius-lg);
  border: 1.5px solid var(--mg-glass-border);
  box-shadow: var(--mg-shadow-sm);
  padding: 12px;
  overflow-x: hidden;
}
</style>
