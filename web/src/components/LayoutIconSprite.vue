<!--
  G 稿 · 控制台档案 — 统一 16px 图标精灵 (viewBox 0 0 16 16, stroke 1.5)
  视觉源: docs/design-proposals/layout-2026-09/G-console.html (四稿共享同一 sprite, 字节一致)
  动机: Element Plus 图标按 24px 设计, 缩到 14-16px 发糊; 本 sprite 圆角矩形 + 整数锚点重画
  用法: <svg class="s"><use href="#i-xxx"/></svg>, 需在 App 壳 (MainLayout) 挂载一次
-->
<template>
  <svg width="0" height="0" style="position: absolute" aria-hidden="true"><defs>
    <symbol id="i-gauge" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11.3a5.5 5.5 0 1 1 10 0"/><path d="M8 9.1 10.7 6.5"/><circle cx="8" cy="9.1" r=".9" fill="currentColor" stroke="none"/></symbol>
    <symbol id="i-chat" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2.5" width="12" height="9" rx="2"/><path d="M5.6 11.5 4.6 14.4 8.4 11.5"/><circle cx="6" cy="7" r=".85" fill="currentColor" stroke="none"/><circle cx="10" cy="7" r=".85" fill="currentColor" stroke="none"/></symbol>
    <symbol id="i-list" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4h7.5M6 8h7.5M6 12h7.5"/><circle cx="2.9" cy="4" r=".95" fill="currentColor" stroke="none"/><circle cx="2.9" cy="8" r=".95" fill="currentColor" stroke="none"/><circle cx="2.9" cy="12" r=".95" fill="currentColor" stroke="none"/></symbol>
    <symbol id="i-camera" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="1.5" y="4" width="9.5" height="8" rx="1.5"/><path d="M11.5 7 14.6 4.9v6.2L11.5 9"/></symbol>
    <symbol id="i-files" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="1.5" width="9" height="11" rx="1.8"/><path d="M5.4 14.5H11a2 2 0 0 0 2-2V6.6"/></symbol>
    <symbol id="i-doc" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9.2 1.8H4.3a1.5 1.5 0 0 0-1.5 1.5v9.4a1.5 1.5 0 0 0 1.5 1.5h7.4a1.5 1.5 0 0 0 1.5-1.5V5.6L9.2 1.8Z"/><path d="M9.2 1.8v3.8h4"/><path d="M5.6 8.8h4.8M5.6 11.2h3.4"/></symbol>
    <symbol id="i-folder" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1.8 3.9a1.6 1.6 0 0 1 1.6-1.6h3.1c.5 0 1 .2 1.3.6l1 1.2h3.8a1.6 1.6 0 0 1 1.6 1.6v5.8a1.6 1.6 0 0 1-1.6 1.6H3.4a1.6 1.6 0 0 1-1.6-1.6V3.9Z"/></symbol>
    <symbol id="i-sliders" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4.5h7M12.5 4.5h1.5M2 11.5h1.5M7 11.5h7"/><circle cx="10.7" cy="4.5" r="1.7"/><circle cx="4.8" cy="11.5" r="1.7"/></symbol>
    <symbol id="i-cpu" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="3.5" width="9" height="9" rx="1"/><rect x="6.4" y="6.4" width="3.2" height="3.2" rx=".5"/><path d="M6 1.6v1.9M10 1.6v1.9M6 12.5v1.9M10 12.5v1.9M1.6 6h1.9M1.6 10h1.9M12.5 6h1.9M12.5 10h1.9"/></symbol>
    <symbol id="i-board" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.6 2.4v11h11"/><path d="M6 12.2V9M8.8 12.2V5.6M11.6 12.2V7.6"/></symbol>
    <symbol id="i-bell" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1.9a4.2 4.2 0 0 0-4.2 4.2c0 3.2-1 4.4-1.5 5.1-.2.4.1.9.6.9h10.2c.5 0 .8-.5.6-.9-.5-.7-1.5-1.9-1.5-5.1A4.2 4.2 0 0 0 8 1.9Z"/><path d="M6.4 14.2a1.7 1.7 0 0 0 3.2 0"/></symbol>
    <symbol id="i-moon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 2a4.4 4.4 0 0 0 6 6A6 6 0 1 1 8 2Z"/></symbol>
    <symbol id="i-fold" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="1.8" y="2.8" width="12.4" height="10.4" rx="1.6"/><path d="M6 2.8v10.4M11.4 6.4 9.6 8l1.8 1.6"/></symbol>
    <symbol id="i-search" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="6.9" cy="6.9" r="4.4"/><path d="m10.2 10.2 3.9 3.9"/></symbol>
    <symbol id="i-user" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="5.4" r="2.9"/><path d="M2.8 14.2c.6-2.9 2.7-4.4 5.2-4.4s4.6 1.5 5.2 4.4"/></symbol>
    <symbol id="i-bunny" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="6.1" cy="4.6" rx="1.3" ry="3"/><ellipse cx="9.9" cy="4.6" rx="1.3" ry="3"/><circle cx="8" cy="10.6" r="3.4"/></symbol>
    <symbol id="i-aim" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.2"/><circle cx="8" cy="8" r="1.5" fill="currentColor" stroke="none"/><path d="M8 .9v2M8 13.1v2M.9 8h2M13.1 8h2"/></symbol>
    <symbol id="i-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 3.6 4.4 4.4L6 12.4"/></symbol>
    <symbol id="i-clock" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.6"/><path d="M8 4.8V8l2.4 1.6"/></symbol>
    <symbol id="i-tag" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 2h5.2l6.6 6.6-5.2 5.2L2 7.4Z"/><circle cx="4.7" cy="4.7" r=".9" fill="currentColor" stroke="none"/></symbol>
    <symbol id="i-arrow" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 8h11M10 4l4 4-4 4"/></symbol>
  </defs></svg>
</template>
