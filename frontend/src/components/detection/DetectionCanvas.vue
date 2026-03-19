<template>
  <div class="ind-canvas-wrap" ref="wrapperRef">
    <canvas ref="canvasRef" class="det-canvas"></canvas>
    <div v-if="detectionStore.filteredTracks.length > 0" class="canvas-badge-tl">{{ detectionStore.filteredTracks.length }} 个目标</div>
    <div v-if="detectionStore.fps > 0" class="canvas-badge-tr">{{ detectionStore.fps.toFixed(1) }} FPS</div>
    <div v-if="!hasFrame" class="canvas-empty">
      <div class="empty-icon">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="3"/>
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
        </svg>
      </div>
      <p class="empty-title">等待检测输入</p>
      <p class="empty-sub">上传无人机图片/视频开始交通检测</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { useDetectionStore } from '@/stores/detection'
import { useDetectionCanvas } from '@/composables/useDetectionCanvas'
import type { Track } from '@/types'

const detectionStore = useDetectionStore()
const { canvasRef, drawDetections, resizeCanvas, captureCanvas } = useDetectionCanvas()
const wrapperRef = ref<HTMLDivElement | null>(null)
const hasFrame = computed(() => !!detectionStore.currentFrameBlob || !!detectionStore.currentFrame)

let renderInFlight = false
let pendingBlob: Blob | null = null
let pendingTracks: Track[] = []
let lastBitmap: ImageBitmap | null = null

function scheduleRender() {
  if (renderInFlight) return
  renderInFlight = true
  requestAnimationFrame(() => {
    const blob = pendingBlob
    const tracks = pendingTracks
    if (blob) {
      createImageBitmap(blob).then(bitmap => {
        if (lastBitmap) lastBitmap.close()
        lastBitmap = bitmap
        drawDetections(tracks, bitmap)
        renderInFlight = false
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
  if (!wrapperRef.value) return
  resizeCanvas(wrapperRef.value.clientWidth, wrapperRef.value.clientHeight)
  if (lastBitmap) drawDetections(detectionStore.filteredTracks, lastBitmap)
}

watch(
  () => [detectionStore.currentFrameBlob, detectionStore.filteredTracks] as const,
  ([blob, tracks]) => {
    pendingBlob = blob
    pendingTracks = tracks
    scheduleRender()
  }
)

let obs: ResizeObserver | null = null
onMounted(() => { handleResize(); obs = new ResizeObserver(handleResize); if (wrapperRef.value) obs.observe(wrapperRef.value) })
onUnmounted(() => obs?.disconnect())

defineExpose({ captureCanvas })
</script>

<style lang="scss" scoped>
.ind-canvas-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  background: #2a3142;
  border-radius: $radius-lg;
  border: 1px solid $border-color;
  overflow: hidden;
  box-shadow: $shadow-panel;
}
.det-canvas { display: block; width: 100%; height: 100%; }
.canvas-badge-tl, .canvas-badge-tr {
  position: absolute;
  top: 10px;
  font-family: $font-mono;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: $radius-sm;
  background: rgba(0, 0, 0, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.15);
  z-index: 5;
}
.canvas-badge-tl { left: 10px; color: #f59e0b; }
.canvas-badge-tr { right: 10px; color: #22c55e; }
.canvas-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.empty-icon {
  width: 72px; height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.35);
  border: 1px dashed rgba(255, 255, 255, 0.2);
  border-radius: $radius-lg;
}
.empty-title { font-size: 16px; font-weight: 600; color: rgba(255, 255, 255, 0.6); }
.empty-sub { font-size: 13px; color: rgba(255, 255, 255, 0.4); }
</style>
