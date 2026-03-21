<template>
  <div ref="containerRef" class="aerial-container">
    <!-- 航拍背景图 -->
    <img
      v-if="backgroundSrc"
      :src="backgroundSrc"
      class="aerial-bg"
      @load="onImageLoad"
    />
    <div v-else class="aerial-placeholder">
      <el-icon :size="64" color="rgba(255,255,255,0.2)"><Camera /></el-icon>
      <span>上传航拍图或运行检测后显示</span>
    </div>

    <!-- 检测框叠加层 -->
    <canvas ref="overlayRef" class="overlay-canvas"></canvas>

    <!-- 热力点叠加 (简化版, 纯 CSS 径向渐变) -->
    <div
      v-for="(point, i) in heatPoints"
      :key="i"
      class="heat-point"
      :style="{
        left: point.x + '%',
        top: point.y + '%',
        background: `radial-gradient(circle, ${point.color}40 0%, transparent 70%)`,
        width: point.size + 'px',
        height: point.size + 'px',
      }"
    />

    <!-- 统计信息 HUD -->
    <div v-if="tracks.length > 0" class="aerial-hud">
      <div class="hud-item">{{ tracks.length }} 目标</div>
      <div v-if="fps > 0" class="hud-item">{{ fps.toFixed(1) }} FPS</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, type PropType } from 'vue'
import { Camera } from '@element-plus/icons-vue'
import { useDetectionStore } from '@/stores/detection'

const CLASS_COLORS: Record<number, string> = {
  0: '#3B82F6', // car
  1: '#EF4444', // truck
  2: '#10B981', // bus
  3: '#F59E0B', // van
  4: '#8B5CF6', // freight_car
}

const detectionStore = useDetectionStore()
const containerRef = ref<HTMLElement>()
const overlayRef = ref<HTMLCanvasElement>()
const backgroundSrc = ref('')
const imgNaturalW = ref(0)
const imgNaturalH = ref(0)

const tracks = computed(() => detectionStore.filteredTracks)
const fps = computed(() => detectionStore.fps)

// 热力点: 从检测结果生成
const heatPoints = computed(() => {
  return tracks.value.map(t => {
    const cx = ((t.bbox[0] + t.bbox[2]) / 2) * 100
    const cy = ((t.bbox[1] + t.bbox[3]) / 2) * 100
    const color = CLASS_COLORS[t.class_id] || '#0891b2'
    return { x: cx, y: cy, color, size: 40 }
  })
})

function onImageLoad(e: Event) {
  const img = e.target as HTMLImageElement
  imgNaturalW.value = img.naturalWidth
  imgNaturalH.value = img.naturalHeight
  drawOverlay()
}

function drawOverlay() {
  const canvas = overlayRef.value
  const container = containerRef.value
  if (!canvas || !container) return

  const rect = container.getBoundingClientRect()
  canvas.width = rect.width
  canvas.height = rect.height
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.clearRect(0, 0, canvas.width, canvas.height)

  for (const track of tracks.value) {
    const [x1, y1, x2, y2] = track.bbox
    const px = x1 * canvas.width
    const py = y1 * canvas.height
    const pw = (x2 - x1) * canvas.width
    const ph = (y2 - y1) * canvas.height
    const color = CLASS_COLORS[track.class_id] || '#0891b2'

    // 边框
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.strokeRect(px, py, pw, ph)

    // 标签背景
    const label = `${track.class_name} ${(track.confidence * 100).toFixed(0)}%`
    ctx.font = '11px "JetBrains Mono", monospace'
    const textW = ctx.measureText(label).width + 8
    ctx.fillStyle = color
    ctx.fillRect(px, py - 16, textW, 16)

    // 标签文字
    ctx.fillStyle = '#fff'
    ctx.fillText(label, px + 4, py - 4)

    // 底部中心点 (用于轨迹分析)
    const bcx = (x1 + x2) / 2 * canvas.width
    const bcy = y2 * canvas.height
    ctx.beginPath()
    ctx.arc(bcx, bcy, 3, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.fill()
  }
}

// 响应检测结果变化重绘
watch(tracks, drawOverlay, { deep: true })

// 响应窗口大小变化
let resizeObs: ResizeObserver | null = null
onMounted(() => {
  if (containerRef.value) {
    resizeObs = new ResizeObserver(drawOverlay)
    resizeObs.observe(containerRef.value)
  }

  // 如果有已检测的帧, 设置背景
  if (detectionStore.currentFrame) {
    backgroundSrc.value = detectionStore.currentFrame
  }
})

// 监听帧变化 (视频检测时)
watch(() => detectionStore.currentFrame, (src) => {
  if (src) backgroundSrc.value = src
})

onUnmounted(() => {
  resizeObs?.disconnect()
})

defineExpose({
  setBackground: (src: string) => { backgroundSrc.value = src },
})
</script>

<style scoped>
.aerial-container {
  position: relative;
  width: 100%;
  height: 100%;
  background: #0f172a;
  overflow: hidden;
}

.aerial-bg {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.aerial-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: rgba(255, 255, 255, 0.3);
  font-size: 14px;
}

.overlay-canvas {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.heat-point {
  position: absolute;
  transform: translate(-50%, -50%);
  pointer-events: none;
  border-radius: 50%;
}

.aerial-hud {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  gap: 8px;
  z-index: 10;
}

.hud-item {
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  backdrop-filter: blur(4px);
}
</style>
