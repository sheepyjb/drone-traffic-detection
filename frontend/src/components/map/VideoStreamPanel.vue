<template>
  <div class="video-panel" :class="{ minimized: isMinimized, expanded: isExpanded }">
    <!-- 标题栏 -->
    <div class="panel-header">
      <div class="header-left">
        <span class="status-dot" :class="detectionStore.isDetecting ? 'active' : 'idle'"></span>
        <span class="header-title">{{ isExpanded ? '全屏检测模式' : 'AR 视频流' }}</span>
        <el-tag v-if="detectionStore.isDetecting" type="success" size="small" effect="dark">LIVE</el-tag>
      </div>
      <div class="header-right">
        <el-button v-if="isExpanded" type="primary" size="small" @click="toggleExpand">
          返回地图
        </el-button>
        <el-button v-else link size="small" @click="toggleExpand">
          全屏检测
        </el-button>
        <el-button v-if="!isExpanded" link size="small" @click="isMinimized = !isMinimized">
          {{ isMinimized ? '展开' : '收起' }}
        </el-button>
      </div>
    </div>

    <!-- 内容区 -->
    <div v-show="!isMinimized" class="video-body">
      <div class="canvas-area">
        <div class="canvas-wrap" ref="wrapperRef">
          <canvas ref="canvasRef"></canvas>
          <div v-if="!hasFrame" class="canvas-empty">
            <el-icon :size="isExpanded ? 48 : 36" color="rgba(255,255,255,0.3)"><VideoCamera /></el-icon>
            <span>等待视频输入</span>
          </div>
          <!-- HUD -->
          <div v-if="hasFrame" class="hud-overlay">
            <div class="hud-tl">
              <span>{{ detectionStore.filteredTracks.length }} 目标</span>
            </div>
            <div class="hud-tr">
              <span v-if="detectionStore.fps > 0">{{ detectionStore.fps.toFixed(1) }} FPS</span>
              <span v-if="detectionStore.latency > 0">{{ detectionStore.latency }}ms</span>
            </div>
            <div class="hud-bl">
              <span v-for="line in flowCountStore.virtualLines" :key="line.id" class="line-badge" :style="{ borderColor: line.color }">
                {{ line.name }}: {{ getLineTotal(line.id) }}
              </span>
            </div>
          </div>
          <!-- 全屏模式浮动退出按钮 -->
          <div v-if="isExpanded" class="expand-exit-btn" @click="toggleExpand">
            <el-icon :size="16"><Close /></el-icon>
            <span>退出全屏</span>
          </div>
        </div>

        <!-- 控制条 -->
        <div class="control-bar">
          <div v-if="!detectionStore.isDetecting" class="upload-area" @click="fileInput?.click()" @dragover.prevent @drop.prevent="handleDrop">
            <el-icon :size="14"><UploadFilled /></el-icon>
            <span>{{ fileName || '上传视频/图片' }}</span>
            <input ref="fileInput" type="file" accept="video/mp4,video/avi,.mp4,.avi,.mov,image/jpeg,image/png,.jpg,.png" style="display:none" @change="handleFileChange" />
          </div>
          <div class="btn-group">
            <el-button v-if="!detectionStore.isDetecting" type="primary" size="small" :icon="VideoPlay" :disabled="!uploadedFile" @click="startDetection">检测</el-button>
            <el-button v-if="detectionStore.isDetecting" :type="detectionStore.paused ? 'success' : 'warning'" size="small" @click="detectionStore.toggleVideoDetection()">
              {{ detectionStore.paused ? '继续' : '暂停' }}
            </el-button>
            <el-button v-if="detectionStore.isDetecting" type="danger" size="small" :icon="Close" @click="detectionStore.stopVideoDetection()">停止</el-button>
          </div>
          <el-progress v-if="detectionStore.isDetecting" :percentage="Math.round(detectionStore.videoProgress)" :stroke-width="4" :show-text="false" class="progress-bar" />
        </div>
      </div>

      <!-- 全屏模式: 数据看板侧边栏（与地图监控右侧一致） -->
      <div v-if="isExpanded" class="stats-sidebar">
        <el-scrollbar>
          <!-- 指标卡 -->
          <MetricCards />

          <!-- 断面流量柱状图 -->
          <FlowBarChart />

          <!-- 车型构成环形图 -->
          <VehiclePieChart />

          <!-- 信号灯配时 -->
          <TrafficLightPanel />

          <!-- 转向分析 -->
          <TurnPieChart />

          <!-- 事件预警 -->
          <EventAlertPanel />

          <!-- 无人机参数 (折叠) -->
          <div class="param-section">
            <el-collapse>
              <el-collapse-item title="无人机参数" name="drone">
                <div class="param-grid">
                  <div class="param-item">
                    <label>纬度</label>
                    <el-input-number v-model="mapStore.droneParams.lat" :step="0.0001" :precision="4" size="small" controls-position="right" />
                  </div>
                  <div class="param-item">
                    <label>经度</label>
                    <el-input-number v-model="mapStore.droneParams.lng" :step="0.0001" :precision="4" size="small" controls-position="right" />
                  </div>
                  <div class="param-item">
                    <label>高度 (m)</label>
                    <el-input-number v-model="mapStore.droneParams.altitude" :min="10" :max="500" :step="10" size="small" controls-position="right" />
                  </div>
                  <div class="param-item">
                    <label>俯仰角</label>
                    <el-input-number v-model="mapStore.droneParams.pitch" :min="-90" :max="0" :step="5" size="small" controls-position="right" />
                  </div>
                  <div class="param-item">
                    <label>水平FOV</label>
                    <el-input-number v-model="mapStore.droneParams.hFov" :min="30" :max="120" :step="2" size="small" controls-position="right" />
                  </div>
                  <div class="param-item">
                    <label>垂直FOV</label>
                    <el-input-number v-model="mapStore.droneParams.vFov" :min="20" :max="90" :step="2" size="small" controls-position="right" />
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <!-- 操作按钮 -->
          <div class="action-section">
            <el-button type="success" size="small" @click="analyzeTraffic" :loading="analyzing">
              配时分析
            </el-button>
            <el-button type="warning" size="small" @click="exportReport">
              导出报告
            </el-button>
          </div>
        </el-scrollbar>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { VideoPlay, Close, UploadFilled, VideoCamera } from '@element-plus/icons-vue'
import { ElNotification } from 'element-plus'
import { useDetectionStore } from '@/stores/detection'
import { useDetectionCanvas } from '@/composables/useDetectionCanvas'
import { useFlowCountStore } from '@/stores/flowCount'
import { useMapStore } from '@/stores/map'
import type { Track } from '@/types'
// 全屏模式侧边栏组件（与地图监控右侧看板一致）
import MetricCards from '@/components/map/MetricCards.vue'
import FlowBarChart from '@/components/map/FlowBarChart.vue'
import VehiclePieChart from '@/components/map/VehiclePieChart.vue'
import TrafficLightPanel from '@/components/map/TrafficLightPanel.vue'
import TurnPieChart from '@/components/map/TurnPieChart.vue'
import EventAlertPanel from '@/components/map/EventAlertPanel.vue'

const detectionStore = useDetectionStore()
const flowCountStore = useFlowCountStore()
const mapStore = useMapStore()
const { canvasRef, drawDetections, resizeCanvas } = useDetectionCanvas()

const isMinimized = ref(false)
const isExpanded = ref(false)
const wrapperRef = ref<HTMLDivElement>()
const fileInput = ref<HTMLInputElement>()
const uploadedFile = ref<File | null>(null)
const fileName = ref('')
const analyzing = ref(false)
const hasFrame = computed(() => !!detectionStore.currentFrameBlob || !!detectionStore.currentFrame)

const ANALYTICS_INTERVAL_MS = 100
let analyticsTimer: ReturnType<typeof setTimeout> | null = null
let lastAnalyticsAt = 0
let pendingAnalysisTracks: Track[] = []
let pendingAnalysisFps = 0

function getLineTotal(lineId: string): number {
  const c = flowCountStore.lineCounts[lineId]
  return c ? c.positive + c.negative : 0
}

function toggleExpand() {
  isExpanded.value = !isExpanded.value
  if (isExpanded.value) isMinimized.value = false
  // 等布局计算完成后再 resize canvas（双 nextTick 确保 DOM 更新 + flex 重算）
  nextTick(() => {
    nextTick(() => handleResize())
  })
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isExpanded.value) {
    isExpanded.value = false
    nextTick(() => handleResize())
  }
}

function handleFileChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) { uploadedFile.value = f; fileName.value = f.name }
}
function handleDrop(e: DragEvent) {
  const f = e.dataTransfer?.files[0]
  if (f) { uploadedFile.value = f; fileName.value = f.name }
}
async function startDetection() {
  if (!uploadedFile.value) return
  flowCountStore.reset()
  await detectionStore.startVideoDetection(uploadedFile.value, 0.25)
}

// ===== 配时分析 & 导出报告（与 MapView 一致） =====
async function analyzeTraffic() {
  if (mapStore.mappedVehicles.length === 0) {
    ElNotification({ title: '提示', message: '暂无检测数据，请先运行检测', type: 'warning', duration: 3000 })
    return
  }
  analyzing.value = true
  try {
    await mapStore.analyzeTraffic()
    ElNotification({ title: '配时分析完成', message: '信号灯策略已生成', type: 'success', duration: 2000 })
  } finally {
    analyzing.value = false
  }
}

function exportReport() {
  const fc = flowCountStore
  const s = mapStore.trafficLightState
  const p = mapStore.droneParams

  let text = '=== 无人机智慧交通检测报告 ===\n\n'
  text += `生成时间: ${new Date().toLocaleString()}\n`
  text += `模型: YOLO26 | 数据集: DroneVehicle\n\n`
  text += `--- 无人机参数 ---\n`
  text += `位置: (${p.lat}, ${p.lng}) | 高度: ${p.altitude}m\n`
  text += `FOV: ${p.hFov}° x ${p.vFov}°\n\n`
  text += `--- 虚拟线圈流量统计 ---\n`
  text += `累计过线车辆: ${fc.totalCrossed}\n`
  text += `北侧: ${fc.directionSummary.north} | 南侧: ${fc.directionSummary.south} | 西侧: ${fc.directionSummary.west} | 东侧: ${fc.directionSummary.east}\n`
  text += `车型分布:\n`
  const labels: Record<number, string> = { 0: '小汽车', 1: '货车', 2: '大巴', 3: '厢式货车', 4: '货运车' }
  for (const [k, v] of Object.entries(fc.classCounts)) {
    if (v > 0) text += `  ${labels[Number(k)] || k}: ${v}\n`
  }
  text += '\n'

  text += `--- 交通拥堵评价 ---\n`
  text += `最大排队长度: ${fc.maxQueueLength}m\n`
  text += `平均延误: ${fc.avgDelay}s\n`
  text += `平均占有率: ${fc.avgOccupancy}%\n`
  text += `服务水平: ${fc.serviceLevelGrade}\n\n`

  if (fc.turns.length > 0) {
    text += `--- 转向分析 ---\n`
    text += `总转向记录: ${fc.turns.length}\n`
    const ts = fc.turnSummary
    for (const dir of ['south', 'north', 'west', 'east'] as const) {
      const dirLabel: Record<string, string> = { south: '南进', north: '北进', west: '西进', east: '东进' }
      const ds = ts[dir]
      const total = ds.straight + ds.left + ds.right + ds.uturn
      if (total > 0) {
        text += `  ${dirLabel[dir]}: 直行${ds.straight} 左转${ds.left} 右转${ds.right} 掉头${ds.uturn}\n`
      }
    }
    text += '\n'
  }

  if (fc.trafficEvents.length > 0) {
    text += `--- 事件预警记录 ---\n`
    for (const evt of fc.trafficEvents.slice(0, 20)) {
      text += `  [${new Date(evt.timestamp).toLocaleTimeString()}] ${evt.message}\n`
    }
    text += '\n'
  }

  if (s) {
    text += `--- 配时策略 ---\n${s.report}\n\n`
  }

  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `traffic_report_${Date.now()}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

// ===== 渲染（createImageBitmap 高性能模式，JPEG 解码在后台线程） =====
let renderInFlight = false
let pendingBlob: Blob | null = null
let pendingTracks: Track[] = []

function flushAnalytics() {
  analyticsTimer = null
  lastAnalyticsAt = Date.now()
  flowCountStore.processFrame(pendingAnalysisTracks, pendingAnalysisFps)
}

function scheduleAnalytics() {
  const delay = ANALYTICS_INTERVAL_MS - (Date.now() - lastAnalyticsAt)
  if (delay <= 0) {
    flushAnalytics()
    return
  }
  if (analyticsTimer) return
  analyticsTimer = setTimeout(() => {
    flushAnalytics()
  }, delay)
}

function drawVirtualLines() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const w = canvas.width, h = canvas.height
  for (const line of flowCountStore.virtualLines) {
    const sx = line.start.x * w, sy = line.start.y * h
    const ex = line.end.x * w, ey = line.end.y * h
    ctx.save()
    ctx.strokeStyle = line.color
    ctx.lineWidth = 2
    ctx.setLineDash([10, 5])
    ctx.beginPath()
    ctx.moveTo(sx, sy)
    ctx.lineTo(ex, ey)
    ctx.stroke()
    ctx.setLineDash([])

    const total = getLineTotal(line.id)
    const labelText = `${line.name} ${total}`
    ctx.font = '600 12px Inter, Microsoft YaHei, sans-serif'
    const tw = ctx.measureText(labelText).width
    const lx = (sx + ex) / 2 - tw / 2 - 2
    const ly = (sy + ey) / 2 - 8
    ctx.fillStyle = 'rgba(0,0,0,0.7)'
    ctx.beginPath()
    ctx.roundRect(lx, ly, tw + 8, 16, 3)
    ctx.fill()
    ctx.fillStyle = line.color
    ctx.fillText(labelText, lx + 4, ly + 12)
    ctx.restore()
  }
}

function scheduleRender() {
  if (renderInFlight) return
  renderInFlight = true
  requestAnimationFrame(() => {
    const blob = pendingBlob
    const tracks = pendingTracks
    if (blob) {
      createImageBitmap(blob).then(bitmap => {
        drawDetections(tracks, bitmap)
        drawVirtualLines()
        bitmap.close()
        renderInFlight = false
        // 解码期间有新帧到达，继续渲染
        if (pendingBlob !== blob) scheduleRender()
      }).catch(() => {
        renderInFlight = false
      })
    } else {
      drawDetections(tracks)
      renderInFlight = false
    }
  })
}

function handleResize() {
  const wrapper = wrapperRef.value
  if (!wrapper) return
  resizeCanvas(wrapper.clientWidth, wrapper.clientHeight)
  // resize 后立即用当前数据重绘
  pendingBlob = detectionStore.currentFrameBlob
  pendingTracks = detectionStore.filteredTracks
  scheduleRender()
}

// 监听帧更新 — 使用 Blob 进行 createImageBitmap 解码（非主线程）
watch(
  () => [detectionStore.currentFrameBlob, detectionStore.filteredTracks] as const,
  ([blob, tracks]) => {
    pendingBlob = blob
    pendingTracks = tracks
    scheduleRender()
  }
)

watch(
  () => detectionStore.frameId,
  (frameId) => {
    if (frameId <= 0) return
    pendingAnalysisTracks = detectionStore.tracks
    pendingAnalysisFps = detectionStore.fps
    scheduleAnalytics()
  }
)

let obs: ResizeObserver | null = null
onMounted(() => {
  handleResize()
  obs = new ResizeObserver(handleResize)
  if (wrapperRef.value) obs.observe(wrapperRef.value)
  document.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
  if (analyticsTimer) clearTimeout(analyticsTimer)
  obs?.disconnect()
  document.removeEventListener('keydown', onKeyDown)
})
</script>

<style lang="scss" scoped>
.video-panel {
  position: absolute;
  top: 12px;
  left: 12px;
  width: 560px;
  background: rgba(255, 255, 255, 0.97);
  border-radius: 12px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.18);
  z-index: 200;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);

  &.minimized { width: 200px; }

  &.expanded {
    position: fixed;
    inset: 0;
    width: 100% !important;
    height: 100%;
    z-index: 9999;
    border-radius: 0;
    display: flex;
    flex-direction: column;
    overflow: visible;

    .panel-header {
      padding: 10px 16px;
      background: #fff;
      border-bottom: 1px solid rgba(0, 0, 0, 0.1);
      flex-shrink: 0;
    }

    .header-title {
      font-size: 15px;
    }
  }
}

// 全屏模式内部布局
.video-panel.expanded .video-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.video-panel.expanded .canvas-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.video-panel.expanded .canvas-wrap {
  flex: 1;
  height: 0 !important;
  min-height: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: rgba(0, 0, 0, 0.03);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
.header-left { display: flex; align-items: center; gap: 6px; }
.header-right { display: flex; align-items: center; gap: 4px; }
.header-title { font-size: 13px; font-weight: 700; color: #1e293b; }

.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  &.active {
    background: #22c55e;
    box-shadow: 0 0 6px rgba(34,197,94,0.6);
    animation: pulse 1.5s infinite;
  }
  &.idle { background: #94a3b8; }
}

.canvas-wrap {
  position: relative;
  width: 100%;
  height: 360px;
  background: #1a1f2e;

  canvas { display: block; width: 100%; height: 100%; }
}

.canvas-empty {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; color: rgba(255,255,255,0.3); font-size: 13px;
}

// HUD 覆盖
.hud-overlay { position: absolute; inset: 0; pointer-events: none; }
.hud-tl, .hud-tr {
  position: absolute; top: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px; font-weight: 600;
  display: flex; gap: 6px;
  span {
    background: rgba(0,0,0,0.65); padding: 3px 10px;
    border-radius: 4px; color: #f59e0b;
  }
}
.hud-tl { left: 8px; }
.hud-tr { right: 8px; span { color: #22c55e; } }
.hud-bl {
  position: absolute; bottom: 8px; left: 8px;
  display: flex; flex-wrap: wrap; gap: 4px;
}
.line-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px; font-weight: 600;
  background: rgba(0,0,0,0.7); padding: 2px 8px;
  border-radius: 4px; color: #e2e8f0; border-left: 3px solid;
}

.control-bar {
  padding: 8px 10px;
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
}
.upload-area {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 10px;
  background: rgba(0,0,0,0.03); border: 1px dashed rgba(0,0,0,0.15);
  border-radius: 6px; cursor: pointer; font-size: 12px; color: #64748b;
  flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  &:hover { border-color: #0891b2; color: #0891b2; }
}
.btn-group { display: flex; gap: 4px; }
.progress-bar { width: 100%; }

// 全屏模式浮动退出按钮
.expand-exit-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: rgba(239, 68, 68, 0.9);
  color: #fff;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
  transition: all 0.2s;
  pointer-events: auto;

  &:hover {
    background: rgba(239, 68, 68, 1);
    transform: scale(1.05);
  }
}

// 全屏模式侧边栏
.stats-sidebar {
  width: 320px;
  flex-shrink: 0;
  border-left: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.97);
  overflow: hidden;
}

// 无人机参数（侧边栏内）
.param-section {
  padding: 4px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.param-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 3px;

  label {
    font-size: 10px;
    color: #94a3b8;
    font-weight: 500;
  }

  :deep(.el-input-number) { width: 100%; }
}

.action-section {
  padding: 12px;
  display: flex;
  gap: 8px;
}

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
</style>
