import { defineStore } from 'pinia'
import { ref, computed, shallowRef } from 'vue'
import { ElMessage } from 'element-plus'
import type { Track, DetectionStats, CategoryDef } from '@/types'
export const useDetectionStore = defineStore('detection', () => {
  const tracks = shallowRef<Track[]>([])
  const currentFrame = shallowRef<string>('')
  const currentFrameBlob = shallowRef<Blob | null>(null)
  const frameId = ref(0)
  const fps = ref(0)
  const latency = ref(0)
  const isDetecting = ref(false)

  const categories = ref<CategoryDef[]>([])
  const selectedCategoryId = ref<number | null>(null)

  // ===== 视频 WebSocket 状态 (全局持久) =====
  let activeWs: WebSocket | null = null
  const paused = ref(false)
  const videoProgress = ref(0)
  const videoCurrentTime = ref(0)
  const videoDuration = ref(0)
  const videoTotalFrames = ref(0)
  const videoSrcFps = ref(25)

  const categoryColorMap = computed(() =>
    Object.fromEntries(categories.value.map(c => [c.id, c.color])) as Record<number, string>
  )

  const filteredTracks = computed(() =>
    selectedCategoryId.value === null
      ? tracks.value
      : tracks.value.filter(t => t.class_id === selectedCategoryId.value)
  )

  function toggleCategoryFilter(categoryId: number) {
    selectedCategoryId.value = selectedCategoryId.value === categoryId ? null : categoryId
  }

  async function fetchCategories() {
    try {
      const res = await fetch('/api/categories')
      if (res.ok) {
        const data = await res.json()
        categories.value = data.categories || []
      }
    } catch { /* backend unreachable — keep existing */ }
  }

  const categoryCounts = computed(() => {
    const counts: Record<number, number> = {}
    categories.value.forEach(c => { counts[c.id] = 0 })
    tracks.value.forEach(t => {
      counts[t.class_id] = (counts[t.class_id] || 0) + 1
    })
    return counts
  })

  const totalObjects = computed(() => tracks.value.length)

  const stats = computed<DetectionStats>(() => ({
    totalObjects: totalObjects.value,
    categoryCounts: categoryCounts.value,
    fps: fps.value,
    latency: latency.value,
  }))

  // ---- HUD 节流：fps/latency/frameId/progress 200ms 刷一次，避免高频触发模板重渲染 ----
  let _fps = 0
  let _latency = 0
  let _frameId = 0
  let _progress = 0
  let _hudTimer: ReturnType<typeof setInterval> | null = null

  function _startHudFlush() {
    if (_hudTimer) return
    _hudTimer = setInterval(() => {
      fps.value = _fps
      latency.value = _latency
      frameId.value = _frameId
      videoProgress.value = _progress
    }, 200)
  }

  function _stopHudFlush() {
    if (_hudTimer) { clearInterval(_hudTimer); _hudTimer = null }
  }

  function updateDetection(frame: string, newTracks: Track[], newFps: number, newLatency: number, newFrameId: number, frameBlob?: Blob | null) {
    currentFrame.value = frameBlob ? 'stream' : frame
    currentFrameBlob.value = frameBlob ?? null
    tracks.value = newTracks
    // 存到普通变量，由定时器 flush 到响应式
    _fps = newFps
    _latency = newLatency
    _frameId = newFrameId
  }

  function clearDetection() {
    _stopHudFlush()
    tracks.value = []
    currentFrame.value = ''
    currentFrameBlob.value = null
    frameId.value = 0
    fps.value = 0
    latency.value = 0
    _fps = 0; _latency = 0; _frameId = 0; _progress = 0
    isDetecting.value = false
  }

  // ===== WebSocket 视频检测 =====

  async function startVideoDetection(file: File, confThreshold: number) {
    if (isDetecting.value) return
    isDetecting.value = true
    paused.value = false
    videoProgress.value = 0
    videoCurrentTime.value = 0
    _progress = 0
    _startHudFlush()

    try {
      const formData = new FormData()
      formData.append('file', file)
      ElMessage.info('正在上传视频...')
      const uploadRes = await fetch('/api/detect/upload', { method: 'POST', body: formData })
      if (!uploadRes.ok) {
        ElMessage.error('视频上传失败')
        isDetecting.value = false
        return
      }
      const uploadData = await uploadRes.json()
      videoDuration.value = uploadData.duration_s || 0
      videoTotalFrames.value = uploadData.total_frames || 0
      videoSrcFps.value = uploadData.fps || 25

      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${proto}//${location.host}/ws/detect`
      const ws = new WebSocket(wsUrl)
      ws.binaryType = 'blob'
      activeWs = ws
      let pendingMeta: any = null

      ws.onopen = () => {
        ws.send(JSON.stringify({ action: 'start', source: uploadData.filename }))
        ElMessage.success('交通检测已开始')
      }

      ws.onmessage = (event) => {
        try {
          if (typeof event.data === 'string') {
            const msg = JSON.parse(event.data)
            if (msg.type === 'detection') {
              pendingMeta = msg
            } else if (msg.type === 'video_info') {
              videoTotalFrames.value = msg.total_frames || 0
              videoDuration.value = msg.duration_s || 0
              videoSrcFps.value = msg.src_fps || 25
            } else if (msg.type === 'status' && msg.message === 'stream_ended') {
              _stopHudFlush()
              videoProgress.value = 100
              fps.value = _fps; latency.value = _latency; frameId.value = _frameId
              ElMessage.success('交通检测完成')
              isDetecting.value = false
              paused.value = false
              if (activeWs) { activeWs.close(); activeWs = null }
            } else if (msg.type === 'status' && msg.message === 'paused') {
              paused.value = true
            } else if (msg.type === 'status' && msg.message === 'resumed') {
              paused.value = false
            } else if (msg.type === 'error') {
              ElMessage.error(msg.message || '检测出错')
              stopVideoDetection()
            }
          } else {
            if (pendingMeta) {
              const meta = pendingMeta
              pendingMeta = null
              const parsedTracks: Track[] = (meta.tracks || []).map((d: any, i: number) => ({
                track_id: d.track_id ?? i,
                class_id: d.class_id,
                class_name: d.class_name,
                bbox: d.bbox,
                confidence: d.confidence,
                age: d.age || 1,
                mask: d.mask || null,
              }))
              const blob = event.data as Blob
              updateDetection('', parsedTracks, meta.fps || 0, meta.latency_ms || 0, meta.frame_id || 0, blob)
              const total = meta.total_frames || videoTotalFrames.value
              if (total > 0) {
                _progress = (meta.frame_id / total) * 100
                videoCurrentTime.value = meta.frame_id / videoSrcFps.value
              }
            }
          }
        } catch { /* ignore parse errors */ }
      }

      ws.onerror = () => {
        ElMessage.error('WebSocket 连接失败')
        stopVideoDetection()
      }
    } catch {
      ElMessage.error('交通检测启动失败，请确保后端已启动')
      isDetecting.value = false
    }
  }

  function toggleVideoDetection() {
    if (!activeWs || activeWs.readyState !== WebSocket.OPEN) return
    if (paused.value) {
      activeWs.send(JSON.stringify({ action: 'resume' }))
      paused.value = false // 乐观更新，不等后端确认
    } else {
      activeWs.send(JSON.stringify({ action: 'pause' }))
      paused.value = true
    }
  }

  function stopVideoDetection() {
    _stopHudFlush()
    if (activeWs) {
      try { activeWs.send(JSON.stringify({ action: 'stop' })) } catch { /* ws may be closed */ }
      activeWs.close()
      activeWs = null
    }
    isDetecting.value = false
    paused.value = false
  }

  function hasActiveWs(): boolean {
    return activeWs !== null && activeWs.readyState === WebSocket.OPEN
  }

  return {
    tracks, currentFrame, currentFrameBlob, frameId, fps, latency, isDetecting,
    categories, categoryColorMap, fetchCategories,
    selectedCategoryId, filteredTracks, toggleCategoryFilter,
    categoryCounts, totalObjects, stats,
    updateDetection, clearDetection,
    // 视频 WebSocket
    paused, videoProgress, videoCurrentTime, videoDuration, videoTotalFrames, videoSrcFps,
    startVideoDetection, toggleVideoDetection, stopVideoDetection, hasActiveWs,
  }
})
