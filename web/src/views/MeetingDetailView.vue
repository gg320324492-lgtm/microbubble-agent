<template>
  <div class="meeting-detail" v-if="meeting">
    <!-- ====== Hero 区域 ====== -->
    <div class="detail-hero">
      <!-- 返回 -->
      <div class="hero-back">
        <el-button text @click="$router.push('/meetings')">
          <el-icon><ArrowLeft /></el-icon> 返回列表
        </el-button>
      </div>

      <!-- 主信息 -->
      <div class="hero-main">
        <!-- 标题（展示/编辑态切换） -->
        <div v-if="!editing" class="hero-title-row">
          <h1 class="hero-title">{{ meeting.title }}</h1>
          <span class="status-badge" :class="'status-' + meeting.status">
            <span class="status-dot" />
            {{ statusLabel(meeting.status) }}
          </span>
        </div>
        <div v-else class="hero-title-row editing">
          <el-input v-model="form.title" class="edit-title-input" />
          <el-tag :type="statusType(meeting.status)" size="default">{{ statusLabel(meeting.status) }}</el-tag>
        </div>

        <!-- 元信息行 -->
        <div class="hero-meta">
          <span class="meta-item">
            <el-icon><Clock /></el-icon>
            <template v-if="!editing">{{ formatDate(meeting.start_time) }}</template>
            <el-date-picker
              v-else
              v-model="form.start_time"
              type="datetime"
              format="YYYY-MM-DD HH:mm"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="选择日期时间"
              size="small"
              style="width: 200px"
              :clearable="false"
            />
          </span>
          <span class="meta-item">
            <el-icon><Location /></el-icon>
            <template v-if="!editing">{{ meeting.location || '未设置' }}</template>
            <el-input v-else v-model="form.location" size="small" style="width:160px" placeholder="地点" />
          </span>
          <span v-if="effectiveDuration" class="meta-item">
            <el-icon><Microphone /></el-icon>
            {{ formatDuration(effectiveDuration) }}
          </span>
        </div>

        <!-- 参与者头像 -->
        <div class="hero-participants">
          <ParticipantAvatars
            :participants="effectiveParticipants"
            :max-display="8"
            :size="36"
          />
        </div>

        <!-- 2026-11-04 选型⑤「融于卡片」: 播放器住进英雄卡 (时间轴 seek 联动不变) -->
        <div v-if="meeting.audio_url" class="hero-player">
          <button class="hp-play" @click="togglePlay" :title="isPlaying ? '暂停' : '播放'">
            {{ isPlaying ? '⏸' : '▶' }}
          </button>
          <span class="hp-tm">{{ formatTs(pbCurrent) }} <span class="hp-sep">/</span> {{ pbDurText }}</span>
          <div class="hp-track" @click="seekToEvent">
            <i :style="{ width: pbPct + '%' }" />
          </div>
          <button class="hp-spd" @click="cycleSpeed">{{ pbSpeed }}x</button>
          <span class="hp-note">时间戳点击 seek</span>
          <audio
            ref="audioEl"
            preload="metadata"
            :src="getAudioSrc(meeting.audio_url)"
            @timeupdate="onAudioTime"
            @loadedmetadata="onAudioMeta"
            @ended="isPlaying = false"
            @pause="isPlaying = false"
            @play="isPlaying = true"
          />
        </div>
        <div v-else class="hp-noaudio">无录音 · 本会议来自粘贴转录分析，时间轴浏览模式</div>
      </div>

      <!-- 操作按钮 -->
      <div class="hero-actions">
        <template v-if="!editing">
          <el-button @click="enterEdit">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
          <el-popconfirm title="确定删除此会议？" @confirm="handleDelete">
            <template #reference>
              <el-button type="danger" plain>删除</el-button>
            </template>
          </el-popconfirm>
        </template>
        <template v-else>
          <el-button type="primary" @click="saveBasic" :loading="saving">保存</el-button>
          <el-button @click="cancelEdit">取消</el-button>
        </template>
      </div>
      <!-- 2026-11-04 选型⑤「融于卡片」: 进度即卡片下边缘的一条 2px 色线 -->
      <div v-if="meeting && meeting.audio_url" class="hero-progress" aria-hidden="true">
        <i :style="{ width: pbPct + '%' }" />
      </div>
    </div>

    <!-- ====== 主体区域 ====== -->
    <div class="detail-body">
      <!-- 左侧 Tab 内容 -->
      <div class="detail-main">
        <!-- 2026-10-25: 失败态卡片。
             改前只有一枚 status-badge(处理失败), 用户看不到原因、更不知道能做什么 ——
             而后端早有补救能力(POST /api/v1/meetings/{id}/reprocess), 前端一处都没调用。
             文案与动作判定统一走 @/utils/meetingFailure, 与移动端共用一份(避免两处漂移)。 -->
        <div v-if="showFailure" class="failure-banner">
          <div class="failure-icon" aria-hidden="true">⚠️</div>
          <div class="failure-body">
            <div class="failure-title">{{ failureInfo.title }}</div>
            <div class="failure-detail">{{ failureInfo.detail }}</div>
            <div v-if="failureInfo.hint" class="failure-hint">{{ failureInfo.hint }}</div>
            <details v-if="failureInfo.technical" class="failure-technical">
              <summary>技术详情</summary>
              <code>{{ failureInfo.technical }}</code>
            </details>
          </div>
          <div class="failure-actions">
            <el-button
              v-if="failureInfo.recoverable"
              type="primary"
              :loading="reprocessing"
              @click="handleReprocess"
            >
              {{ failureInfo.actionLabel }}
            </el-button>
            <el-button v-else @click="goRecordRoom">去听会页面上传</el-button>
          </div>
        </div>
        <!-- 铁律 31: tab 统一用 <TabStrip> (lazy → v-show 保留内联模板编辑态) -->
        <div class="tab-strip-wrapper">
          <TabStrip v-model="activeTab" :items="tabItems" aria-label="会议详情视图切换" />
        </div>

        <!-- Tab 1: 会议纪要 -->
        <div v-show="activeTab === 'minutes'" role="tabpanel"
          :aria-labelledby="`tab-strip-minutes`" class="tab-content">
          <div class="tab-content-inner">
              <!-- 编辑态 -->
              <template v-if="editingMinutes">
                <div class="section">
                  <h4>摘要</h4>
                  <el-input v-model="minutesForm.summary" type="textarea" :rows="4" placeholder="会议摘要..." />
                </div>
                <div class="section">
                  <h4>讨论要点</h4>
                  <div class="item-list">
                    <div v-for="(p, i) in minutesForm.key_points" :key="'kp'+i" class="item-row">
                      <span class="item-dot" />
                      <el-input v-model="minutesForm.key_points[i]" placeholder="输入要点..." />
                      <el-button :icon="Delete" circle size="small" class="item-del" @click="minutesForm.key_points.splice(i,1)" />
                    </div>
                    <el-button dashed size="small" class="item-add" @click="minutesForm.key_points.push('')">
                      <el-icon><Plus /></el-icon> 添加要点
                    </el-button>
                  </div>
                </div>
                <div class="section">
                  <h4>决议事项</h4>
                  <div class="item-list">
                    <div v-for="(d, i) in minutesForm.decisions" :key="'dc'+i" class="item-row decision">
                      <span class="item-dot decision-dot" />
                      <el-input v-model="minutesForm.decisions[i]" placeholder="输入决议..." />
                      <el-button :icon="Delete" circle size="small" class="item-del" @click="minutesForm.decisions.splice(i,1)" />
                    </div>
                    <el-button dashed size="small" class="item-add decision-add" @click="minutesForm.decisions.push('')">
                      <el-icon><Plus /></el-icon> 添加决议
                    </el-button>
                  </div>
                </div>
                <div class="section-actions">
                  <el-button type="primary" @click="saveMinutes">保存纪要</el-button>
                  <el-button @click="editingMinutes = false">取消</el-button>
                </div>
              </template>

              <!-- 展示态 -->
              <template v-else>
                <div class="topic-board">
                  <section v-if="meeting.summary" class="topic-brief">
                    <div class="topic-brief-main">
                      <div class="topic-eyebrow">THE MEETING IN ONE PARAGRAPH</div>
                      <p>{{ summaryPreview }}</p>
                      <button
                        v-if="summaryCanExpand"
                        class="topic-text-btn"
                        type="button"
                        @click="showFullSummary = !showFullSummary"
                      >
                        {{ showFullSummary ? '收起摘要' : '展开完整摘要' }}
                      </button>
                    </div>
                    <div class="topic-facts">
                      <div><b>{{ topicCards.length }}</b><span>讨论要点</span></div>
                      <div><b>{{ totalDecisionCount }}</b><span>决议事项</span></div>
                      <div><b>{{ effectiveParticipants.length }}</b><span>发言人</span></div>
                      <div><b>{{ formatDuration(effectiveDuration) }}</b><span>时长</span></div>
                    </div>
                  </section>

                  <section v-if="topicCards.length" class="topic-section">
                    <div class="topic-section-head">
                      <div><span class="topic-eyebrow">TOPICS</span><h4>议题板</h4></div>
                      <span>按内容归类，不再按发言人重复堆叠</span>
                    </div>
                    <div class="topic-grid">
                      <article
                        v-for="card in visibleTopicCards"
                        :key="card.index"
                        class="topic-card"
                        :class="{ 'topic-card-anonymous': card.anonymous }"
                      >
                        <div class="topic-card-top">
                          <span
                            class="topic-avatar"
                            :class="{ 'has-img': !!getSpeakerAvatar(card.speaker) }"
                            :style="getSpeakerAvatar(card.speaker) ? { backgroundImage: `url(${getSpeakerAvatar(card.speaker)})` } : {}"
                            :title="card.speaker"
                          >{{ card.speaker[0] }}</span>
                          <span class="topic-who">{{ card.speaker }}</span>
                          <span class="topic-tag">要点 {{ ('0' + (card.index + 1)).slice(-2) }}</span>
                        </div>
                        <h5>{{ card.title }}</h5>
                        <p :title="card.text">{{ card.text }}</p>
                      </article>
                    </div>
                    <button
                      v-if="topicCards.length > 6"
                      class="topic-text-btn"
                      type="button"
                      @click="showAllTopics = !showAllTopics"
                    >
                      {{ showAllTopics ? '收起要点' : `展开全部 ${topicCards.length} 条要点` }}
                    </button>
                  </section>

                  <section v-if="groupedDecisions.length" class="action-board">
                    <div class="topic-section-head">
                      <div><span class="topic-eyebrow">ACTIONS</span><h4>行动板</h4></div>
                      <span>共 {{ totalDecisionCount }} 项 · 按负责人归档</span>
                    </div>
                    <div class="action-columns">
                      <div v-for="col in actionColumns" :key="col.speaker" class="action-column">
                        <div class="action-column-head"><span>{{ col.speaker }}</span><em>{{ col.count }}</em></div>
                        <div v-for="(item, i) in col.items" :key="i" class="action-item">
                          <b>{{ ('0' + (i + 1)).slice(-2) }}</b><span>{{ item }}</span>
                        </div>
                        <div v-if="col.more" class="action-more">还有 {{ col.more }} 项</div>
                      </div>
                    </div>
                    <button class="topic-text-btn" type="button" @click="showAllDecisions = !showAllDecisions">
                      {{ showAllDecisions ? '收起全部决议' : `查看全部 ${totalDecisionCount} 项决议` }}
                    </button>
                    <div v-if="showAllDecisions" class="all-decisions">
                      <div v-for="(group, gi) in groupedDecisions" :key="gi" class="all-decision-group">
                        <div class="all-decision-who">{{ group.speaker || '未识别发言人' }}<span>{{ group.items.length }}</span></div>
                        <ul><li v-for="(item, ii) in group.items" :key="ii">{{ item }}</li></ul>
                      </div>
                    </div>
                  </section>

                  <details v-if="meeting.agenda?.length" class="topic-agenda">
                    <summary>会议议程（{{ meeting.agenda.length }} 项）</summary>
                    <el-timeline>
                      <el-timeline-item v-for="(item, idx) in meeting.agenda" :key="idx" :timestamp="''">
                        <template #dot><div class="agenda-dot">{{ idx + 1 }}</div></template>
                        <div class="agenda-text">{{ item }}</div>
                      </el-timeline-item>
                    </el-timeline>
                  </details>

                  <div class="topic-board-foot">
                    <el-button v-if="!editingMinutes" size="small" class="edit-minutes-btn" @click="enterEditMinutes">
                      <el-icon><Edit /></el-icon> 编辑纪要
                    </el-button>
                  </div>
                  <el-empty
                    v-if="!meeting.summary && !meeting.key_points?.length && !meeting.decisions?.length && !meeting.agenda?.length"
                    description="暂无会议纪要"
                  />
                </div>
              </template>
            </div>
          </div>

          <!-- Tab 2: 转录记录 -->
          <div v-show="activeTab === 'transcript'" role="tabpanel"
            :aria-labelledby="`tab-strip-transcript`" class="tab-content">
            <div class="tab-content-inner">
              <template v-if="transcriptEntries.length">
                <div
                  v-for="(entry, i) in displayedTranscriptEntries"
                  :key="i"
                  class="transcript-entry"
                  :class="{ 'entry-removed': entry.removed, 'entry-current': hasAudio && i === currentTranscriptIdx }"
                >
                  <div class="transcript-left">
                    <el-avatar :size="28" :src="getSpeakerAvatar(entry.speaker)" class="transcript-avatar" :alt="`${entry.speaker || '未知'}的头像`">
                      {{ (entry.speaker || '?')[0] }}
                    </el-avatar>
                    <div class="transcript-line" />
                  </div>
                  <div class="transcript-body">
                    <div class="transcript-header">
                      <el-popover
                        :width="200"
                        placement="bottom-start"
                        trigger="click"
                        :show-arrow="false"
                        :disabled="isSpeakerSaving(i)"
                      >
                        <template #reference>
                          <button
                            class="speaker-name-btn"
                            :class="{ saving: isSpeakerSaving(i) }"
                            :title="`点击修改发言人（当前：${entry.speaker || '未知'}）`"
                          >
                            {{ entry.speaker || '未知' }}
                          </button>
                        </template>
                        <el-select
                          :model-value="entry.speaker || '未知'"
                          size="small"
                          filterable
                          :loading="isSpeakerSaving(i)"
                          :disabled="isSpeakerSaving(i)"
                          @change="(val) => saveTranscriptSpeaker(i, val)"
                        >
                          <el-option
                            v-for="option in speakerOptions"
                            :key="option"
                            :label="option"
                            :value="option"
                          />
                        </el-select>
                      </el-popover>
                      <el-tag v-if="entry.removed" size="small" type="info" effect="plain">已过滤</el-tag>
                      <el-tag v-else-if="entry.polish_failed" size="small" type="warning" effect="plain">降级</el-tag>
                      <span
                        v-if="entry.ts"
                        class="transcript-ts ts-seek"
                        :title="`跳转到 ${formatTs(entry.ts)}`"
                        @click.stop="seekToTs(entry.ts)"
                      >▶ {{ formatTs(entry.ts) }}</span>
                    </div>
                    <div v-if="!entry.removed" class="transcript-text">
                      {{ getPolishedText(entry, i) }}
                    </div>
                    <div v-else class="transcript-text removed">
                      <el-icon><Delete /></el-icon>
                      <span>{{ entry.text || '(空)' }}</span>
                      <span v-if="entry.reason" class="remove-reason">({{ entry.reason }})</span>
                    </div>
                  </div>
                </div>
                <!-- 2026-07-08 修复: 分页按钮（避免 3331 段一次性渲染） -->
                <div v-if="hasMoreTranscript" class="transcript-load-more">
                  <!-- 2026-11-09: 去掉 el-button。全站 variables.css 末尾的
                       :root .el-button--primary:not(.is-text):not(.is-link) 会把
                       **plain 按钮也染成实底**（选择器没排 .is-plain），
                       W89 a11y 又把文字设成白色 ⇒ 截图里那块「深色实心 + 深色文字」
                       的不可读黑块。这里用原生 button + 本页 scoped 样式，
                       不依赖 Element Plus 主题变量，也不会被全局覆盖误伤。 -->
                  <button type="button" class="load-more-btn" @click="loadMoreTranscript">
                    加载更多 ({{ displayedTranscriptEntries.length }} / {{ transcriptEntries.length }})
                  </button>
                </div>
              </template>
              <!-- 2026-10-25: 失败时不再只显示一句"暂无转录记录" ——
                   空态本身要说明原因, 与移动端保持一致 (两端各写一套必然漂移)。 -->
              <div v-else class="transcript-empty">
                <el-empty :description="showFailure ? failureInfo.title : '暂无转录记录'" />
                <div v-if="showFailure" class="transcript-empty-hint">{{ failureInfo.detail }}</div>
              </div>
            </div>
          </div>

          <!-- Tab 3: 发言统计 -->
          <div v-show="activeTab === 'stats'" role="tabpanel"
            :aria-labelledby="`tab-strip-stats`" class="tab-content">
            <div class="tab-content-inner">
              <SpeakerStatsCard :stats="meeting.speaker_stats || []" />
            </div>
          </div>
      </div>

      <!-- 右侧边栏：只保留相关会议；纪要 Tab 使用整幅议题板，不再重复摘要/决议 -->
      <div v-if="relatedMeetings.length && activeTab !== 'minutes'" class="detail-side">
        <el-card v-if="relatedMeetings.length > 0" class="side-card">
          <template #header><span>相关会议</span></template>
          <div v-for="m in relatedMeetings" :key="m.id" class="related-item">
            <router-link :to="`/meetings/${m.id}`" class="related-link">{{ m.title }}</router-link>
            <span class="related-similarity">{{ Math.round(m.similarity * 100) }}%</span>
          </div>
        </el-card>
      </div>
    </div>
  </div>

  <div v-else class="loading-state">
    <el-icon class="is-loading" size="24"><Loading /></el-icon> 加载中...
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Edit, Delete, Document, Plus, Loading, Clock, Location, Microphone, ChatLineRound, PieChart } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { parseDbDate } from '@/utils/format'
import { useMemberStore } from '@/stores/member'
import TabStrip from '@/components/common/TabStrip.vue'
import ParticipantAvatars from '@/components/ParticipantAvatars.vue'
import SpeakerStatsCard from '@/components/SpeakerStatsCard.vue'
// 2026-10-25: 失败态文案 + 补救动作判定（桌面端与移动端共用同一份）
import { describeMeetingFailure, shouldShowFailure } from '@/utils/meetingFailure'

const route = useRoute()
const router = useRouter()
const memberStore = useMemberStore()

const meeting = ref(null)
const editing = ref(false)
const editingMinutes = ref(false)
const saving = ref(false)
const savingTranscriptSpeaker = ref(null)
// 铁律 29: URL ?tab= 同步双向（VALID_TABS 白名单 + watch + replace）
const VALID_TABS = ['minutes', 'transcript', 'stats']
// 2026-09-13 方案B 时间轴剧场: 默认进入转录时间轴 (页面主角), 纪要/统计仍可切换
const activeTab = ref(
  route.query.tab && VALID_TABS.includes(String(route.query.tab))
    ? String(route.query.tab)
    : 'transcript'
)
// 2026-07-08 修复: 大会议 (3331+ 段) v-for 渲染 ~30k Element Plus 组件
// 触发 "Maximum call stack size exceeded"。transcript 改分页渲染，每页 50 段，
// "加载更多" 按钮手动追加。避免一次 render 30k EP 组件实例。
const TRANSCRIPT_PAGE_SIZE = 50
const transcriptPageCount = ref(1)

// 铁律 30: EP 图标 named import + 通过 props 传入
const tabItems = [
  { key: 'minutes',    label: '会议纪要', icon: Document },
  { key: 'transcript', label: '转录记录', icon: ChatLineRound },
  { key: 'stats',      label: '发言统计', icon: PieChart },
]

// 铁律 29: tab → URL 同步（router.replace 不污染 history, 合并其他 query）
watch(activeTab, (tab) => {
  router.replace({ query: { ...route.query, tab } })
})

// 2026-07-08 修复: savingTranscriptSpeaker 变化时同步到非响应式 _currentSavingIdx
// 让 isSpeakerSaving() 函数每次都返回最新值, 但函数本身**不**建立 reactive 依赖
// (Vue 模板里调用函数, 不会 track 内部 .value 访问, 只在 watch 触发时更新)
watch(savingTranscriptSpeaker, (val) => { _currentSavingIdx = val ?? -1 })

// 铁律 29: URL → tab 反向同步（浏览器前进/后退）
watch(() => route.query.tab, (t) => {
  if (t && VALID_TABS.includes(String(t)) && String(t) !== activeTab.value) {
    activeTab.value = String(t)
  }
})

const relatedMeetings = ref([])

// ===== 2026-09-13 方案B: 墨色常驻播放条 (替代侧栏 AudioPlayer 卡) =====
// 原生 <audio> 受控: 播放/暂停/seek/倍速; 时间轴时间戳点击 → seekToTs 联动
const audioEl = ref(null)
const isPlaying = ref(false)
const pbCurrent = ref(0)
const pbDuration = ref(0)
const pbSpeed = ref(1)
const hasAudio = computed(() => !!meeting.value?.audio_url)
// 展示用时长: media_duration_seconds 是 ffprobe 真实媒体时长, audio_duration 是录音会话墙钟时长。
// 二者在 App 内正常录音时相等, 但补传 / 续传时会严重不等(实测 2h24m 的会议 audio_duration=39
// 而真实 8669 秒), 故一律优先取媒体时长, 回退墙钟(历史会议 media_duration_seconds 为 NULL)。
const effectiveDuration = computed(() => meeting.value?.media_duration_seconds || meeting.value?.audio_duration || 0)

// ====== 2026-10-25: 失败态 (status=error) ======
// 文案与补救动作判定见 @/utils/meetingFailure —— 与后端 reprocess 守卫同源,
// 避免「前端显示可重试、后端回 400」的错位 (类 20.220)。
const showFailure = computed(() => shouldShowFailure(meeting.value))
const failureInfo = computed(() => describeMeetingFailure(meeting.value))
const reprocessing = ref(false)

const handleReprocess = async () => {
  if (!meeting.value) return
  reprocessing.value = true
  try {
    await axios.post(`/api/v1/meetings/${meeting.value.id}/reprocess`)
    ElMessage.success('已重新提交处理，稍后刷新查看结果')
    await fetchMeeting()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '重新处理失败，请稍后重试')
  } finally {
    reprocessing.value = false
  }
}

const goRecordRoom = () => router.push('/meetings/room')
const pbPct = computed(() => (pbDuration.value ? Math.min(100, (pbCurrent.value / pbDuration.value) * 100) : 0))

function togglePlay() {
  const el = audioEl.value
  if (!el) return
  if (el.paused) { el.play(); isPlaying.value = true } else { el.pause(); isPlaying.value = false }
}
function onAudioTime() {
  if (audioEl.value) pbCurrent.value = audioEl.value.currentTime
}
function onAudioMeta() {
  // 2026-09-13 修复: 流式/缺失元数据时 duration 可能为 Infinity, 回退后端上报的展示时长
  const d = audioEl.value?.duration
  pbDuration.value = (d && isFinite(d)) ? d : effectiveDuration.value
}
const pbDurText = computed(() => {
  if (pbDuration.value > 0) return formatTs(pbDuration.value)
  const ad = effectiveDuration.value
  return ad ? formatTs(ad) : '--:--'
})
function seekTo(sec) {
  const el = audioEl.value
  if (!el) return
  el.currentTime = Math.min(Math.max(sec, 0), el.duration || sec)
  pbCurrent.value = el.currentTime
}
function seekToEvent(e) {
  const el = audioEl.value
  if (!el || !el.duration) return
  const rect = e.currentTarget.getBoundingClientRect()
  seekTo(((e.clientX - rect.left) / rect.width) * el.duration)
}
// 时间轴时间戳点击: seek + 自动播放
function seekToTs(sec) {
  seekTo(sec)
  const el = audioEl.value
  if (el && el.paused) { el.play() }
  if (!activeTab.value || activeTab.value !== 'transcript') activeTab.value = 'transcript'
}
function cycleSpeed() {
  const el = audioEl.value
  if (!el) return
  const speeds = [1, 1.5, 2]
  pbSpeed.value = speeds[(speeds.indexOf(pbSpeed.value) + 1) % speeds.length]
  el.playbackRate = pbSpeed.value
}
// 当前播放段: 显示的转录条目中最后一条 ts <= 播放进度的段 (自动高亮)
const currentTranscriptIdx = computed(() => {
  if (!hasAudio.value || !isPlaying.value && pbCurrent.value === 0) return -1
  let idx = -1
  const list = displayedTranscriptEntries.value || []
  for (let i = 0; i < list.length; i++) {
    const ts = list[i]?.ts
    if (ts == null) continue
    if (ts <= pbCurrent.value) idx = i
    else break
  }
  return idx
})

const showFullSummary = ref(false)
const showAllTopics = ref(false)
const showAllDecisions = ref(false)

// 转录记录：优先用 polished，回退到原始 transcript
// 合并策略：只合并短段（合并后 < 60字）；长段保持独立以保证阅读体验
const MERGE_THRESHOLD_CHARS = 60
const transcriptEntries = computed(() => {
  if (!meeting.value) return []
  const raw = meeting.value.transcript_polished?.length
    ? meeting.value.transcript_polished
    : (meeting.value.transcript || [])
  if (!raw.length) return []

  const merged = []
  let current = { ...raw[0], text: raw[0].text || '', _origIndex: 0 }
  for (let i = 1; i < raw.length; i++) {
    const entry = raw[i]
    if (
      entry.speaker === current.speaker &&
      !entry.removed &&
      ((current.text?.length || 0) + (entry.text?.length || 0)) < MERGE_THRESHOLD_CHARS
    ) {
      current.text = (current.text || '') + ' ' + (entry.text || '')
      if (entry.ts) current.end_ts = entry.ts
    } else {
      merged.push(current)
      current = { ...entry, text: entry.text || '', _origIndex: i }
    }
  }
  merged.push(current)

  return merged
})

// 存储润色后的文本
// v31.3.2 修复: 改用 polish-text-batch 单次调用, 避免 83 段会议触发 write tier 30/min 限流
// (单文本 polish-text 端点虽然 Redis 缓存命中 0 LLM, 但 rate-limit middleware 每次请求都计数,
//  并发 3 × 83 段 = ~83 POST, 30/min 限流后段全部 429, console 30+ 个重复错误像 Vue loop)
const polishedTexts = ref({})

// 2026-07-08 修复: 分页渲染 transcript (避免 3331 段触发 Element Plus 栈溢出)
// 每次只渲染前 pageCount * 50 段，"加载更多"按钮递增 pageCount
const displayedTranscriptEntries = computed(() => {
  const all = transcriptEntries.value || []
  const end = Math.min(all.length, transcriptPageCount.value * TRANSCRIPT_PAGE_SIZE)
  return all.slice(0, end)
})
const hasMoreTranscript = computed(
  () => (transcriptEntries.value?.length || 0) > displayedTranscriptEntries.value.length
)
function loadMoreTranscript() {
  transcriptPageCount.value++
}

async function autoPolishIfNeeded() {
  if (!meeting.value) return
  const entries = transcriptEntries.value
  if (!entries.length) return

  // 收集需要润色的 entries (跳过 DB 中已润色 / 短文本)
  const pending = []  // { i, text }
  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i]
    if (!entry) continue
    const trimmed = (entry.text || '').trim()
    if (trimmed.length < 3) continue
    const origIdx = entry._origIndex ?? i
    const polEntry = meeting.value.transcript_polished?.[origIdx]
    const rawEntry = meeting.value.transcript?.[origIdx]
    // 跳过: DB 中 transcript_polished[i].text 已与原 transcript[i].text 不同 (= 已润色)
    if (polEntry && rawEntry && polEntry.text !== rawEntry.text) continue
    pending.push({ i, text: entry.text })
  }
  if (!pending.length) return

  // 2026-07-08 修复: 大会议 (>= 500 段) 跳过自动润色
  // 根因: Promise.all 并发 17 个 polish-text-batch 请求 → 每请求 60s LLM 调用 +
  // 持 DB session → 后端连接池 30 个全占满 → 所有 API 500/504
  // 长会议用户已能接受原始 ASR 文本 (会议纪要 + 关键要点已由 LLM 生成)
  if (pending.length >= 500) {
    console.warn(`[MeetingDetailView] ${pending.length} 段待润色 > 500，跳过自动润色（防 DB 连接池耗尽）`)
    return
  }

  // 按 200 条分块（后端 polish-text-batch 端点硬上限 200 条/批，防 LLM token 超限）
  // 长会议 #120 (3357 段) / #95 (333 段) / #151 (426 段) 不分块会触发 400
  const BATCH_SIZE = 200
  const chunks = []
  for (let i = 0; i < pending.length; i += BATCH_SIZE) {
    chunks.push(pending.slice(i, i + BATCH_SIZE))
  }

  // 2026-07-08 修复: 并发限流 (max 3 chunk 同时) 防连接池耗尽
  // 原版 Promise.all 会把所有 chunk 同时发, 17 个 LLM 请求持 17 个 DB session
  const MAX_CONCURRENT_CHUNKS = 3
  const responses = new Array(chunks.length).fill(null)

  for (let i = 0; i < chunks.length; i += MAX_CONCURRENT_CHUNKS) {
    const batch = chunks.slice(i, i + MAX_CONCURRENT_CHUNKS).map((chunk, idx) => ({
      chunk, idx: i + idx,
      promise: axios.post(`/api/v1/meetings/${meeting.value.id}/polish-text-batch`, {
        texts: chunk.map(p => p.text),
      }).catch(() => null)  // 单 chunk 失败不影响其他 chunk
    }))
    const settled = await Promise.all(batch.map(b => b.promise))
    settled.forEach((res, k) => { responses[batch[k].idx] = res })
  }

  let pendingIdx = 0
  for (let ci = 0; ci < chunks.length; ci++) {
    const res = responses[ci]
    const chunk = chunks[ci]
    const polishedArr = res?.data?.polished
    if (!polishedArr) {
      pendingIdx += chunk.length
      continue
    }
    for (let k = 0; k < chunk.length && k < polishedArr.length; k++) {
      const polished = polishedArr[k]
      if (polished && polished !== pending[pendingIdx].text) {
        polishedTexts.value[pending[pendingIdx].i] = polished
      }
      pendingIdx++
    }
  }
}

function getPolishedText(entry, index) {
  return polishedTexts.value[index] || entry.text
}

// 2026-07-08 修复: 封装 savingTranscriptSpeaker === i 为函数, 避免每个 popover/select 单独的 reactive 依赖
// 根因: template 直接用 `savingTranscriptSpeaker === i` 时, Vue 把 savingTranscriptSpeaker 设为
//       50 个 popover 的依赖 → 任何 savingTranscriptSpeaker 变化触发 50 个 popover 全部重 mount → 循环
// 修法: 用 markRaw 把 ref 包成非响应式, 函数内只读普通变量 (_currentSavingIdx)
//       这样函数被 50 个 popover 调用, 但**不**建立 reactive 依赖, 不会触发循环
//       watch 同步更新 _currentSavingIdx (单向数据流, reactive → 缓存变量)
function isSpeakerSaving(i) {
  return _currentSavingIdx === i
}

// _currentSavingIdx 是普通变量 (let), 必须在 setup 顶层声明
// 由上面的 watch 同步, 不建立 reactive 依赖
let _currentSavingIdx = -1

// 2026-06-26 新增: 头部头像 fallback — meeting.participants 为空时, 从 transcript[].speaker 去重
const effectiveParticipants = computed(() => {
  if (meeting.value?.participants?.length) return meeting.value.participants
  const transcript = meeting.value?.transcript || []
  const seen = new Set()
  const list = []
  for (const seg of transcript) {
    const sp = seg.speaker
    if (!sp || sp.startsWith('发言人') || sp === '?') continue
    if (seen.has(sp)) continue
    seen.add(sp)
    list.push({ name: sp })
  }
  return list
})

const speakerOptions = computed(() => {
  const options = new Set()
  memberStore.members.forEach(m => {
    if (m.name) options.add(m.name)
  })
  ;(transcriptEntries.value || []).forEach(entry => {
    if (entry?.speaker) options.add(entry.speaker)
  })
  ;['发言人A', '发言人B', '发言人C', '发言人D', '未知'].forEach(name => options.add(name))
  return Array.from(options)
})

// 解析条目中的发言人（如 "【杜同贺】介绍了..." → "杜同贺"）
function parseSpeaker(text) {
  const match = text.match(/^【(.+?)】/)
  return match ? match[1] : null
}

// 去掉发言人前缀
function removeSpeakerPrefix(text) {
  return text.replace(/^【.+?】/, '')
}

function topicLabel(text) {
  const t = String(text || '')
  if (/ASV|菌群|微生物|多样性|群落/.test(t)
      && !/赴现场|现场配合|安装调试/.test(t)) return '微生物群落'
  if (/赴现场|现场配合|现场检查|现场设备|安装调试|水质检测/.test(t)) return '现场与设备'
  if (/旋流|纯氧机|实验装置|装置设计/.test(t)) return '装置与实验'
  if (/文献|综述|界面活性氧/.test(t)) return '文献与机制'
  if (/通过模拟|分子动力学|扩散|模型假设|模拟分析/.test(t)) return '模型与模拟'
  if (/实测|文件|计算|数据|对照/.test(t)) return '数据可靠性'
  if (/机制|自由基/.test(t)) return '机制讨论'
  if (/论文|第\s*25|换水|主线/.test(t)) return '论文主线'
  return '讨论要点'
}

// 合并所有同一发言者的条目（非连续也合并）
function groupBySpeaker(items) {
  if (!items?.length) return []
  const map = new Map()  // speaker → items[]
  const order = []       // 保持发言人首次出现顺序
  for (const item of items) {
    const speaker = parseSpeaker(item)
    const text = speaker ? removeSpeakerPrefix(item) : item
    if (speaker) {
      if (!map.has(speaker)) {
        map.set(speaker, [])
        order.push(speaker)
      }
      map.get(speaker).push(text)
    } else {
      // 无发言人前缀的条目单独显示
      order.push(null)
      map.set(null, [text])
    }
  }
  // 去重：同一发言人的相同内容只保留一条
  const result = []
  const seen = new Set()
  for (const speaker of order) {
    const items = map.get(speaker)
    const unique = items.filter(item => {
      const key = item.trim()
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    if (unique.length) {
      result.push({ speaker, items: unique, _editValues: unique.map(() => speaker) })
    }
  }
  return result
}

// 分组后的讨论要点和决议
const groupedDecisions = computed(() => groupBySpeaker(meeting.value?.decisions))

const topicCards = computed(() => (meeting.value?.key_points || []).map((item, index) => {
  const speaker = parseSpeaker(item)
  const text = speaker ? removeSpeakerPrefix(item) : item
  return {
    speaker: speaker || '未识别发言人',
    text,
    title: topicLabel(text),
    index,
    anonymous: !speaker,
  }
}))
const visibleTopicCards = computed(() => (
  showAllTopics.value ? topicCards.value : topicCards.value.slice(0, 6)
))
const actionColumns = computed(() => groupedDecisions.value.slice(0, 3).map((group) => ({
  speaker: group.speaker || '未识别发言人',
  count: group.items.length,
  items: group.items.slice(0, 3),
  more: Math.max(0, group.items.length - 3),
})))
const totalDecisionCount = computed(() => (
  groupedDecisions.value.reduce((sum, group) => sum + group.items.length, 0)
))
const summaryPreview = computed(() => {
  const summary = meeting.value?.summary || ''
  return showFullSummary.value || summary.length <= 140 ? summary : `${summary.slice(0, 140)}…`
})
const summaryCanExpand = computed(() => (meeting.value?.summary || '').length > 140)

const form = ref({ title: '', start_time: '', location: '', participants: [], presenter_ids: [], description: '' })
const minutesForm = ref({ summary: '', key_points: [], decisions: [] })

// ===== 数据加载 =====

const fetchMeeting = async () => {
  try {
    const res = await axios.get(`/api/v1/meetings/${route.params.id}`)
    meeting.value = res.data
    // 异步触发润色: 后端已用 Redis 缓存 (key=polish:{meeting_id}:{text_hash}, TTL=24h),
    // 同一段文本二次请求直接命中缓存, 重复跑也无性能损耗. 用 requestIdleCallback 不阻塞渲染.
    const schedule = window.requestIdleCallback || ((cb) => setTimeout(cb, 800))
    schedule(() => autoPolishIfNeeded())
    // 如果没有发言统计但有转录，自动获取统计数据
    if (!meeting.value.speaker_stats && meeting.value.transcript?.length) {
      try {
        const analyticsRes = await axios.get(`/api/v1/meetings/${route.params.id}/analytics`)
        meeting.value.speaker_stats = analyticsRes.data.speaker_stats || []
      } catch { /* 静默失败 */ }
    }
  } catch {
    ElMessage.error('加载会议失败')
  }
}

// ===== 编辑模式 =====

function enterEdit() {
  // 确保日期格式兼容 el-date-picker (YYYY-MM-DD HH:mm:ss)
  let startTime = meeting.value.start_time || ''
  if (startTime && startTime.includes('T')) {
    startTime = startTime.replace('T', ' ').replace(/\.\d+$/, '')
  }
  form.value = {
    title: meeting.value.title,
    start_time: startTime,
    location: meeting.value.location || '',
    participants: meeting.value.participants?.map(p => p.member_id) || [],
    presenter_ids: meeting.value.presenter_ids || [],
    description: meeting.value.description || '',
  }
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

const saveBasic = async () => {
  saving.value = true
  try {
    await axios.put(`/api/v1/meetings/${meeting.value.id}`, {
      title: form.value.title,
      start_time: form.value.start_time,
      location: form.value.location,
      description: form.value.description,
      participants: form.value.participants,
    })
    ElMessage.success('已保存')
    editing.value = false
    await fetchMeeting()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

// ===== 纪要编辑 =====

function enterEditMinutes() {
  minutesForm.value = {
    summary: meeting.value.summary || '',
    key_points: meeting.value.key_points ? [...meeting.value.key_points] : [],
    decisions: meeting.value.decisions ? [...meeting.value.decisions] : [],
  }
  editingMinutes.value = true
}

const saveMinutes = async () => {
  try {
    await axios.put(`/api/v1/meetings/${meeting.value.id}`, {
      summary: minutesForm.value.summary,
      key_points: minutesForm.value.key_points.filter(Boolean),
      decisions: minutesForm.value.decisions.filter(Boolean),
    })
    ElMessage.success('纪要已保存')
    editingMinutes.value = false
    await fetchMeeting()
  } catch {
    ElMessage.error('保存失败')
  }
}

async function saveTranscriptSpeaker(displayIndex, speaker) {
  if (!meeting.value || !speaker) return
  savingTranscriptSpeaker.value = displayIndex
  // 用合并前的原始索引（如果有的话）
  const entry = transcriptEntries.value[displayIndex]
  const realIndex = entry?._origIndex ?? displayIndex
  try {
    const res = await axios.patch(`/api/v1/meetings/${meeting.value.id}/transcript-speaker`, {
      entry_index: realIndex,
      speaker,
    })
    meeting.value.transcript = res.data.transcript
    meeting.value.transcript_polished = res.data.transcript_polished
    meeting.value.speaker_mapping = res.data.speaker_mapping
    meeting.value.speaker_stats = res.data.speaker_stats
    ElMessage.success('发言人已更新')
  } catch {
    ElMessage.error('更新发言人失败')
  } finally {
    savingTranscriptSpeaker.value = null
  }
}

// ===== 删除 =====

const handleDelete = async () => {
  try {
    await axios.delete(`/api/v1/meetings/${meeting.value.id}`)
    ElMessage.success('已删除')
    router.push('/meetings')
  } catch {
    ElMessage.error('删除失败')
  }
}

// ===== 相关会议 =====

async function loadRelated() {
  try {
    const resp = await fetch(`/api/v1/meetings/${meeting.value.id}/related?top_k=3`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
    })
    if (resp.ok) relatedMeetings.value = await resp.json()
  } catch { /* ignore */ }
}

// ===== 辅助函数 =====

function getSpeakerAvatar(name) {
  if (!name) return null
  const member = memberStore.members.find(m => m.name === name)
  return member?.avatar || null
}

function getAudioSrc(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return `/minio/microbubble/${url}`
}

const formatDate = (d) => {
  // 2026-11-10 时区收口: parseDbDate 显式按 UTC 解析 (替换 dayjs+add(8))
  const parsed = parseDbDate(d)
  return parsed ? dayjs(parsed).format('YYYY-MM-DD HH:mm') : ''
}
const formatTs = (sec) => {
  const s = Math.floor(sec || 0)
  return `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`
}
const formatDuration = (sec) => {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}
const statusLabel = (s) => ({
  scheduled: '已预约',
  recording: '录制中',
  processing: '处理中',
  completed: '已完成',
  completed_with_warnings: '已完成（含部分警告）',
  cancelled: '已取消',
  error: '处理失败',
}[s] || s)
const statusType = (s) => ({
  scheduled: 'info',
  recording: 'warning',
  processing: 'warning',
  completed: 'success',
  completed_with_warnings: 'warning',
  cancelled: 'info',
  error: 'danger',
}[s] || '')

onMounted(async () => {
  document.body.classList.add('meeting-topic-board')
  await memberStore.fetchMembers()
  await fetchMeeting()
  await loadRelated()
})

onUnmounted(() => {
  document.body.classList.remove('meeting-topic-board')
})
</script>

<style scoped>
/* ====== 布局 ====== */
.meeting-detail {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  padding: 16px 20px;
  gap: 16px;
  overflow: hidden;
}

/* ====== Hero ====== */
.detail-hero {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px 24px;
  background: linear-gradient(180deg, #fff 0%, var(--color-bg-page, #f5f7fa) 100%);
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--color-border, #ebeef5);
  flex-shrink: 0;
  position: relative; /* 2026-11-04: hero-progress(卡片下边缘进度) 的定位基准 */
}

.hero-back { flex-shrink: 0; }

.hero-main { flex: 1; min-width: 0; }

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.hero-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-primary, #2d2d2d);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hero-title-row.editing { gap: 12px; }
.edit-title-input { max-width: 400px; }

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: var(--radius-full, 9999px);
  font-size: 13px;
  font-weight: 500;
  flex-shrink: 0;
}
.status-badge .status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-badge.status-scheduled { background: var(--color-info-bg); color: var(--color-info); }
.status-badge.status-scheduled .status-dot { background: var(--color-info); }
.status-badge.status-recording { background: var(--color-primary-bg); color: var(--color-primary); }
.status-badge.status-recording .status-dot { background: var(--color-primary); animation: dot-pulse 1.2s infinite; }
.status-badge.status-processing { background: var(--color-warning-bg); color: var(--color-warning); }
.status-badge.status-processing .status-dot { background: var(--color-warning); animation: dot-pulse 1.5s infinite; }
.status-badge.status-completed { background: var(--color-success-bg); color: var(--color-success); }
.status-badge.status-completed .status-dot { background: var(--color-success); }
.status-badge.status-cancelled { background: var(--color-info-bg); color: var(--color-info); }
.status-badge.status-cancelled .status-dot { background: var(--color-info); opacity: 0.5; }
.status-badge.status-error { background: var(--color-danger-bg); color: var(--color-danger); }
.status-badge.status-error .status-dot { background: var(--color-danger); }

.hero-meta {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: var(--color-text-regular, #606266);
}
.meta-item .el-icon { color: var(--color-text-secondary, #909399); }

.hero-participants { margin-top: 4px; }

.hero-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
  align-self: flex-start;
}

/* ====== 主体 ====== */
.detail-body {
  flex: 1;
  display: flex;
  gap: 16px;
  overflow: hidden;
}

.detail-main {
  flex: 1;
  overflow-y: auto;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--color-border, #ebeef5);
}

/* ====== 2026-10-25: 失败态卡片 (status=error) ====== */
.failure-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin: 16px 20px 0;
  padding: 14px 16px;
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--color-danger, #F56C6C);
  background: var(--color-danger-bg);
}
.failure-icon {
  font-size: 20px;
  line-height: 1.4;
}
.failure-body {
  flex: 1;
  min-width: 0;
}
.failure-title {
  font-weight: 600;
  color: var(--color-danger, #F56C6C);
  margin-bottom: 4px;
}
.failure-detail {
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-regular);
}
.failure-hint {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
.failure-technical {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.failure-technical summary {
  cursor: pointer;
}
.failure-technical code {
  display: block;
  margin-top: 6px;
  padding: 8px 10px;
  border-radius: var(--radius-sm, 4px);
  background: var(--color-bg-secondary);
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
  white-space: pre-wrap;
}
.failure-actions {
  flex-shrink: 0;
}

/* 转录空态: 失败时补一句可读原因 */
.transcript-empty-hint {
  text-align: center;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-secondary);
  max-width: 520px;
  margin: -8px auto 0;
  padding: 0 20px;
}

/* 铁律 31: 替代原 .detail-tabs el-tabs */
.tab-strip-wrapper {
  margin-bottom: var(--space-3);
  display: flex;
  align-items: center;
}

.tab-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ====== 侧边栏 ====== */
.detail-side {
  width: 320px;
  flex-shrink: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.side-card {
  border-radius: var(--radius-lg, 12px);
}
.side-card :deep(.el-card__header) {
  font-weight: 600;
  font-size: 14px;
  padding: 12px 16px;
}

.audio-meta {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

.call-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  cursor: pointer;
  border: 2px dashed var(--color-border, #ebeef5);
  border-radius: var(--radius-lg, 12px);
  transition: var(--transition-all-normal);
}
.call-placeholder:hover {
  border-color: var(--color-primary, #FF7A5C);
  background: var(--color-primary-bg, #fff0ed);
}
.call-placeholder p {
  margin: 8px 0 0;
  font-size: 14px;
  color: var(--color-text-secondary, #909399);
}

/* ====== 纪要 ====== */
.section h4 {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary, #2d2d2d);
}
.speaker-group {
  margin-bottom: 12px;
}
.speaker-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
/* v71 P1: 移除 .speaker-row.clickable / .expanded / .toggle-icon / .rotated (默认展开, 不再折叠) */
/* .speaker-row 仅作为 flex 容器, 不再有 clickable 行为 */
.speaker-avatar {
  flex-shrink: 0;
}
.speaker-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary, #FF7A5C);
}
.speaker-name--anonymous {
  color: var(--color-text-secondary, #909399);
  font-weight: 500;
}
.speaker-count {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
  font-weight: normal;
  margin-left: auto;
}

/* v71 P1: 展开全部/收起按钮 (per-card) */
.more-items {
  list-style: none;
  margin-top: 6px;
  padding-left: 0;
}
.more-items-button {
  font-size: 13px;
  padding: 4px 0;
  margin-left: -4px;
}

/* v72 P1: TL;DR 主题色卡 (v70 P3 容器 + 主题色自适应) */
.tldr-card {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--color-primary) 10%, transparent),
    color-mix(in srgb, var(--color-primary) 6%, transparent)
  );
  border: 1px solid color-mix(in srgb, var(--color-primary) 30%, transparent);
  border-radius: var(--radius-md, 8px);
  padding: 12px 16px;
  margin-bottom: 16px;
}
.tldr-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.tldr-icon {
  color: var(--color-primary);
  font-size: 16px;
}
.tldr-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text-primary, #303133);
}
.tldr-summary {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: var(--color-text-regular, #606266);
}
.point-item {
  cursor: pointer;
  transition: background 0.15s;
  border-radius: var(--radius-sm, 4px);
  padding: 2px 4px;
  margin-left: -4px;
}
.point-item:hover {
  background: var(--color-bg-page, #f5f7fa);
}
.inline-speaker-select {
  width: 84px;
}
.transcript-speaker-select {
  width: 90px;
}
.speaker-name-btn {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
  cursor: pointer;
  transition: var(--transition-all-fast) ease;
  min-width: 64px;
  text-align: left;
}
.speaker-name-btn:hover {
  background: var(--color-bg-page, #f5f7fa);
  border-color: var(--color-border-light, #ebeef5);
}
.speaker-name-btn.saving {
  opacity: 0.5;
  cursor: wait;
}
.point-text {
  flex: 1;
}
.points-list, .decisions-list {
  padding-left: 20px;
  margin: 0;
}
.points-list li, .decisions-list li {
  margin-bottom: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-regular, #606266);
}
.decisions-list li::marker {
  color: var(--color-warning, #E6A23C);
}

/* v71 P1: 议程 timeline 样式 (替换旧 .agenda-list) */
.agenda-count {
  font-size: 12px;
  font-weight: normal;
  color: var(--color-text-secondary, #909399);
  margin-left: 8px;
}
.agenda-timeline {
  padding-left: 4px;
  margin-top: 4px;
}
.agenda-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-primary, #FF7A5C);
  color: var(--color-bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 0 0 3px var(--color-bg-card, #fff);
}
.agenda-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-regular, #606266);
  padding: 4px 0;
}
.edit-minutes-btn {
  margin-top: 8px;
  align-self: flex-start;
}
.section-actions {
  display: flex;
  gap: 8px;
}

/* ====== 转录记录 ====== */
.transcript-entry {
  display: flex;
  gap: 12px;
}
.transcript-entry.entry-removed {
  opacity: 0.5;
}
.transcript-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}
.transcript-avatar {
  flex-shrink: 0;
}
.transcript-line {
  flex: 1;
  width: 2px;
  background: var(--color-border, #ebeef5);
  margin: 4px 0;
}
.transcript-entry:last-child .transcript-line {
  display: none;
}
/* 2026-07-08 修复: transcript 分页按钮 (避免 3331 段一次性渲染触发 Element Plus 栈溢出) */
.transcript-load-more {
  text-align: center;
  padding: 24px 0 12px;
  border-top: 1px dashed var(--color-border, #e0e0e0);
  margin-top: 8px;
}
.transcript-load-more .load-more-btn {
  min-width: 240px;
  padding: 10px 22px;
  border: 1px solid var(--color-primary-border, #f7c7bb);
  border-radius: var(--radius-md, 8px);
  background: var(--color-primary-bg, #fff0ed);
  color: var(--color-primary-text, #b84523);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition-all-normal, background-color .2s, border-color .2s);
}
.transcript-load-more .load-more-btn:hover {
  background: var(--color-primary, #ff7a5c);
  border-color: var(--color-primary, #ff7a5c);
  color: #fff;
}
.transcript-load-more .load-more-btn:focus-visible {
  outline: 2px solid var(--color-primary, #ff7a5c);
  outline-offset: 2px;
}
.transcript-body {
  flex: 1;
  padding-bottom: 16px;
}
.transcript-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.transcript-speaker {
  font-weight: 600;
  font-size: 14px;
  color: var(--color-primary, #FF7A5C);
}
.transcript-ts {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  margin-left: auto;
}
.transcript-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-regular, #606266);
}
.transcript-text.removed {
  display: flex;
  align-items: center;
  gap: 6px;
  font-style: italic;
  text-decoration: line-through;
  color: var(--color-text-secondary, #909399);
}
.remove-reason {
  font-size: 12px;
  color: var(--color-text-placeholder, #c0c4cc);
}

/* ====== 相关会议 ====== */
.related-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border, #ebeef5);
}
.related-item:last-child { border-bottom: none; }
.related-link {
  font-size: 13px;
  color: var(--color-primary, #FF7A5C);
  text-decoration: none;
  font-weight: 500;
}
.related-link:hover { text-decoration: underline; }
.related-similarity {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

/* ====== 编辑态表单 ====== */
.hero-meta .el-date-editor {
  --el-date-editor-width: 200px;
}

/* ====== 纪要编辑列表 ====== */
.item-list { display: flex; flex-direction: column; gap: 8px; }
.item-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; background: var(--color-bg-page, #f5f7fa); border-radius: var(--radius-md, 8px);
  border: 1px solid transparent; transition: var(--transition-all-normal);
}
.item-row:hover, .item-row:focus-within { border-color: rgba(var(--color-primary-rgb), 0.3); background: var(--color-primary-bg, #fff0ed); }
.item-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: var(--color-primary, #FF7A5C); }
.decision-dot { background: var(--color-warning, #E6A23C); }
.item-row .el-input { flex: 1; }
.item-del { opacity: 0; transition: opacity 0.2s; }
.item-row:hover .item-del { opacity: 1; }
.item-add { width: 100%; justify-content: center; border-style: dashed; }
.decision-add { color: var(--color-warning, #E6A23C); border-color: var(--color-warning, #E6A23C); }

/* ====== 加载态 ====== */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 8px;
  color: var(--color-text-secondary, #909399);
}

/* ====== 入场动画 ====== */
.fade-slide-up {
  animation: fadeSlideUp 300ms var(--ease-out) both;
}
/* ====== 响应式 ====== */
@media (max-width: 768px) {
  .meeting-detail { height: auto; }
  .detail-hero { flex-direction: column; }
  .hero-actions { flex-direction: row; align-self: stretch; }
  .detail-body { flex-direction: column; }
  .detail-side { width: 100%; }
  .hero-title { font-size: 18px; }
  /* 选型⑤: 窄屏下播放行允许换行, 隐藏等宽提示 */
  .hero-player { flex-wrap: wrap; row-gap: 10px; }
  .hp-note { display: none; }
}
/* 03 议题板外壳：把旧的“大英雄卡”收成简报式页头 */
.meeting-detail { background: #f7f3eb; padding: 10px 18px; gap: 12px; }
.detail-hero {
  padding: 8px 4px 13px;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--color-border, #e5ded2);
  border-radius: 0;
}
.hero-title { font-size: 31px; line-height: 1.22; white-space: normal; }
.hero-meta { gap: 14px; margin-bottom: 7px; }
.meta-item { font-size: 11px; }
.hero-actions { flex-direction: row; align-self: flex-end; gap: 8px; }
.hero-player { margin-top: 9px; padding-top: 9px; }
.hp-note { display: none; }
.hero-progress { display: none; }
.detail-main { background: transparent; border: 0; border-radius: 0; }
</style>

<style>
/* v69 P1b: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
[data-theme="dark"] .detail-hero {
  background: linear-gradient(180deg, var(--color-bg-card) 0%, var(--color-bg-page) 100%);
  border-color: var(--color-border);
}
[data-theme="dark"] .status-badge.status-scheduled {
  background: rgba(144, 147, 153, 0.18);
  color: var(--color-text-secondary);
}
[data-theme="dark"] .status-badge.status-scheduled .status-dot { background: var(--color-text-secondary); }
[data-theme="dark"] .status-badge.status-recording {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
[data-theme="dark"] .status-badge.status-recording .status-dot { background: var(--color-primary); }
[data-theme="dark"] .status-badge.status-processing {
  background: var(--color-warning-bg);
  color: var(--color-warning, #E6A23C);
}
[data-theme="dark"] .status-badge.status-processing .status-dot { background: var(--color-warning, #E6A23C); }
[data-theme="dark"] .status-badge.status-completed {
  background: var(--color-success-bg);
  color: var(--color-success, #67C23A);
}
[data-theme="dark"] .status-badge.status-completed .status-dot { background: var(--color-success, #67C23A); }
[data-theme="dark"] .status-badge.status-cancelled {
  background: rgba(144, 147, 153, 0.18);
  color: var(--color-text-secondary);
}
[data-theme="dark"] .status-badge.status-cancelled .status-dot { background: var(--color-text-secondary); }
[data-theme="dark"] .status-badge.status-error {
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
}
[data-theme="dark"] .status-badge.status-error .status-dot { background: var(--color-danger, #F56C6C); }
[data-theme="dark"] .detail-main {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .call-placeholder {
  border-color: var(--color-border);
}
[data-theme="dark"] .call-placeholder:hover {
  background: var(--color-primary-bg);
}
[data-theme="dark"] .point-item:hover {
  background: var(--color-bg-page);
}
[data-theme="dark"] .transcript-line {
  background: var(--color-border);
}
[data-theme="dark"] .item-row {
  background: var(--color-bg-page);
}
[data-theme="dark"] .item-row:hover,
[data-theme="dark"] .item-row:focus-within {
  border-color: var(--color-primary-border);
  background: var(--color-primary-bg);
}
[data-theme="dark"] .related-item {
  border-bottom-color: var(--color-border);
}

/* v72 P1 TL;DR 主题色卡 dark mode + v71 P1 议程 timeline dark mode (v60-v67 教训: 必须非 scoped 块) */
[data-theme="dark"] .tldr-card {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--color-primary) 8%, transparent),
    color-mix(in srgb, var(--color-primary) 4%, transparent)
  );
  border-color: color-mix(in srgb, var(--color-primary) 25%, transparent);
}
/* v71 P1: 议程 timeline dark mode */
[data-theme="dark"] .agenda-dot {
  background: var(--color-primary);
  color: var(--color-bg-card);
  box-shadow: 0 0 0 3px var(--color-bg-card);
}
[data-theme="dark"] .agenda-text {
  color: var(--color-text-regular);
}
[data-theme="dark"] .agenda-count {
  color: var(--color-text-secondary);
}
/* v71 P1: 移除 .speaker-row.clickable / .expanded dark (不再折叠) */

/* ═══ 2026-09-13 方案B「时间轴剧场」· 配色④青灰水墨页面令牌 ═══ */
.meeting-detail {
  --color-text-primary: #1c2427;
  --color-text-regular: #39434b;
  --color-text-secondary: #78848a;
  --color-text-placeholder: #a9b3b9;
  --color-border: #d9dee1;
  --color-border-light: #e6ebee;
  --color-info-bg: #eef1f3;
  --color-primary: #3d6b64;
  --color-primary-light: #4a7d75;
  --color-primary-dark: #2f544e;
  --color-primary-bg: #edf2f1;
  --color-primary-border: rgba(61, 107, 100, 0.35);
  --color-accent: #3d6b64;
  --color-accent-bg: #edf2f1;
  --color-primary-strong: #1c2427;
  --el-color-primary: #1c2427;
  --el-color-primary-light-3: #454f55;
  --el-color-primary-light-5: #6e777d;
  --el-color-primary-light-7: #a8aeb3;
  --el-color-primary-light-8: #c8cdd1;
  --el-color-primary-light-9: #e9eced;
  --el-color-primary-dark-2: #161d20;
}

/* 2026-11-04 选型⑤「融于卡片」: 播放器住进英雄卡, 进度=卡片下边缘 */
.hero-player {
  margin-top: 14px; padding-top: 12px;
  border-top: 1px solid var(--color-border-light, #eef1f1);
  display: flex; align-items: center; gap: 12px;
}
.hp-play {
  /* 2026-11-09: 设计稿是 30×30 的正圆。mobile-base.css 的全局
     button{min-height:var(--touch-target-min)}（44px）会把 height:30px 钳成
     44px ⇒ 30×44 椭圆（截图里的形状）。min-height 永远压过 height，
     单写 !important 也容易被后续规则覆盖 ⇒ 用 aspect-ratio + min-height:0
     显式解除，并把 44px 触控区挪到 ::before 伪元素（视觉仍是正圆）。 */
  width: 30px; height: 30px; min-height: 0; aspect-ratio: 1 / 1;
  box-sizing: border-box; padding: 0; line-height: 1;
  border-radius: 50%; flex-shrink: 0; cursor: pointer;
  position: relative;
  background: var(--color-primary); color: #fff; border: none; font-size: 10px;
  display: grid; place-items: center;
  transition: transform var(--duration-fast, .15s) ease-out, background .15s;
}
.hp-play::before {
  content: ''; position: absolute; inset: -7px; border-radius: 50%;
}
.hp-play:hover { transform: scale(1.06); background: var(--color-primary-dark); }
.hp-tm { font-family: Consolas, 'SFMono-Regular', monospace; font-size: 12px; letter-spacing: .06em; white-space: nowrap; color: var(--color-text-secondary); }
.hp-sep { opacity: .45; margin: 0 2px; }
.hp-track {
  flex: 1; height: 2px; border-radius: 2px; cursor: pointer;
  background: var(--color-border-light, #e3e8e6); position: relative;
  transition: height .15s ease-out;
}
.hp-track:hover { height: 5px; }
.hp-track i {
  position: absolute; left: 0; top: 0; height: 100%;
  background: var(--color-primary); border-radius: 2px;
}
.hp-spd {
  font-family: Consolas, monospace; font-size: 11px; cursor: pointer;
  background: transparent; color: var(--color-text-secondary);
  border: 1px solid var(--color-border); border-radius: 9999px; padding: 1px 9px;
}
.hp-spd:hover { color: var(--color-primary); border-color: var(--color-primary-border, rgba(61,107,100,.2)); }
.hp-note {
  font-family: Consolas, monospace; font-size: 10px; letter-spacing: .14em;
  color: var(--color-text-placeholder); white-space: nowrap;
}
.hp-noaudio {
  margin-top: 14px; padding-top: 12px;
  border-top: 1px solid var(--color-border-light);
  font-family: Consolas, monospace; font-size: 11px; letter-spacing: .08em;
  color: var(--color-text-placeholder);
}
/* 进度 = 卡片下边缘的一条 2px 色线 (detail-hero 加 position:relative) */
.hero-progress {
  position: absolute; left: 0; right: 0; bottom: -1px; height: 2px;
  border-radius: 0 0 var(--radius-lg, 12px) var(--radius-lg, 12px);
  overflow: hidden; pointer-events: none;
}
.hero-progress i { display: block; height: 100%; background: var(--color-primary); transition: width .2s linear; }

/* 转录时间戳 → seek 按钮 */
.transcript-ts.ts-seek {
  cursor: pointer; color: var(--teal-soft, #198e83);
  font-weight: 700; border-bottom: 1px dashed currentColor;
  margin-left: auto;
}
.transcript-ts.ts-seek:hover { color: var(--coral, #ef7256); }

/* 当前播放段高亮 */
.transcript-entry.entry-current {
  background: var(--color-primary-bg, #edf2f1);
  box-shadow: inset 2px 0 0 var(--color-primary);
  border-radius: 4px;
}

/* 侧栏摘要/决议卡 */
.side-eyebrow {
  font-family: Consolas, monospace; font-size: 9px; letter-spacing: .25em;
  color: var(--color-text-secondary);
}
.side-abstract-text {
  font-size: 12.5px; color: var(--color-text-regular); line-height: 1.75; margin: 0;
  max-height: 200px; overflow-y: auto;
}
.side-decision-group { margin-bottom: 10px; }
.side-decision-who {
  font-weight: 700; font-size: 12px; color: var(--color-primary);
  margin-bottom: 3px;
}
.side-decision-list { list-style: none; padding-left: 12px; }
.side-decision-list li {
  font-size: 12px; color: var(--color-text-regular); line-height: 1.6;
  padding: 2px 0; position: relative;
}
.side-decision-list li::before { content: '·'; color: var(--coral); font-weight: 700; position: absolute; left: -10px; }

/* ====== 议题板（2026-11-11 会议详情重设计 03） ====== */
.topic-board { display: flex; flex-direction: column; gap: 18px; }
.topic-brief {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 13px;
}
.topic-brief-main {
  position: relative;
  overflow: hidden;
  border-radius: 12px;
  padding: 20px 22px 18px;
  color: #eff8f3;
  background: linear-gradient(135deg, #2c6e63 0%, #24584e 100%);
}
.topic-brief-main::after {
  content: '';
  position: absolute;
  width: 180px; height: 180px;
  right: -55px; top: -80px;
  border: 1px solid rgba(255, 255, 255, .13);
  border-radius: 50%;
  pointer-events: none;
}
.topic-eyebrow {
  font-family: Consolas, monospace;
  font-size: 9px;
  letter-spacing: .18em;
  color: var(--color-primary, #ff7a5c);
}
.topic-brief-main .topic-eyebrow { color: #d0e8df; margin-bottom: 9px; }
.topic-brief-main p {
  position: relative;
  z-index: 1;
  max-width: 680px;
  margin: 0;
  font-family: "Noto Serif SC", "Songti SC", serif;
  font-size: 16px;
  line-height: 1.8;
  color: #eff8f3;
}
.topic-text-btn {
  display: inline-block;
  margin-top: 11px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-primary, #ff7a5c);
  font: inherit;
  font-size: 10px;
  cursor: pointer;
  text-decoration: none;
  border-bottom: 1px solid currentColor;
}
.topic-brief-main .topic-text-btn { color: #d9eee7; }
.topic-facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  overflow: hidden;
  border: 1px solid var(--color-border, #ebeef5);
  border-radius: 12px;
  background: var(--color-border, #ebeef5);
}
.topic-facts > div { background: var(--color-bg-card, #fff); padding: 15px 16px; }
.topic-facts b {
  display: block;
  color: #2c6e63;
  font-size: 25px;
  line-height: 1;
  font-weight: 650;
}
.topic-facts span { display: block; margin-top: 6px; color: var(--color-text-secondary, #909399); font-size: 10px; }
.topic-section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin: 4px 0 10px;
}
.topic-section-head > div { display: flex; align-items: baseline; gap: 10px; }
.topic-section-head h4 { margin: 0; color: var(--color-text-primary, #2d2d2d); font-size: 16px; font-weight: 700; }
.topic-section-head > span { color: var(--color-text-secondary, #909399); font-size: 10px; }
.topic-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 11px; }
.topic-card {
  position: relative;
  min-height: 116px;
  overflow: hidden;
  border: 1px solid var(--color-border, #ebeef5);
  border-radius: 11px;
  background: var(--color-bg-card, #fff);
  padding: 15px 16px 13px;
}
.topic-card::before { content: ''; position: absolute; left: 0; right: 0; top: 0; height: 3px; background: var(--color-primary, #ff7a5c); }
.topic-card:nth-child(3n+2)::before { background: #c8893d; }
.topic-card:nth-child(3n+3)::before { background: #6b88a1; }
.topic-card-anonymous::before { background: var(--color-text-placeholder, #c0c4cc); }
.topic-card-top { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.topic-avatar { width: 23px; height: 23px; border-radius: 50%; flex: 0 0 auto; display: grid; place-items: center; background: #dbeae5; color: #2c6e63; font-size: 9px; font-weight: 700; background-size: cover; background-position: center; }
.topic-avatar.has-img { color: transparent; }
.topic-who { color: var(--color-text-primary, #2d2d2d); font-size: 11px; font-weight: 700; }
.topic-tag {
  margin-left: auto;
  color: var(--color-text-secondary, #909399);
  border: 1px solid var(--color-border, #ebeef5);
  border-radius: 3px;
  padding: 3px 5px;
  font-size: 8px;
}
.topic-card h5 { margin: 0 0 5px; color: var(--color-text-primary, #2d2d2d); font-size: 12.5px; line-height: 1.35; font-weight: 700; }
.topic-card p { margin: 0; color: var(--color-text-regular, #606266); font-size: 12px; line-height: 1.65; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.topic-section .topic-text-btn { align-self: flex-start; }
.action-board {
  overflow: hidden;
  border: 1px solid var(--color-border, #ebeef5);
  border-radius: 12px;
  background: var(--color-bg-card, #fff);
  padding: 15px 17px 13px;
}
.action-board .topic-section-head { margin: 0 0 11px; }
.action-columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; background: var(--color-border, #ebeef5); border: 1px solid var(--color-border, #ebeef5); border-radius: 8px; overflow: hidden; }
.action-column { background: var(--color-bg-card, #fff); padding: 12px 14px 13px; min-width: 0; }
.action-column-head { display: flex; align-items: baseline; justify-content: space-between; color: #2c6e63; font-size: 11px; font-weight: 700; margin-bottom: 8px; }
.action-column-head em { font-style: normal; color: var(--color-text-secondary, #909399); font-family: Consolas, monospace; font-size: 9px; font-weight: 400; }
.action-item { display: grid; grid-template-columns: 16px minmax(0, 1fr); gap: 6px; padding: 7px 0; border-top: 1px solid var(--color-border-light, #f0f0f0); color: var(--color-text-regular, #606266); font-size: 11px; line-height: 1.55; }
.action-item:first-of-type { border-top: 0; }
.action-item b { color: var(--color-primary, #ff7a5c); font-family: Consolas, monospace; font-size: 9px; font-weight: 400; padding-top: 1px; }
.action-more { padding-top: 7px; color: var(--color-text-secondary, #909399); font-size: 9px; }
.all-decisions { margin-top: 13px; padding-top: 12px; border-top: 1px solid var(--color-border, #ebeef5); display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 22px; }
.all-decision-who { display: flex; justify-content: space-between; color: #2c6e63; font-size: 10px; font-weight: 700; margin-bottom: 5px; }
.all-decision-who span { color: var(--color-text-secondary, #909399); font-family: Consolas, monospace; font-weight: 400; }
.all-decision-group ul { margin: 0; padding-left: 15px; color: var(--color-text-regular, #606266); }
.all-decision-group li { margin: 4px 0; font-size: 11px; line-height: 1.55; }
.topic-agenda { border-top: 1px solid var(--color-border, #ebeef5); padding-top: 10px; color: var(--color-text-regular, #606266); font-size: 11px; }
.topic-agenda summary { cursor: pointer; color: #2c6e63; font-weight: 600; }
.topic-board-foot { display: flex; justify-content: flex-end; padding-top: 2px; }
.topic-board-foot .edit-minutes-btn { margin: 0; }
@media (max-width: 1050px) {
  .topic-brief { grid-template-columns: 1fr; }
  .topic-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .action-columns { grid-template-columns: 1fr; }
  .all-decisions { grid-template-columns: 1fr; }
}
@media (max-width: 680px) {
  .topic-grid { grid-template-columns: 1fr; }
  .topic-brief-main { padding: 17px; }
  .topic-brief-main p { font-size: 14px; }
}


</style>

<style>
/* 配色④ 深色主题页面令牌 (非 scoped, 铁律 26) */
[data-theme="dark"] .meeting-detail {
  --color-text-primary: #e5ebe7;
  --color-text-regular: #c3cdc7;
  --color-text-secondary: #93a29b;
  --color-text-placeholder: #6d7f7a;
  --color-border: #2a3430;
  --color-border-light: #232c28;
  --color-info-bg: rgba(147, 162, 155, 0.12);
  --color-primary: #6fa39b;
  --color-primary-light: #85b8b1;
  --color-primary-dark: #4a7d75;
  --color-primary-bg: rgba(111, 163, 155, 0.14);
  --color-primary-border: rgba(111, 163, 155, 0.4);
  --color-accent: #6fa39b;
  --color-accent-bg: rgba(111, 163, 155, 0.14);
  --color-primary-strong: #3d6b64;
  --el-color-primary: #6fa39b;
  --el-color-primary-light-3: #558078;
  --el-color-primary-light-5: #40605b;
  --el-color-primary-light-7: #2e4742;
  --el-color-primary-light-8: #263a36;
  --el-color-primary-light-9: #1e2e2b;
  --el-color-primary-dark-2: #85b8b1;
}
/* 选型⑤ 融于卡片: 颜色全部走本页局部 token, 深色主题自动跟随, 只补轨道底色 */
[data-theme="dark"] .hp-track { background: rgba(255, 255, 255, 0.10); }
[data-theme="dark"] .hp-noaudio { border-color: rgba(255, 255, 255, 0.08); }
[data-theme="dark"] .transcript-ts.ts-seek { color: var(--raw-7fb3aa); }

/* 03 方案没有大块头像和返回条；保留播放器，但收成细条 */
body.meeting-topic-board .hero-back,
body.meeting-topic-board .hero-participants { display: none; }
body.meeting-topic-board .hero-actions { align-self: flex-end; }

/* Tab 从胶囊改成分隔线导航，接近 03 的简洁页头 */
body.meeting-topic-board .tab-strip {
  gap: 20px;
  padding: 0;
  border: 0;
  border-bottom: 1px solid #e5ded2;
  border-radius: 0;
  background: transparent;
}
body.meeting-topic-board .tab-strip__item {
  padding: 10px 0;
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  background: transparent;
  color: #817b70;
}
body.meeting-topic-board .tab-strip__item.is-active {
  background: transparent;
  color: #2c6e63;
  border-bottom-color: #2c6e63;
}
body.meeting-topic-board .tab-strip__no { color: #a8a096; }
body.meeting-topic-board .tab-strip__item.is-active .tab-strip__no { color: #2c6e63; }

</style>
