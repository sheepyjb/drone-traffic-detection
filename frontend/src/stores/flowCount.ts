/**
 * 交通态势分析 Store
 *
 * 双模式:
 * 1. 自动模式 (默认): 纯轨迹分析, 无需虚拟线
 *    - 车流量 = 唯一 track_id 计数
 *    - 方向 = 轨迹运动向量
 *    - 拥堵 = 区域平均速度
 *    - 排队 = 连续静止车辆
 *    - 转向 = 轨迹曲率变化
 * 2. 虚拟线模式 (可选): 任意角度虚拟线断面计数
 *
 * 性能: 热路径用纯 JS, 冷路径 10Hz 刷新 Vue 响应式
 */
import { defineStore } from 'pinia'
import { ref, computed, reactive } from 'vue'
import type { Track, VirtualLine, LineCrossing, TrackTurn, TurnType, TrafficEvent, LOSGrade } from '@/types'

const CLASS_LABELS: Record<number, string> = {
  0: '小汽车', 1: '货车', 2: '大巴', 3: '厢式货车', 4: '货运车',
}

const TURN_MAP: Record<string, Record<string, TurnType>> = {
  south: { north: 'straight', east: 'left',    west: 'right',   south: 'uturn' },
  north: { south: 'straight', west: 'left',    east: 'right',   north: 'uturn' },
  west:  { east:  'straight', north: 'left',   south: 'right',  west:  'uturn' },
  east:  { west:  'straight', south: 'left',   north: 'right',  east:  'uturn' },
}

const TURN_LABELS: Record<TurnType, string> = {
  straight: '直行', left: '左转', right: '右转', uturn: '掉头', unknown: '未知',
}

function getServiceLevel(avgDelaySec: number): LOSGrade {
  if (avgDelaySec <= 10) return 'A'
  if (avgDelaySec <= 20) return 'B'
  if (avgDelaySec <= 35) return 'C'
  if (avgDelaySec <= 55) return 'D'
  if (avgDelaySec <= 80) return 'E'
  return 'F'
}

const LOS_COLORS: Record<LOSGrade, string> = {
  A: '#22c55e', B: '#84cc16', C: '#eab308', D: '#f97316', E: '#ef4444', F: '#dc2626',
}

const FLUSH_INTERVAL = 100

export const useFlowCountStore = defineStore('flowCount', () => {

  // ===== 几何工具 =====
  function crossProduct(line: VirtualLine, px: number, py: number): number {
    const dx = line.end.x - line.start.x
    const dy = line.end.y - line.start.y
    return dx * (py - line.start.y) - dy * (px - line.start.x)
  }

  function bboxIntersectsLine(bbox: [number, number, number, number], line: VirtualLine): boolean {
    const [x1, y1, x2, y2] = bbox
    const corners = [
      crossProduct(line, x1, y1), crossProduct(line, x2, y1),
      crossProduct(line, x1, y2), crossProduct(line, x2, y2),
    ]
    return corners.some(c => c > 0) && corners.some(c => c < 0)
  }

  // ===== 模式切换 =====
  const linesEnabled = ref(false) // 默认关闭虚拟线

  // ===== 虚拟线 (可选) =====
  const virtualLines = ref<VirtualLine[]>([
    { id: 'line-north', start: { x: 0, y: 0.30 }, end: { x: 1, y: 0.30 }, name: '北侧线', color: '#3B82F6' },
    { id: 'line-south', start: { x: 0, y: 0.70 }, end: { x: 1, y: 0.70 }, name: '南侧线', color: '#EF4444' },
    { id: 'line-west',  start: { x: 0.30, y: 0 }, end: { x: 0.30, y: 1 }, name: '西侧线', color: '#F59E0B' },
    { id: 'line-east',  start: { x: 0.70, y: 0 }, end: { x: 0.70, y: 1 }, name: '东侧线', color: '#10B981' },
  ])

  // ===== 轨迹数据 =====
  const trackHistory = new Map<number, { cy: number; cx: number }>()
  const trackPositionHistory = new Map<number, { cx: number; cy: number; t: number }[]>()
  const trackFirstSeen = new Map<number, number>()
  const seenTrackIds = new Set<number>() // 全局唯一 ID 统计

  // ===== 自动模式: 车流量统计 =====
  const totalVehicleCount = ref(0) // 唯一 track_id 总数
  const classCounts = reactive<Record<number, number>>({ 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 })

  // ===== 自动模式: 方向统计 (轨迹向量) =====
  const _autoDir = { north: 0, south: 0, east: 0, west: 0 }
  const autoDirectionCounts = reactive<Record<string, number>>({ north: 0, south: 0, east: 0, west: 0 })

  /** 根据轨迹历史计算运动方向 */
  function getTrackDirection(trackId: number): string | null {
    const history = trackPositionHistory.get(trackId)
    if (!history || history.length < 10) return null
    const first = history[0]
    const last = history[history.length - 1]
    const dx = last.cx - first.cx
    const dy = last.cy - first.cy
    const dist = Math.hypot(dx, dy)
    if (dist < 0.02) return null // 几乎没动
    // 主方向
    if (Math.abs(dy) > Math.abs(dx)) {
      return dy < 0 ? 'north' : 'south'
    } else {
      return dx < 0 ? 'west' : 'east'
    }
  }

  // ===== 自动模式: 速度 & 拥堵 =====
  const avgSpeed = ref(0)       // 归一化坐标/帧
  const congestionLevel = ref<'畅通' | '缓行' | '拥堵' | '严重拥堵'>('畅通')
  const stoppedCount = ref(0)   // 静止车辆数
  const movingCount = ref(0)    // 运动车辆数

  const SPEED_THRESHOLD_SLOW = 0.003   // 缓行
  const SPEED_THRESHOLD_STOP = 0.001   // 静止

  function computeAutoMetrics(tracks: Track[]) {
    let totalSpeed = 0
    let speedCount = 0
    let stopped = 0
    let moving = 0

    for (const track of tracks) {
      const history = trackPositionHistory.get(track.track_id)
      if (!history || history.length < 3) continue
      const recent = history.slice(-5)
      const first = recent[0]
      const last = recent[recent.length - 1]
      const speed = Math.hypot(last.cx - first.cx, last.cy - first.cy) / recent.length
      totalSpeed += speed
      speedCount++
      if (speed < SPEED_THRESHOLD_STOP) stopped++
      else moving++
    }

    stoppedCount.value = stopped
    movingCount.value = moving
    avgSpeed.value = speedCount > 0 ? totalSpeed / speedCount : 0

    // 拥堵等级
    const ratio = tracks.length > 0 ? stopped / tracks.length : 0
    if (ratio > 0.6) congestionLevel.value = '严重拥堵'
    else if (ratio > 0.4) congestionLevel.value = '拥堵'
    else if (ratio > 0.2) congestionLevel.value = '缓行'
    else congestionLevel.value = '畅通'
  }

  // ===== 自动模式: 转向分析 (轨迹曲率) =====
  const autoTurns = ref<{ trackId: number; direction: string; className: string }[]>([])
  const trackedDirections = new Map<number, string>() // 已记录方向的 track

  function analyzeAutoTurn(trackId: number, className: string) {
    const history = trackPositionHistory.get(trackId)
    if (!history || history.length < 20) return
    // 看前半段和后半段的方向变化
    const mid = Math.floor(history.length / 2)
    const firstHalf = history.slice(0, mid)
    const secondHalf = history.slice(mid)
    const dir1 = vecDirection(firstHalf[0], firstHalf[firstHalf.length - 1])
    const dir2 = vecDirection(secondHalf[0], secondHalf[secondHalf.length - 1])
    if (dir1 && dir2 && dir1 !== dir2) {
      autoTurns.value.push({ trackId, direction: `${dir1}→${dir2}`, className })
      if (autoTurns.value.length > 100) autoTurns.value.shift()
    }
  }

  function vecDirection(a: { cx: number; cy: number }, b: { cx: number; cy: number }): string | null {
    const dx = b.cx - a.cx, dy = b.cy - a.cy
    if (Math.hypot(dx, dy) < 0.02) return null
    if (Math.abs(dy) > Math.abs(dx)) return dy < 0 ? '北' : '南'
    return dx < 0 ? '西' : '东'
  }

  // ===== 虚拟线模式的数据 =====
  const crossings = ref<LineCrossing[]>([])
  let _totalCrossedCount = 0
  const totalCrossedRef = ref(0)
  const lineCounts = reactive<Record<string, { positive: number; negative: number }>>({})

  const totalCrossed = computed(() => totalCrossedRef.value)
  const directionSummary = computed(() => {
    if (linesEnabled.value) {
      const result: Record<string, number> = { north: 0, south: 0, west: 0, east: 0 }
      for (const line of virtualLines.value) {
        const c = lineCounts[line.id]
        if (c) result[line.id.replace('line-', '')] = c.positive + c.negative
      }
      return result
    }
    return { ...autoDirectionCounts }
  })

  // ===== 转向 =====
  const trackEntryLine = new Map<number, string>()
  const turns = ref<TrackTurn[]>([])

  function classifyTurn(entry: string, exit: string): TurnType {
    return TURN_MAP[entry]?.[exit] || 'unknown'
  }

  const turnSummary = computed(() => {
    const result: Record<string, Record<TurnType, number>> = {}
    for (const dir of ['north', 'south', 'east', 'west']) {
      result[dir] = { straight: 0, left: 0, right: 0, uturn: 0, unknown: 0 }
    }
    for (const t of turns.value) {
      if (result[t.entryLine]) result[t.entryLine][t.turnType]++
    }
    return result
  })

  // ===== 拥堵指标 =====
  const trackDwellTimes = ref<number[]>([])
  const detectionStartTime = ref(0)
  let currentFps = 30
  let totalFrames = 0

  const _dirVehicles = { north: 0, south: 0, east: 0, west: 0 }
  const _queueVehicles = { north: 0, south: 0, east: 0, west: 0 }
  const _lineOccBuf: Record<string, boolean[]> = {}
  let lastFlushTime = 0

  const directionVehicleCounts = reactive<Record<string, number>>({ north: 0, south: 0, east: 0, west: 0 })
  const queueVehiclesByDirection = reactive<Record<string, number>>({ north: 0, south: 0, east: 0, west: 0 })
  const occupancySnapshot = ref<Record<string, number>>({})

  function flushToReactive(now: number) {
    if (now - lastFlushTime < FLUSH_INTERVAL) return
    lastFlushTime = now
    directionVehicleCounts.north = _dirVehicles.north
    directionVehicleCounts.south = _dirVehicles.south
    directionVehicleCounts.east = _dirVehicles.east
    directionVehicleCounts.west = _dirVehicles.west
    queueVehiclesByDirection.north = _queueVehicles.north
    queueVehiclesByDirection.south = _queueVehicles.south
    queueVehiclesByDirection.east = _queueVehicles.east
    queueVehiclesByDirection.west = _queueVehicles.west

    // 自动方向统计 (基于轨迹)
    autoDirectionCounts.north = _autoDir.north
    autoDirectionCounts.south = _autoDir.south
    autoDirectionCounts.east = _autoDir.east
    autoDirectionCounts.west = _autoDir.west

    if (linesEnabled.value) {
      const occResult: Record<string, number> = {}
      for (const line of virtualLines.value) {
        const dir = line.id.replace('line-', '')
        const buf = _lineOccBuf[line.id]
        if (!buf || buf.length === 0) { occResult[dir] = 0; continue }
        let count = 0
        for (let i = 0; i < buf.length; i++) { if (buf[i]) count++ }
        occResult[dir] = Math.round((count / buf.length) * 100)
      }
      occupancySnapshot.value = occResult
    }
  }

  // ===== 排队 =====
  const VEHICLE_LENGTH = 5
  const QUEUE_SPEED_THRESHOLD = 0.003
  const QUEUE_ZONE_MARGIN = 0.05

  const queueLengthByDirection = computed(() => {
    const result: Record<string, number> = {}
    for (const dir of ['north', 'south', 'east', 'west']) {
      result[dir] = queueVehiclesByDirection[dir] * VEHICLE_LENGTH
    }
    return result
  })

  const maxQueueLength = computed(() => Math.max(...Object.values(queueLengthByDirection.value), 0))

  function isTrackStopped(trackId: number): boolean {
    const history = trackPositionHistory.get(trackId)
    if (!history || history.length < 5) return false
    const last = history[history.length - 1]
    const first = history[history.length - 5]
    return (Math.abs(last.cx - first.cx) + Math.abs(last.cy - first.cy)) < QUEUE_SPEED_THRESHOLD
  }

  function computeQueueVehicles(tracks: Track[]) {
    _queueVehicles.north = _queueVehicles.south = _queueVehicles.east = _queueVehicles.west = 0
    for (const track of tracks) {
      if (!isTrackStopped(track.track_id)) continue
      const cx = (track.bbox[0] + track.bbox[2]) / 2
      const cy = (track.bbox[1] + track.bbox[3]) / 2
      if (cy < 0.35) _queueVehicles.north++
      else if (cy > 0.65) _queueVehicles.south++
      if (cx < 0.35) _queueVehicles.west++
      else if (cx > 0.65) _queueVehicles.east++
    }
  }

  const OCCUPANCY_WINDOW = 60
  const occupancyByLine = computed(() => occupancySnapshot.value)
  const avgOccupancy = computed(() => {
    const vals = Object.values(occupancySnapshot.value)
    if (vals.length === 0) return 0
    return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
  })
  const avgDelay = computed(() => {
    const times = trackDwellTimes.value
    if (times.length === 0) return 0
    return Math.round(times.reduce((a, b) => a + b, 0) / times.length / 1000 * 10) / 10
  })
  const serviceLevelGrade = computed<LOSGrade>(() => getServiceLevel(avgDelay.value))
  const serviceLevelColor = computed(() => LOS_COLORS[serviceLevelGrade.value])

  // ===== 事件预警 =====
  const trafficEvents = ref<TrafficEvent[]>([])
  const ILLEGAL_STOP_FRAMES = 45
  const ILLEGAL_STOP_THRESHOLD = 0.005
  const LONG_QUEUE_THRESHOLD = 50
  const ACCIDENT_DISTANCE_THRESHOLD = 0.03
  const ACCIDENT_MIN_STOPPED = 3
  const WRONG_WAY_RATIO_THRESHOLD = 0.80
  const WRONG_WAY_MIN_TOTAL = 8
  let eventIdCounter = 0
  const triggeredStopEvents = new Set<number>()
  const triggeredWrongWayEvents = new Set<number>()

  function addEvent(event: Omit<TrafficEvent, 'id'>) {
    const id = `evt-${++eventIdCounter}-${Date.now()}`
    trafficEvents.value.unshift({ ...event, id })
    if (trafficEvents.value.length > 50) trafficEvents.value = trafficEvents.value.slice(0, 50)
  }

  function checkWrongWay(lineId: string, lineName: string, direction: 'positive' | 'negative', trackId: number, cx: number, cy: number, now: number) {
    if (triggeredWrongWayEvents.has(trackId)) return
    const counts = lineCounts[lineId]
    if (!counts) return
    const total = counts.positive + counts.negative
    if (total < WRONG_WAY_MIN_TOTAL) return
    const majorDir = counts.positive >= counts.negative ? 'positive' : 'negative'
    const majorRatio = Math.max(counts.positive, counts.negative) / total
    if (majorRatio >= WRONG_WAY_RATIO_THRESHOLD && direction !== majorDir) {
      triggeredWrongWayEvents.add(trackId)
      addEvent({ type: 'wrong_way', severity: 'danger', message: `车辆 #${trackId} 疑似逆行（${lineName}反向穿越）`, trackId, timestamp: now, position: { cx, cy } })
    }
  }

  function checkEvents(tracks: Track[], now: number) {
    // 违停 (自动模式也能检测: 路口中心区域静止)
    for (const [trackId, history] of trackPositionHistory) {
      if (history.length < ILLEGAL_STOP_FRAMES || triggeredStopEvents.has(trackId)) continue
      const last = history[history.length - 1]
      const first = history[history.length - ILLEGAL_STOP_FRAMES]
      if (Math.abs(last.cx - first.cx) < ILLEGAL_STOP_THRESHOLD && Math.abs(last.cy - first.cy) < ILLEGAL_STOP_THRESHOLD) {
        // 在画面中心区域才算违停
        if (last.cx > 0.2 && last.cx < 0.8 && last.cy > 0.2 && last.cy < 0.8) {
          triggeredStopEvents.add(trackId)
          addEvent({ type: 'illegal_stop', severity: 'warning', message: `车辆 #${trackId} 疑似违停（持续静止 >5s）`, trackId, timestamp: now, position: { cx: last.cx, cy: last.cy } })
        }
      }
    }

    // 长排队
    for (const dir of ['north', 'south', 'east', 'west'] as const) {
      const ql = _queueVehicles[dir] * VEHICLE_LENGTH
      if (ql >= LONG_QUEUE_THRESHOLD) {
        const recentSame = trafficEvents.value.find(e => e.type === 'long_queue' && e.message.includes(dir) && now - e.timestamp < 10000)
        if (!recentSame) {
          const dirLabel: Record<string, string> = { north: '北', south: '南', east: '东', west: '西' }
          addEvent({ type: 'long_queue', severity: 'warning', message: `${dirLabel[dir]}方向排队过长（${ql}m）`, timestamp: now })
        }
      }
    }

    // 事故疑似
    const stoppedTracks: { trackId: number; cx: number; cy: number }[] = []
    for (const [trackId, history] of trackPositionHistory) {
      if (history.length < 30) continue
      const first = history[history.length - 30], last = history[history.length - 1]
      if (Math.abs(last.cx - first.cx) < ILLEGAL_STOP_THRESHOLD && Math.abs(last.cy - first.cy) < ILLEGAL_STOP_THRESHOLD) {
        stoppedTracks.push({ trackId, cx: last.cx, cy: last.cy })
      }
    }
    if (stoppedTracks.length >= ACCIDENT_MIN_STOPPED) {
      for (let i = 0; i < stoppedTracks.length; i++) {
        let nearbyCount = 0
        for (let j = 0; j < stoppedTracks.length; j++) {
          if (i !== j && Math.hypot(stoppedTracks[i].cx - stoppedTracks[j].cx, stoppedTracks[i].cy - stoppedTracks[j].cy) < ACCIDENT_DISTANCE_THRESHOLD)
            nearbyCount++
        }
        if (nearbyCount >= ACCIDENT_MIN_STOPPED - 1) {
          if (!trafficEvents.value.find(e => e.type === 'accident_suspect' && now - e.timestamp < 15000)) {
            addEvent({ type: 'accident_suspect', severity: 'danger', message: `疑似交通事故：${nearbyCount + 1}辆车聚集停止`, timestamp: now, position: { cx: stoppedTracks[i].cx, cy: stoppedTracks[i].cy } })
          }
          break
        }
      }
    }

    // 自动逆行检测 (无需虚拟线: 运动方向与主流方向相反)
    if (!linesEnabled.value) {
      const dirCounts = { north: 0, south: 0, east: 0, west: 0 }
      for (const track of tracks) {
        const d = getTrackDirection(track.track_id)
        if (d) dirCounts[d as keyof typeof dirCounts]++
      }
      // 找主流方向
      const totalDir = Object.values(dirCounts).reduce((a, b) => a + b, 0)
      if (totalDir >= 5) {
        for (const track of tracks) {
          if (triggeredWrongWayEvents.has(track.track_id)) continue
          const d = getTrackDirection(track.track_id)
          if (!d) continue
          const opposite: Record<string, string> = { north: 'south', south: 'north', east: 'west', west: 'east' }
          const oppDir = opposite[d]
          if (dirCounts[oppDir as keyof typeof dirCounts] / totalDir > 0.7 && dirCounts[d as keyof typeof dirCounts] <= 1) {
            triggeredWrongWayEvents.add(track.track_id)
            const cx = (track.bbox[0] + track.bbox[2]) / 2, cy = (track.bbox[1] + track.bbox[3]) / 2
            addEvent({ type: 'wrong_way', severity: 'danger', message: `车辆 #${track.track_id} 疑似逆行（运动方向与主流相反）`, trackId: track.track_id, timestamp: Date.now(), position: { cx, cy } })
          }
        }
      }
    }
  }

  // ===== 时间序列 =====
  const flowTimeSeries = ref<{ time: string; count: number }[]>([])
  let lastBucketTime = 0
  let bucketNewVehicles = 0

  // ========================================
  // 核心 processFrame
  // ========================================
  function processFrame(tracks: Track[], fps?: number) {
    const now = Date.now()
    if (fps) currentFps = fps
    if (detectionStartTime.value === 0) detectionStartTime.value = now
    totalFrames++

    const currentIds = new Set<number>()
    _dirVehicles.north = _dirVehicles.south = _dirVehicles.east = _dirVehicles.west = 0
    _autoDir.north = _autoDir.south = _autoDir.east = _autoDir.west = 0

    const lineOccupiedThisFrame: Record<string, boolean> = {}
    if (linesEnabled.value) {
      for (const line of virtualLines.value) lineOccupiedThisFrame[line.id] = false
    }

    for (const track of tracks) {
      currentIds.add(track.track_id)
      const cx = (track.bbox[0] + track.bbox[2]) / 2
      const cy = (track.bbox[1] + track.bbox[3]) / 2

      // 首次出现 → 计入车流量
      if (!seenTrackIds.has(track.track_id)) {
        seenTrackIds.add(track.track_id)
        totalVehicleCount.value = seenTrackIds.size
        classCounts[track.class_id] = (classCounts[track.class_id] || 0) + 1
        bucketNewVehicles++
      }

      if (!trackFirstSeen.has(track.track_id)) trackFirstSeen.set(track.track_id, now)

      // 位置历史
      let posHistory = trackPositionHistory.get(track.track_id)
      if (!posHistory) { posHistory = []; trackPositionHistory.set(track.track_id, posHistory) }
      posHistory.push({ cx, cy, t: now })
      if (posHistory.length > 60) posHistory.shift()

      // 方向分区 (位置)
      if (cy < 0.3) _dirVehicles.north++
      else if (cy > 0.7) _dirVehicles.south++
      if (cx < 0.3) _dirVehicles.west++
      else if (cx > 0.7) _dirVehicles.east++

      // 方向统计 (轨迹向量)
      const dir = getTrackDirection(track.track_id)
      if (dir) _autoDir[dir as keyof typeof _autoDir]++

      // ===== 虚拟线模式 =====
      if (linesEnabled.value) {
        for (const line of virtualLines.value) {
          if (bboxIntersectsLine(track.bbox, line)) lineOccupiedThisFrame[line.id] = true
        }
        const prev = trackHistory.get(track.track_id)
        if (prev) {
          for (const line of virtualLines.value) {
            const prevSide = crossProduct(line, prev.cx, prev.cy)
            const currSide = crossProduct(line, cx, cy)
            if ((prevSide < 0) !== (currSide < 0) && prevSide !== 0 && currSide !== 0) {
              const direction: 'positive' | 'negative' = currSide > 0 ? 'positive' : 'negative'
              _totalCrossedCount++
              totalCrossedRef.value = _totalCrossedCount
              crossings.value.push({ lineId: line.id, trackId: track.track_id, classId: track.class_id, className: track.class_name || CLASS_LABELS[track.class_id] || `class_${track.class_id}`, direction, timestamp: now })
              if (crossings.value.length > 200) crossings.value.shift()
              if (!lineCounts[line.id]) lineCounts[line.id] = { positive: 0, negative: 0 }
              lineCounts[line.id][direction]++

              checkWrongWay(line.id, line.name, direction, track.track_id, cx, cy, now)

              const lineName = line.id.replace('line-', '')
              const existingEntry = trackEntryLine.get(track.track_id)
              if (!existingEntry) trackEntryLine.set(track.track_id, lineName)
              else if (existingEntry !== lineName) {
                turns.value.push({ trackId: track.track_id, classId: track.class_id, className: track.class_name || CLASS_LABELS[track.class_id] || `class_${track.class_id}`, entryLine: existingEntry, exitLine: lineName, turnType: classifyTurn(existingEntry, lineName), timestamp: now })
                trackEntryLine.delete(track.track_id)
              }
            }
          }
        }
      }

      trackHistory.set(track.track_id, { cy, cx })
    }

    // 占有率 (虚拟线模式)
    if (linesEnabled.value) {
      for (const line of virtualLines.value) {
        if (!_lineOccBuf[line.id]) _lineOccBuf[line.id] = []
        _lineOccBuf[line.id].push(lineOccupiedThisFrame[line.id])
        if (_lineOccBuf[line.id].length > OCCUPANCY_WINDOW) _lineOccBuf[line.id].shift()
      }
    }

    computeQueueVehicles(tracks)
    computeAutoMetrics(tracks)

    // 清理消失轨迹
    for (const [id] of trackHistory) {
      if (!currentIds.has(id)) {
        trackHistory.delete(id)
        const firstSeen = trackFirstSeen.get(id)
        if (firstSeen) {
          trackDwellTimes.value.push(now - firstSeen)
          if (trackDwellTimes.value.length > 200) trackDwellTimes.value.shift()
          trackFirstSeen.delete(id)
        }
        // 消失时做转向分析
        analyzeAutoTurn(id, CLASS_LABELS[0])
        trackPositionHistory.delete(id)
        trackEntryLine.delete(id)
        triggeredStopEvents.delete(id)
        triggeredWrongWayEvents.delete(id)
        trackedDirections.delete(id)
      }
    }

    if (totalFrames % 30 === 0) checkEvents(tracks, now)

    // 时间序列
    const bucketMs = 2000
    if (now - lastBucketTime >= bucketMs) {
      lastBucketTime = now
      const timeStr = new Date(now).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      flowTimeSeries.value.push({ time: timeStr, count: bucketNewVehicles })
      bucketNewVehicles = 0
      if (flowTimeSeries.value.length > 60) flowTimeSeries.value.shift()
    }

    flushToReactive(now)
  }

  const detectionDuration = computed(() => {
    if (detectionStartTime.value === 0) return 0
    return (Date.now() - detectionStartTime.value) / 1000
  })

  function reset() {
    trackHistory.clear(); crossings.value = []; _totalCrossedCount = 0; totalCrossedRef.value = 0
    Object.keys(classCounts).forEach(k => { classCounts[Number(k)] = 0 })
    Object.keys(lineCounts).forEach(k => delete lineCounts[k])
    flowTimeSeries.value = []; lastBucketTime = 0; bucketNewVehicles = 0
    trackEntryLine.clear(); turns.value = []; trackFirstSeen.clear(); trackDwellTimes.value = []
    detectionStartTime.value = 0; totalFrames = 0; seenTrackIds.clear(); totalVehicleCount.value = 0
    _dirVehicles.north = _dirVehicles.south = _dirVehicles.east = _dirVehicles.west = 0
    _queueVehicles.north = _queueVehicles.south = _queueVehicles.east = _queueVehicles.west = 0
    _autoDir.north = _autoDir.south = _autoDir.east = _autoDir.west = 0
    autoDirectionCounts.north = autoDirectionCounts.south = autoDirectionCounts.east = autoDirectionCounts.west = 0
    directionVehicleCounts.north = directionVehicleCounts.south = directionVehicleCounts.east = directionVehicleCounts.west = 0
    queueVehiclesByDirection.north = queueVehiclesByDirection.south = queueVehiclesByDirection.east = queueVehiclesByDirection.west = 0
    Object.keys(_lineOccBuf).forEach(k => delete _lineOccBuf[k])
    occupancySnapshot.value = {}; lastFlushTime = 0; trackPositionHistory.clear()
    trafficEvents.value = []; eventIdCounter = 0; triggeredStopEvents.clear(); triggeredWrongWayEvents.clear()
    avgSpeed.value = 0; congestionLevel.value = '畅通'; stoppedCount.value = 0; movingCount.value = 0
    autoTurns.value = []; trackedDirections.clear()
  }

  function clearEvents() { trafficEvents.value = [] }

  return {
    // 模式
    linesEnabled,
    // 虚拟线
    virtualLines, crossings, lineCounts, totalCrossed,
    // 自动模式
    totalVehicleCount, autoDirectionCounts, avgSpeed, congestionLevel, stoppedCount, movingCount, autoTurns,
    // 共用
    classCounts, flowTimeSeries, directionSummary,
    turns, turnSummary, TURN_LABELS,
    queueLengthByDirection, maxQueueLength,
    occupancyByLine, avgOccupancy, avgDelay,
    serviceLevelGrade, serviceLevelColor,
    directionVehicleCounts, detectionDuration,
    trafficEvents,
    processFrame, reset, clearEvents,
  }
})
