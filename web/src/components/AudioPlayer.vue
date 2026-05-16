<template>
  <div class="audio-player" v-if="src">
    <!-- 播放按钮 -->
    <el-button
      :type="isPlaying ? 'danger' : 'primary'"
      circle
      size="small"
      @click="togglePlay"
    >
      <el-icon>
        <VideoPlay v-if="!isPlaying" />
        <VideoPause v-else />
      </el-icon>
    </el-button>

    <!-- 进度条 -->
    <div class="progress-bar" @click="seek">
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: progress + '%' }"></div>
      </div>
    </div>

    <!-- 时间显示 -->
    <span class="time">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>

    <!-- 音量控制 -->
    <el-popover trigger="click" width="200">
      <template #reference>
        <el-button circle size="small">
          <el-icon>
            <Microphone />
          </el-icon>
        </el-button>
      </template>
      <div class="volume-control">
        <el-slider
          v-model="volume"
          :min="0"
          :max="100"
          @change="setVolume"
        />
      </div>
    </el-popover>

    <!-- 隐藏的audio元素 -->
    <audio
      ref="audioRef"
      :src="src"
      @loadedmetadata="onLoadedMetadata"
      @timeupdate="onTimeUpdate"
      @ended="onEnded"
      @error="onError"
    ></audio>
  </div>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'

const props = defineProps({
  src: {
    type: String,
    default: ''
  },
  autoplay: {
    type: Boolean,
    default: false
  }
})

const audioRef = ref(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const progress = ref(0)
const volume = ref(80)

// 播放/暂停切换
const togglePlay = () => {
  if (!audioRef.value) return

  if (isPlaying.value) {
    audioRef.value.pause()
  } else {
    audioRef.value.play()
  }
  isPlaying.value = !isPlaying.value
}

// 跳转到指定位置
const seek = (event) => {
  if (!audioRef.value || !duration.value) return

  const rect = event.currentTarget.getBoundingClientRect()
  const percent = (event.clientX - rect.left) / rect.width
  audioRef.value.currentTime = percent * duration.value
}

// 设置音量
const setVolume = (val) => {
  if (audioRef.value) {
    audioRef.value.volume = val / 100
  }
}

// 元数据加载完成
const onLoadedMetadata = () => {
  if (audioRef.value) {
    duration.value = audioRef.value.duration
    audioRef.value.volume = volume.value / 100

    if (props.autoplay) {
      togglePlay()
    }
  }
}

// 时间更新
const onTimeUpdate = () => {
  if (audioRef.value) {
    currentTime.value = audioRef.value.currentTime
    progress.value = (currentTime.value / duration.value) * 100 || 0
  }
}

// 播放结束
const onEnded = () => {
  isPlaying.value = false
  currentTime.value = 0
  progress.value = 0
}

// 错误处理
const onError = (e) => {
  console.error('音频播放错误:', e)
  isPlaying.value = false
}

// 格式化时间
const formatTime = (seconds) => {
  if (!seconds || isNaN(seconds)) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// 监听src变化
watch(() => props.src, (newSrc) => {
  if (newSrc) {
    isPlaying.value = false
    currentTime.value = 0
    progress.value = 0
  }
})

// 停止播放
const stop = () => {
  if (audioRef.value) {
    audioRef.value.pause()
    audioRef.value.currentTime = 0
    isPlaying.value = false
    currentTime.value = 0
    progress.value = 0
  }
}

onUnmounted(() => {
  stop()
})

defineExpose({
  stop,
  togglePlay
})
</script>

<style scoped>
.audio-player {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 20px;
}

.progress-bar {
  flex: 1;
  height: 20px;
  display: flex;
  align-items: center;
  cursor: pointer;
}

.progress-track {
  width: 100%;
  height: 4px;
  background: #dcdfe6;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #409eff;
  border-radius: 2px;
  transition: width 0.1s linear;
}

.time {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
  min-width: 80px;
  text-align: center;
}

.volume-control {
  padding: 10px 0;
}
</style>
