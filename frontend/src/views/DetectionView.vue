<template>
  <div class="detection-view">
    <div class="detection-main">
      <div class="video-area">
        <div class="video-wrapper"><DetectionCanvas ref="canvasComp" /></div>
        <VideoControls :progress="detectionStore.videoProgress" :current-time="detectionStore.videoCurrentTime" :duration="detectionStore.videoDuration" :playing="detectionStore.isDetecting && !detectionStore.paused" @stop="stopDetection" @toggle-play="toggleDetection" @seek="handleSeek" />
      </div>
      <div class="stats-area">
        <div class="clay-card param-card">
          <div class="section-label">参数设置</div>
          <div class="param-row">
            <span class="param-name">置信度</span>
            <el-slider v-model="confThreshold" :min="0.05" :max="0.95" :step="0.05" size="small" />
            <span class="param-val mono">{{ confThreshold.toFixed(2) }}</span>
          </div>
          <div class="param-row">
            <span class="param-name">IoU</span>
            <el-slider v-model="iouThreshold" :min="0.1" :max="0.9" :step="0.05" size="small" />
            <span class="param-val mono">{{ iouThreshold.toFixed(2) }}</span>
          </div>
        </div>
        <PerformanceInfo />
        <ObjectCounter />
        <CategoryPieChart />
      </div>
    </div>
    <div class="action-bar clay-card">
      <VideoUpload :label="appStore.isFusionModel ? '可见光图像 (RGB)' : '拖拽或点击上传'" @upload="handleUpload" />
      <VideoUpload v-if="appStore.isFusionModel" label="红外图像 (IR)" accept="image/jpeg,image/png,.jpg,.png" @upload="handleUploadIr" />
      <div class="action-btns">
        <button class="clay-btn primary" @click="startDetection" :disabled="detectionStore.isDetecting"><el-icon><VideoPlay /></el-icon>开始检测</button>
        <button class="clay-btn" @click="stopDetection" :disabled="!detectionStore.isDetecting"><el-icon><VideoPause /></el-icon>停止</button>
        <button class="clay-btn" @click="saveImage" :disabled="!detectionStore.currentFrame"><el-icon><PictureFilled /></el-icon>保存图片</button>
        <button class="clay-btn" @click="exportCSV" :disabled="detectionStore.tracks.length===0"><el-icon><Download /></el-icon>导出CSV</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, VideoPause, Download, PictureFilled } from '@element-plus/icons-vue'
import DetectionCanvas from '@/components/detection/DetectionCanvas.vue'
import VideoControls from '@/components/detection/VideoControls.vue'
import VideoUpload from '@/components/detection/VideoUpload.vue'
import PerformanceInfo from '@/components/stats/PerformanceInfo.vue'
import ObjectCounter from '@/components/stats/ObjectCounter.vue'
import CategoryPieChart from '@/components/stats/CategoryPieChart.vue'
import { useDetectionStore } from '@/stores/detection'
import { useAppStore } from '@/stores/app'
import type { Track } from '@/types'

const detectionStore = useDetectionStore()
const appStore = useAppStore()
const canvasComp = ref<InstanceType<typeof DetectionCanvas> | null>(null)
const confThreshold = ref(0.25)
const iouThreshold = ref(0.45)
const uploadedFile = ref<File | null>(null)
const uploadedIrFile = ref<File | null>(null)

function exportCSV() {
  const t = detectionStore.tracks; if (!t.length) return
  const ts = new Date().toISOString().replace(/[:.]/g, '-')
  const header = 'ID,类别ID,类别名称,置信度,X1,Y1,X2,Y2\n'
  const rows = t.map(x => {
    return [
      x.track_id, x.class_id, x.class_name, x.confidence.toFixed(3),
      ...x.bbox.map(v => v.toFixed(4)),
    ].join(',')
  }).join('\n')
  const bom = '\uFEFF'
  const b = new Blob([bom + header + rows], { type: 'text/csv;charset=utf-8' })
  const u = URL.createObjectURL(b)
  const a = document.createElement('a'); a.href = u; a.download = `交通检测报告_${ts}.csv`; a.click()
  URL.revokeObjectURL(u)
  ElMessage.success(`已导出 ${t.length} 条检测数据`)
}

function saveImage() {
  const dataUrl = canvasComp.value?.captureCanvas()
  if (!dataUrl) { ElMessage.warning('没有可保存的检测结果'); return }
  const a = document.createElement('a')
  a.href = dataUrl
  a.download = `traffic_annotated_${Date.now()}.png`
  a.click()
  ElMessage.success('标注图片已保存')
}

function handleUpload(f: File) {
  uploadedFile.value = f
  stopDetection()
  detectionStore.clearDetection()
  if (/\.(jpg|jpeg|png|bmp|webp|gif)$/i.test(f.name)) {
    const reader = new FileReader()
    reader.onload = (e) => {
      const base64 = (e.target?.result as string).split(',')[1]
      detectionStore.updateDetection(base64, [], 0, 0, 0)
    }
    reader.readAsDataURL(f)
  }
}

function handleUploadIr(f: File) {
  uploadedIrFile.value = f
}

watch(() => appStore.isFusionModel, (fusion) => {
  if (!fusion) uploadedIrFile.value = null
})

async function startDetection() {
  if (detectionStore.isDetecting) return
  if (!uploadedFile.value) {
    ElMessage.warning('请先上传图片或视频文件')
    return
  }
  const isImage = /\.(jpg|jpeg|png|bmp|webp|gif)$/i.test(uploadedFile.value.name)
  if (isImage) {
    await detectImage()
  } else {
    await detectionStore.startVideoDetection(uploadedFile.value, confThreshold.value)
  }
}

async function detectImage() {
  if (!uploadedFile.value) return
  detectionStore.isDetecting = true
  try {
    const formData = new FormData()
    formData.append('file', uploadedFile.value)
    if (appStore.isFusionModel && uploadedIrFile.value) {
      formData.append('ir_file', uploadedIrFile.value)
    }
    const res = await fetch(`/api/detect/image?conf=${confThreshold.value}&save=true`, { method: 'POST', body: formData })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: '检测失败' }))
      ElMessage.error(err.detail || '检测失败')
      return
    }
    const data = await res.json()
    const tracks: Track[] = (data.tracks || []).map((d: any, i: number) => ({
      track_id: d.track_id ?? (100 + i),
      class_id: d.class_id,
      class_name: d.class_name,
      bbox: d.bbox,
      confidence: d.confidence,
      age: 1,
      mask: d.mask || null,
    }))
    const reader = new FileReader()
    reader.onload = (e) => {
      const base64 = (e.target?.result as string).split(',')[1]
      const fpsVal = data.latency_ms > 0 ? +(1000 / data.latency_ms).toFixed(1) : 0
      detectionStore.updateDetection(base64, tracks, fpsVal, data.latency_ms || 0, 1)
    }
    reader.readAsDataURL(uploadedFile.value!)
    ElMessage.success(`检测完成: ${data.object_count} 个目标, ${(data.latency_ms || 0).toFixed(1)}ms`)
  } catch {
    ElMessage.error('无法连接后端，请确保后端已启动 (端口 8000)')
  } finally {
    detectionStore.isDetecting = false
  }
}

function toggleDetection() {
  if (!detectionStore.isDetecting) {
    if (uploadedFile.value) startDetection()
    return
  }
  detectionStore.toggleVideoDetection()
}

function handleSeek(_val: number) { /* 视频流不支持 seek */ }

function stopDetection() {
  detectionStore.stopVideoDetection()
}
</script>

<style lang="scss" scoped>
.detection-view { height: 100%; display: flex; flex-direction: column; gap: 12px; }
.detection-main { flex: 1; display: flex; gap: 14px; min-height: 0; }
.video-area { flex: 7; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.video-wrapper { flex: 1; min-height: 0; }
.stats-area { flex: 3; display: flex; flex-direction: column; gap: 10px; overflow-y: auto; min-width: 280px; }
.param-card { padding: 18px; }
.param-row { display: flex; align-items: center; gap: 10px; margin-top: 8px; .el-slider { flex: 1; } }
.param-name { font-size: 14px; color: $text-secondary; width: 54px; font-weight: 600; }
.param-val { font-size: 14px; color: $ind-cyan; width: 40px; text-align: right; font-weight: 700; }
.action-bar { display: flex; gap: 16px; align-items: center; padding: 14px 20px; }
.action-btns { display: flex; gap: 10px; flex-shrink: 0; }
</style>
