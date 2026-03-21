<template>
  <div class="command-center">
    <!-- ===== 全屏航拍检测 (视频帧 = 背景) ===== -->
    <div class="aerial-layer">
      <div class="canvas-wrap" ref="wrapperRef">
        <canvas ref="canvasRef"></canvas>
        <!-- 空状态 -->
        <div v-if="!hasFrame" class="empty-state">
          <div class="empty-icon">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L8 6H4V10L2 12L4 14V18H8L12 22L16 18H20V14L22 12L20 10V6H16L12 2Z" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
              <circle cx="12" cy="12" r="3" fill="rgba(255,255,255,0.15)"/>
            </svg>
          </div>
          <div class="empty-text">上传视频开始交通态势分析</div>
          <div class="upload-btn" @click="fileInput?.click()">
            <el-icon><UploadFilled /></el-icon>
            <span>选择视频/图片</span>
          </div>
          <input ref="fileInput" type="file" accept="video/mp4,video/avi,.mp4,.avi,.mov,image/jpeg,image/png,.jpg,.png" style="display:none" @change="handleFileChange" />
        </div>

        <!-- HUD 叠加 -->
        <div v-if="hasFrame" class="hud-overlay">
          <!-- 左上: 目标数 -->
          <div class="hud-tl">
            <span class="hud-badge primary">{{ detectionStore.filteredTracks.length }} 目标</span>
          </div>
          <!-- 右上: 性能 -->
          <div class="hud-tr">
            <span v-if="detectionStore.fps > 0" class="hud-badge success">{{ detectionStore.fps.toFixed(1) }} FPS</span>
            <span v-if="detectionStore.latency > 0" class="hud-badge">{{ detectionStore.latency }}ms</span>
          </div>
          <!-- 左下: 虚拟线计数 -->
          <div class="hud-bl">
            <span v-for="line in flowCountStore.virtualLines" :key="line.id" class="line-badge" :style="{ borderColor: line.color }">
              {{ line.name }}: {{ getLineTotal(line.id) }}
            </span>
          </div>
          <!-- 右下: 图层开关 -->
          <div class="hud-br">
            <label class="layer-toggle" :class="{ active: showTrajectory }">
              <input type="checkbox" v-model="showTrajectory" /> 轨迹
            </label>
            <label class="layer-toggle" :class="{ active: showHeatmap }">
              <input type="checkbox" v-model="showHeatmap" /> 热力
            </label>
            <label class="layer-toggle" :class="{ active: showLines }">
              <input type="checkbox" v-model="showLines" /> 线圈
            </label>
          </div>
        </div>
      </div>

      <!-- 底部控制条 -->
      <div class="control-bar">
        <div v-if="!detectionStore.isDetecting && hasFrame" class="upload-area-sm" @click="fileInput2?.click()">
          <el-icon><UploadFilled /></el-icon>
          <span>{{ fileName || '更换文件' }}</span>
          <input ref="fileInput2" type="file" accept="video/mp4,video/avi,.mp4,.avi,.mov,image/jpeg,image/png,.jpg,.png" style="display:none" @change="handleFileChange" />
        </div>
        <div v-if="!detectionStore.isDetecting && !hasFrame && uploadedFile" class="file-info">
          {{ fileName }}
        </div>
        <div class="btn-group">
          <el-button v-if="!detectionStore.isDetecting && uploadedFile" type="primary" size="small" @click="startDetection">开始检测</el-button>
          <el-button v-if="detectionStore.isDetecting" :type="detectionStore.paused ? 'success' : 'warning'" size="small" @click="detectionStore.toggleVideoDetection()">
            {{ detectionStore.paused ? '继续' : '暂停' }}
          </el-button>
          <el-button v-if="detectionStore.isDetecting" type="danger" size="small" @click="detectionStore.stopVideoDetection()">停止</el-button>
        </div>
        <el-progress v-if="detectionStore.isDetecting" :percentage="Math.round(detectionStore.videoProgress)" :stroke-width="4" :show-text="false" class="progress-bar" />
        <div class="control-spacer"></div>
        <div class="status-info">
          <span class="status-dot" :class="detectionStore.isDetecting ? 'active' : ''"></span>
          {{ detectionStore.isDetecting ? 'LIVE' : '待机' }}
        </div>
      </div>
    </div>

    <!-- ===== 右侧数据看板 ===== -->
    <div class="dashboard-panel" :class="{ collapsed: dashCollapsed }">
      <div class="dash-toggle" @click="dashCollapsed = !dashCollapsed">
        {{ dashCollapsed ? '&#9664;' : '&#9654;' }}
      </div>
      <div v-show="!dashCollapsed" class="dash-content">
        <el-scrollbar>
          <MetricCards />
          <FlowBarChart />
          <VehiclePieChart />
          <TrafficLightPanel />
          <TurnPieChart />
          <EventAlertPanel />
          <div class="action-section">
            <el-button type="success" size="small" @click="analyzeTraffic" :loading="analyzing">配时分析</el-button>
            <el-button type="warning" size="small" @click="exportReport">导出报告</el-button>
          </div>
        </el-scrollbar>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElNotification } from 'element-plus'
import { useDetectionStore } from '@/stores/detection'
import { useDetectionCanvas } from '@/composables/useDetectionCanvas'
import { useFlowCountStore } from '@/stores/flowCount'
import { useMapStore } from '@/stores/map'
import type { Track } from '@/types'
import MetricCards from '@/components/map/MetricCards.vue'
import FlowBarChart from '@/components/map/FlowBarChart.vue'
import VehiclePieChart from '@/components/map/VehiclePieChart.vue'
import TrafficLightPanel from '@/components/map/TrafficLightPanel.vue'
import TurnPieChart from '@/components/map/TurnPieChart.vue'
import EventAlertPanel from '@/components/map/EventAlertPanel.vue'

const CLASS_COLORS: Record<number, string> = {
  0: '#3B82F6', 1: '#EF4444', 2: '#10B981', 3: '#F59E0B', 4: '#8B5CF6',
}

const detectionStore = useDetectionStore()
const flowCountStore = useFlowCountStore()
const mapStore = useMapStore()
const { canvasRef, drawDetections, resizeCanvas } = useDetectionCanvas()

const wrapperRef = ref<HTMLDivElement>()
const fileInput = ref<HTMLInputElement>()
const fileInput2 = ref<HTMLInputElement>()
const uploadedFile = ref<File | null>(null)
const fileName = ref('')
const analyzing = ref(false)
const dashCollapsed = ref(false)

const showTrajectory = ref(true)
const showHeatmap = ref(false)
const showLines = ref(true)

const hasFrame = computed(() => !!detectionStore.currentFrameBlob || !!detectionStore.currentFrame)

// ===== 轨迹历史 =====
const trajectoryHistory = ref<Map<number, Array<{x: number, y: number}>>>(new Map())
const MAX_TRAIL_LENGTH = 30

function updateTrajectories(tracks: Track[]) {
  for (const t of tracks) {
    const id = t.track_id ?? -1
    if (id < 0) continue
    const cx = (t.bbox[0] + t.bbox[2]) / 2
    const cy = t.bbox[3]  // 底部中心
    let trail = trajectoryHistory.value.get(id)
    if (!trail) {
      trail = []
      trajectoryHistory.value.set(id, trail)
    }
    trail.push({ x: cx, y: cy })
    if (trail.length > MAX_TRAIL_LENGTH) trail.shift()
  }
  // 清除已消失的 track
  const activeIds = new Set(tracks.map(t => t.track_id ?? -1))
  for (const id of trajectoryHistory.value.keys()) {
    if (!activeIds.has(id)) trajectoryHistory.value.delete(id)
  }
}

// ===== 叠加层绘制 =====
function drawOverlays() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const w = canvas.width, h = canvas.height

  // 轨迹
  if (showTrajectory.value) {
    for (const [trackId, trail] of trajectoryHistory.value) {
      if (trail.length < 2) continue
      // 找对应 track 的颜色
      const track = detectionStore.filteredTracks.find(t => t.track_id === trackId)
      const color = CLASS_COLORS[track?.class_id ?? 0] || '#0891b2'

      ctx.beginPath()
      ctx.moveTo(trail[0].x * w, trail[0].y * h)
      for (let i = 1; i < trail.length; i++) {
        ctx.lineTo(trail[i].x * w, trail[i].y * h)
      }
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.globalAlpha = 0.6
      ctx.stroke()

      // 渐变尾迹点
      for (let i = 0; i < trail.length; i++) {
        const alpha = (i / trail.length) * 0.8
        const r = 1.5 + (i / trail.length) * 2
        ctx.beginPath()
        ctx.arc(trail[i].x * w, trail[i].y * h, r, 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.globalAlpha = alpha
        ctx.fill()
      }
      ctx.globalAlpha = 1
    }
  }

  // 热力
  if (showHeatmap.value) {
    for (const t of detectionStore.filteredTracks) {
      const cx = ((t.bbox[0] + t.bbox[2]) / 2) * w
      const cy = ((t.bbox[1] + t.bbox[3]) / 2) * h
      const color = CLASS_COLORS[t.class_id] || '#0891b2'
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 30)
      grad.addColorStop(0, color + '40')
      grad.addColorStop(1, 'transparent')
      ctx.fillStyle = grad
      ctx.fillRect(cx - 30, cy - 30, 60, 60)
    }
  }

  // 虚拟线
  if (showLines.value) {
    drawVirtualLines(ctx, w, h)
  }
}

function drawVirtualLines(ctx: CanvasRenderingContext2D, w: number, h: number) {
  for (const line of flowCountStore.virtualLines) {
    const isH = line.orientation === 'horizontal'
    ctx.save()
    ctx.strokeStyle = line.color
    ctx.lineWidth = 2
    ctx.setLineDash([10, 5])
    ctx.beginPath()
    if (isH) {
      ctx.moveTo(0, line.position * h)
      ctx.lineTo(w, line.position * h)
    } else {
      ctx.moveTo(line.position * w, 0)
      ctx.lineTo(line.position * w, h)
    }
    ctx.stroke()
    ctx.setLineDash([])

    const total = getLineTotal(line.id)
    const label = `${line.name} ${total}`
    ctx.font = '600 12px Inter, sans-serif'
    const tw = ctx.measureText(label).width
    const lx = isH ? 6 : line.position * w + 4
    const ly = isH ? line.position * h - 6 : 16
    ctx.fillStyle = 'rgba(0,0,0,0.7)'
    ctx.beginPath()
    ctx.roundRect(lx - 2, ly - 12, tw + 8, 16, 3)
    ctx.fill()
    ctx.fillStyle = line.color
    ctx.fillText(label, lx + 2, ly)
    ctx.restore()
  }
}

function getLineTotal(lineId: string): number {
  const c = flowCountStore.lineCounts[lineId]
  return c ? c.positive + c.negative : 0
}

// ===== 渲染管线 =====
let renderInFlight = false
let pendingBlob: Blob | null = null
let pendingTracks: Track[] = []

const ANALYTICS_INTERVAL_MS = 100
let analyticsTimer: ReturnType<typeof setTimeout> | null = null
let lastAnalyticsAt = 0

function scheduleRender() {
  if (renderInFlight) return
  renderInFlight = true
  requestAnimationFrame(() => {
    const blob = pendingBlob
    const tracks = pendingTracks
    updateTrajectories(tracks)
    if (blob) {
      createImageBitmap(blob).then(bitmap => {
        drawDetections(tracks, bitmap)
        drawOverlays()
        bitmap.close()
        renderInFlight = false
        if (pendingBlob !== blob) scheduleRender()
      }).catch(() => { renderInFlight = false })
    } else {
      drawDetections(tracks)
      drawOverlays()
      renderInFlight = false
    }
  })
}

function handleResize() {
  const wrapper = wrapperRef.value
  if (!wrapper) return
  resizeCanvas(wrapper.clientWidth, wrapper.clientHeight)
  pendingBlob = detectionStore.currentFrameBlob
  pendingTracks = detectionStore.filteredTracks
  scheduleRender()
}

// ===== 文件上传 =====
function handleFileChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) { uploadedFile.value = f; fileName.value = f.name }
}

function startDetection() {
  if (!uploadedFile.value) return
  flowCountStore.reset()
  trajectoryHistory.value.clear()
  detectionStore.startVideoDetection(uploadedFile.value, 0.25)
}

// ===== 配时 & 导出 =====
async function analyzeTraffic() {
  if (mapStore.mappedVehicles.length === 0) {
    ElNotification({ title: '提示', message: '暂无检测数据', type: 'warning', duration: 3000 })
    return
  }
  analyzing.value = true
  try {
    await mapStore.analyzeTraffic()
    ElNotification({ title: '配时分析完成', type: 'success', duration: 2000 })
  } finally { analyzing.value = false }
}

function exportReport() {
  const fc = flowCountStore
  const s = mapStore.trafficLightState
  let text = '=== 无人机交通态势分析报告 ===\n\n'
  text += `生成时间: ${new Date().toLocaleString()}\n`
  text += `模型: YOLO26 | 数据集: DroneVehicle\n\n`
  text += `--- 车流统计 ---\n`
  text += `累计过线: ${fc.totalCrossed}\n`
  text += `北:${fc.directionSummary.north} 南:${fc.directionSummary.south} 西:${fc.directionSummary.west} 东:${fc.directionSummary.east}\n\n`
  text += `--- 拥堵评价 ---\n`
  text += `排队: ${fc.maxQueueLength}m | 延误: ${fc.avgDelay}s | 占有率: ${fc.avgOccupancy}% | LOS: ${fc.serviceLevelGrade}\n\n`
  if (s) text += `--- 配时策略 ---\n${s.report}\n`
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = `traffic_report_${Date.now()}.txt`; a.click()
  URL.revokeObjectURL(url)
}

// ===== 监听 =====
watch(
  () => [detectionStore.currentFrameBlob, detectionStore.filteredTracks] as const,
  ([blob, tracks]) => { pendingBlob = blob; pendingTracks = tracks; scheduleRender() }
)

watch(() => detectionStore.frameId, (fid) => {
  if (fid <= 0) return
  const now = Date.now()
  if (now - lastAnalyticsAt >= ANALYTICS_INTERVAL_MS) {
    lastAnalyticsAt = now
    flowCountStore.processFrame(detectionStore.tracks, detectionStore.fps)
  } else if (!analyticsTimer) {
    analyticsTimer = setTimeout(() => {
      analyticsTimer = null
      lastAnalyticsAt = Date.now()
      flowCountStore.processFrame(detectionStore.tracks, detectionStore.fps)
    }, ANALYTICS_INTERVAL_MS - (now - lastAnalyticsAt))
  }
})

let obs: ResizeObserver | null = null
onMounted(() => {
  handleResize()
  obs = new ResizeObserver(handleResize)
  if (wrapperRef.value) obs.observe(wrapperRef.value)
})
onUnmounted(() => {
  if (analyticsTimer) clearTimeout(analyticsTimer)
  obs?.disconnect()
})
</script>

<style lang="scss" scoped>
.command-center {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  overflow: hidden;
  background: #0f172a;
}

.aerial-layer {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.canvas-wrap {
  flex: 1;
  position: relative;
  background: #0f172a;
  canvas { display: block; width: 100%; height: 100%; }
}

// ===== 空状态 =====
.empty-state {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 16px;
}
.empty-text { color: rgba(255,255,255,0.3); font-size: 15px; }
.upload-btn {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 24px; border-radius: 8px;
  background: rgba(8, 145, 178, 0.15); border: 1px dashed rgba(8, 145, 178, 0.4);
  color: #0891b2; font-size: 14px; cursor: pointer;
  transition: all 0.2s;
  &:hover { background: rgba(8, 145, 178, 0.25); border-color: #0891b2; }
}

// ===== HUD =====
.hud-overlay { position: absolute; inset: 0; pointer-events: none; }
.hud-tl, .hud-tr, .hud-bl, .hud-br {
  position: absolute;
  display: flex; gap: 6px;
  font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600;
}
.hud-tl { top: 12px; left: 12px; }
.hud-tr { top: 12px; right: 12px; }
.hud-bl { bottom: 12px; left: 12px; flex-wrap: wrap; }
.hud-br { bottom: 12px; right: 12px; pointer-events: auto; }

.hud-badge {
  background: rgba(0,0,0,0.65); padding: 4px 12px;
  border-radius: 4px; color: #e2e8f0; backdrop-filter: blur(4px);
  &.primary { color: #f59e0b; }
  &.success { color: #22c55e; }
}

.line-badge {
  font-size: 10px; background: rgba(0,0,0,0.7); padding: 2px 8px;
  border-radius: 4px; color: #e2e8f0; border-left: 3px solid;
}

.layer-toggle {
  pointer-events: auto; cursor: pointer;
  background: rgba(0,0,0,0.5); padding: 3px 10px; border-radius: 4px;
  color: rgba(255,255,255,0.5); font-size: 11px; user-select: none;
  transition: all 0.15s;
  input { display: none; }
  &.active { background: rgba(8,145,178,0.6); color: #fff; }
  &:hover { background: rgba(8,145,178,0.4); color: #fff; }
}

// ===== 控制条 =====
.control-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; background: rgba(255,255,255,0.97);
  border-top: 1px solid rgba(0,0,0,0.06);
}
.upload-area-sm {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 10px; background: rgba(0,0,0,0.03); border: 1px dashed rgba(0,0,0,0.15);
  border-radius: 6px; cursor: pointer; font-size: 12px; color: #64748b;
  &:hover { border-color: #0891b2; color: #0891b2; }
}
.file-info { font-size: 12px; color: #64748b; }
.btn-group { display: flex; gap: 4px; }
.progress-bar { flex: 1; min-width: 80px; }
.control-spacer { flex: 1; }
.status-info {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px; color: #64748b; font-family: 'JetBrains Mono', monospace;
}
.status-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #94a3b8;
  &.active { background: #22c55e; box-shadow: 0 0 4px rgba(34,197,94,0.6); animation: blink 1.5s infinite; }
}

// ===== 右侧看板 =====
.dashboard-panel {
  width: 320px; flex-shrink: 0;
  background: rgba(255,255,255,0.97);
  border-left: 1px solid rgba(0,0,0,0.08);
  display: flex; position: relative;
  transition: width 0.3s ease;
  &.collapsed { width: 0; .dash-content { display: none; } }
}
.dash-toggle {
  position: absolute; left: -24px; top: 50%; transform: translateY(-50%);
  width: 24px; height: 48px; background: rgba(255,255,255,0.95);
  border: 1px solid rgba(0,0,0,0.08); border-right: none;
  border-radius: 6px 0 0 6px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; font-size: 10px; color: #94a3b8; z-index: 10;
  &:hover { color: #0891b2; }
}
.dash-content { flex: 1; overflow: hidden; }
.action-section { padding: 12px; display: flex; gap: 8px; }

@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.4} }
</style>
