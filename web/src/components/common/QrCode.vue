<!--
  QrCode.vue - 二维码生成 wrapper (2026-07-20 file-request 实装)

  基于 qrcode 1.5.4 (npm: qrcode), 输出 SVG 字符串嵌入 template.
  为何不直接用 <img src="data:..."> 而是 innerHTML: SVG 矢量缩放, dark mode 自动跟随颜色变量.

  Props:
    - value: 二维码内容 (string, 必填, 通常是 URL)
    - size: 尺寸 (px, 默认 200)
    - level: 容错等级 L/M/Q/H (默认 M)
    - fgColor: 前景色 (默认 'currentColor' 跟父元素, dark mode 自动适应)

  用法:
    <QrCode :value="shareUrl" :size="180" />
-->
<template>
  <div class="qrcode-wrapper" :style="{ width: size + 'px', height: size + 'px' }" v-html="svg" />
</template>

<script setup>
import { ref, watchEffect } from 'vue'
import QRCode from 'qrcode'

const props = defineProps({
  value: { type: String, required: true },
  size: { type: Number, default: 200 },
  level: { type: String, default: 'M' },  // L=7%, M=15%, Q=25%, H=30%
  fgColor: { type: String, default: 'currentColor' },
  bgColor: { type: String, default: 'transparent' },
  margin: { type: Number, default: 2 },
})

const svg = ref('')

async function regenerate() {
  if (!props.value) {
    svg.value = ''
    return
  }
  try {
    // generate() 返 SVG 字符串, type:'svg' + color.dark/fgColor 配色
    // margin 单位 modules (默认 4, 这里降到 2 节省空间)
    const out = await QRCode.toString(props.value, {
      type: 'svg',
      errorCorrectionLevel: props.level,
      margin: props.margin,
      color: {
        dark: props.fgColor,
        light: props.bgColor,
      },
      width: props.size,
    })
    svg.value = out
  } catch (e) {
    // 二维码内容超长等极端情况 → 静默空, 父组件 v-if 显式提示
    console.warn('[QrCode] generate failed:', e?.message || e)
    svg.value = ''
  }
}

// props 变化 (URL 切换) 自动重生成
watchEffect(() => {
  // 显式引用让 watchEffect 追踪
  void props.value
  void props.size
  void props.fgColor
  void props.bgColor
  regenerate()
})
</script>

<style scoped>
.qrcode-wrapper {
  display: inline-block;
  line-height: 0;
}
.qrcode-wrapper :deep(svg) {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
