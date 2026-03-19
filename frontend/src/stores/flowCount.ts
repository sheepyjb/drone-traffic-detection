/**
 * 虚拟线圈流量统计 Store
 * 4条检测线：北侧/南侧(水平) + 西侧/东侧(垂直)
 * 扩展功能：转向分析、拥堵评价、事件预警
 *
 * 性能优化：热路径（逐帧计算）使用纯 JS 变量，零响应式开销；
 * 冷路径（UI 渲染）通过 flushToReactive() 以 10Hz 刷新。
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

// ============================================================
// 刷新频率常量
// ============================================================
const FLUSH_INTERVAL = 100 // ms — UI 响应式数据刷新间隔（10Hz）

export const useFlowCountStore = defineStore('flowCount', () => {
  // ===== 4条虚拟检测线（十字路口） =====
  const virtualLines = ref<VirtualLine[]>([
    { id: 'line-north', position: 0.30, orientation: 'horizontal', name: '北侧线', color: '#3B82F6' },
    { id: 'line-south', position: 0.70, orientation: 'horizontal', name: '南侧线', color: '#EF4444' },
    { id: 'line-west',  position: 0.30, orientation: 'vertical',   name: '西侧线', color: '#F59E0B' },
    { id: 'line-east',  position: 0.70, orientation: 'vertical',   name: '东侧线', color: '#10B981' },
  ])

  // ===== 基础轨迹历史（纯 JS，非响应式） =====
  const trackHistory = new Map<number, { cy: number; cx: number }>()

  // ===== 穿越记录（保留最近 200 条用于导出，计数器记录总数） =====
  const crossings = ref<LineCrossing[]>([])
  let _totalCrossedCount = 0
  const totalCrossedRef = ref(0)

  // ===== 按车型累计 =====
  const classCounts = reactive<Record<number, number>>({
    0: 0, 1: 0, 2: 0, 3: 0, 4: 0,
  })

  // ===== 按检测线累计（事件驱动） =====
  const lineCounts = reactive<Record<string, { positive: number; negative: number }>>({})

  const totalCrossed = computed(() => totalCrossedRef.value)

  // ===== 时间序列 =====
  const flowTimeSeries = ref<{ time: string; count: number }[]>([])
  let lastBucketTime = 0
  let bucketCrossingCount = 0 // 增量计数，避免全量 filter

  // ===== 四方向统计 =====
  const directionSummary = computed(() => {
    const result: Record<string, number> = { north: 0, south: 0, west: 0, east: 0 }
    for (const line of virtualLines.value) {
      const c = lineCounts[line.id]
      if (c) result[line.id.replace('line-', '')] = c.positive + c.negative
    }
    return result
  })

  // ========================================
  // Feature 1: 轨迹转向分析
  // ========================================
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
      if (result[t.entryLine]) {
        result[t.entryLine][t.turnType]++
      }
    }
    return result
  })

  // ========================================
  // Feature 2: 拥堵评价指标
  // ========================================
  const trackFirstSeen = new Map<number, number>()
  const trackDwellTimes = ref<number[]>([])
  const detectionStartTime = ref(0)
  let currentFps = 30
  let totalFrames = 0

  // ---------- 热路径：纯 JS 变量（每帧更新，零响应式开销） ----------
  const _dirVehicles = { north: 0, south: 0, east: 0, west: 0 }
  const _queueVehicles = { north: 0, south: 0, east: 0, west: 0 }
  const _lineOccBuf: Record<string, boolean[]> = {}
  let lastFlushTime = 0

  // ---------- 冷路径：响应式变量（10Hz 刷新，驱动 UI） ----------
  const directionVehicleCounts = reactive<Record<string, number>>({
    north: 0, south: 0, east: 0, west: 0,
  })
  const queueVehiclesByDirection = reactive<Record<string, number>>({
    north: 0, south: 0, east: 0, west: 0,
  })
  // 占有率快照（10Hz 刷新）
  const occupancySnapshot = ref<Record<string, number>>({})

  /** 将热路径数据刷入响应式状态（10Hz 节流） */
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

    // 占有率计算
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

  // ===== 排队长度 =====
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

  const maxQueueLength = computed(() => {
    return Math.max(...Object.values(queueLengthByDirection.value), 0)
  })

  /** 判断 track 是否在排队（零分配版） */
  function isTrackStopped(trackId: number): boolean {
    const history = trackPositionHistory.get(trackId)
    if (!history || history.length < 5) return false
    const last = history[history.length - 1]
    const first = history[history.length - 5]
    return (Math.abs(last.cx - first.cx) + Math.abs(last.cy - first.cy)) < QUEUE_SPEED_THRESHOLD
  }

  /** 计算排队车辆数 → 写入热路径 _queueVehicles */
  function computeQueueVehicles(tracks: Track[]) {
    _queueVehicles.north = 0
    _queueVehicles.south = 0
    _queueVehicles.east = 0
    _queueVehicles.west = 0

    const nL = 0.30, sL = 0.70, wL = 0.30, eL = 0.70

    for (const track of tracks) {
      if (!isTrackStopped(track.track_id)) continue
      const cx = (track.bbox[0] + track.bbox[2]) / 2
      const cy = (track.bbox[1] + track.bbox[3]) / 2
      const inLaneH = cx > (wL - QUEUE_ZONE_MARGIN) && cx < (eL + QUEUE_ZONE_MARGIN)
      const inLaneV = cy > (nL - QUEUE_ZONE_MARGIN) && cy < (sL + QUEUE_ZONE_MARGIN)

      if (cy < nL && inLaneH) _queueVehicles.north++
      if (cy > sL && inLaneH) _queueVehicles.south++
      if (cx < wL && inLaneV) _queueVehicles.west++
      if (cx > eL && inLaneV) _queueVehicles.east++
    }
  }

  // 占有率（从快照读取）
  const OCCUPANCY_WINDOW = 60
  const occupancyByLine = computed(() => occupancySnapshot.value)

  const avgOccupancy = computed(() => {
    const vals = Object.values(occupancySnapshot.value)
    if (vals.length === 0) return 0
    return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
  })

  // 车均延误
  const avgDelay = computed(() => {
    const times = trackDwellTimes.value
    if (times.length === 0) return 0
    const avg = times.reduce((a, b) => a + b, 0) / times.length
    return Math.round(avg / 1000 * 10) / 10
  })

  const serviceLevelGrade = computed<LOSGrade>(() => getServiceLevel(avgDelay.value))
  const serviceLevelColor = computed(() => LOS_COLORS[serviceLevelGrade.value])

  // ========================================
  // Feature 4: 事件预警
  // ========================================
  const trackPositionHistory = new Map<number, { cx: number; cy: number; t: number }[]>()
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
    if (trafficEvents.value.length > 50) {
      trafficEvents.value = trafficEvents.value.slice(0, 50)
    }
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
      addEvent({
        type: 'wrong_way',
        severity: 'danger',
        message: `车辆 #${trackId} 疑似逆行（${lineName}反向穿越，该线${Math.round(majorRatio * 100)}%车辆为正向）`,
        trackId,
        timestamp: now,
        position: { cx, cy },
      })
    }
  }

  function checkEvents(tracks: Track[], now: number) {
    const nL = 0.30, sL = 0.70, wL = 0.30, eL = 0.70

    // 违停检测
    for (const [trackId, history] of trackPositionHistory) {
      if (history.length < ILLEGAL_STOP_FRAMES || triggeredStopEvents.has(trackId)) continue
      const last = history[history.length - 1]
      const first = history[history.length - ILLEGAL_STOP_FRAMES]
      const dx = Math.abs(last.cx - first.cx)
      const dy = Math.abs(last.cy - first.cy)
      if (dx < ILLEGAL_STOP_THRESHOLD && dy < ILLEGAL_STOP_THRESHOLD) {
        const cx = last.cx, cy = last.cy
        if ((cy < nL) || (cy > sL) || (cx < wL) || (cx > eL)) continue
        triggeredStopEvents.add(trackId)
        addEvent({
          type: 'illegal_stop',
          severity: 'warning',
          message: `车辆 #${trackId} 疑似违停（路口内持续静止 >5s）`,
          trackId,
          timestamp: now,
          position: { cx, cy },
        })
      }
    }

    // 长排队检测
    for (const dir of ['north', 'south', 'east', 'west']) {
      const ql = _queueVehicles[dir as keyof typeof _queueVehicles] * VEHICLE_LENGTH
      if (ql >= LONG_QUEUE_THRESHOLD) {
        const recentSame = trafficEvents.value.find(
          e => e.type === 'long_queue' && e.message.includes(dir) && now - e.timestamp < 10000
        )
        if (!recentSame) {
          const dirLabel: Record<string, string> = { north: '北', south: '南', east: '东', west: '西' }
          addEvent({
            type: 'long_queue',
            severity: 'warning',
            message: `${dirLabel[dir]}方向排队过长（${ql}m, ${_queueVehicles[dir as keyof typeof _queueVehicles]}辆）`,
            timestamp: now,
          })
        }
      }
    }

    // 事故疑似检测
    const stoppedTracks: { trackId: number; cx: number; cy: number }[] = []
    for (const [trackId, history] of trackPositionHistory) {
      if (history.length < 30) continue
      const first = history[history.length - 30]
      const last = history[history.length - 1]
      if (Math.abs(last.cx - first.cx) < ILLEGAL_STOP_THRESHOLD && Math.abs(last.cy - first.cy) < ILLEGAL_STOP_THRESHOLD) {
        if (last.cx > nL && last.cx < eL && last.cy > nL && last.cy < sL) {
          stoppedTracks.push({ trackId, cx: last.cx, cy: last.cy })
        }
      }
    }
    if (stoppedTracks.length >= ACCIDENT_MIN_STOPPED) {
      for (let i = 0; i < stoppedTracks.length; i++) {
        let nearbyCount = 0
        for (let j = 0; j < stoppedTracks.length; j++) {
          if (i === j) continue
          if (Math.hypot(stoppedTracks[i].cx - stoppedTracks[j].cx, stoppedTracks[i].cy - stoppedTracks[j].cy) < ACCIDENT_DISTANCE_THRESHOLD)
            nearbyCount++
        }
        if (nearbyCount >= ACCIDENT_MIN_STOPPED - 1) {
          const recentAccident = trafficEvents.value.find(
            e => e.type === 'accident_suspect' && now - e.timestamp < 15000
          )
          if (!recentAccident) {
            addEvent({
              type: 'accident_suspect',
              severity: 'danger',
              message: `疑似交通事故：${nearbyCount + 1}辆车聚集停止`,
              timestamp: now,
              position: { cx: stoppedTracks[i].cx, cy: stoppedTracks[i].cy },
            })
          }
          break
        }
      }
    }
  }

  // ========================================
  // 核心 processFrame
  // 每帧调用，全精度计算；UI 数据 10Hz 刷新
  // ========================================
  function processFrame(tracks: Track[], fps?: number) {
    const now = Date.now()
    if (fps) currentFps = fps
    if (detectionStartTime.value === 0) detectionStartTime.value = now
    totalFrames++

    const currentIds = new Set<number>()

    // 热路径：方向车辆计数 → 纯 JS
    _dirVehicles.north = 0
    _dirVehicles.south = 0
    _dirVehicles.east = 0
    _dirVehicles.west = 0

    // 占有率：本帧是否覆盖检测线
    const lineOccupiedThisFrame: Record<string, boolean> = {}
    for (const line of virtualLines.value) {
      lineOccupiedThisFrame[line.id] = false
    }

    for (const track of tracks) {
      currentIds.add(track.track_id)
      const cx = (track.bbox[0] + track.bbox[2]) / 2
      const cy = (track.bbox[1] + track.bbox[3]) / 2

      // 首次出现时间
      if (!trackFirstSeen.has(track.track_id)) {
        trackFirstSeen.set(track.track_id, now)
      }

      // 位置历史（最多 60 帧 ≈ 2s）
      let posHistory = trackPositionHistory.get(track.track_id)
      if (!posHistory) {
        posHistory = []
        trackPositionHistory.set(track.track_id, posHistory)
      }
      posHistory.push({ cx, cy, t: now })
      if (posHistory.length > 60) posHistory.shift()

      // 方向分区 → 热路径
      if (cy < 0.3) _dirVehicles.north++
      else if (cy > 0.7) _dirVehicles.south++
      if (cx < 0.3) _dirVehicles.west++
      else if (cx > 0.7) _dirVehicles.east++

      // 占有率检测
      for (const line of virtualLines.value) {
        const isH = line.orientation === 'horizontal'
        if (isH) {
          if (track.bbox[1] <= line.position && track.bbox[3] >= line.position)
            lineOccupiedThisFrame[line.id] = true
        } else {
          if (track.bbox[0] <= line.position && track.bbox[2] >= line.position)
            lineOccupiedThisFrame[line.id] = true
        }
      }

      // 穿越检测（事件驱动：仅穿越时触发响应式更新，频率很低）
      const prev = trackHistory.get(track.track_id)
      if (prev) {
        for (const line of virtualLines.value) {
          const isH = line.orientation === 'horizontal'
          const prevVal = isH ? prev.cy : prev.cx
          const currVal = isH ? cy : cx
          if ((prevVal < line.position) !== (currVal < line.position)) {
            const direction: 'positive' | 'negative' = currVal > prevVal ? 'positive' : 'negative'
            _totalCrossedCount++
            totalCrossedRef.value = _totalCrossedCount
            crossings.value.push({
              lineId: line.id,
              trackId: track.track_id,
              classId: track.class_id,
              className: track.class_name || CLASS_LABELS[track.class_id] || `class_${track.class_id}`,
              direction,
              timestamp: now,
            })
            // 限制数组大小，保留最近 200 条（导出报告用）
            if (crossings.value.length > 200) crossings.value.shift()
            classCounts[track.class_id] = (classCounts[track.class_id] || 0) + 1
            if (!lineCounts[line.id]) lineCounts[line.id] = { positive: 0, negative: 0 }
            lineCounts[line.id][direction]++
            bucketCrossingCount++

            checkWrongWay(line.id, line.name, direction, track.track_id, cx, cy, now)

            // 转向分析
            const lineName = line.id.replace('line-', '')
            const existingEntry = trackEntryLine.get(track.track_id)
            if (!existingEntry) {
              trackEntryLine.set(track.track_id, lineName)
            } else if (existingEntry !== lineName) {
              turns.value.push({
                trackId: track.track_id,
                classId: track.class_id,
                className: track.class_name || CLASS_LABELS[track.class_id] || `class_${track.class_id}`,
                entryLine: existingEntry,
                exitLine: lineName,
                turnType: classifyTurn(existingEntry, lineName),
                timestamp: now,
              })
              trackEntryLine.delete(track.track_id)
            }
          }
        }
      }
      trackHistory.set(track.track_id, { cy, cx })
    }

    // 占有率缓冲 → 热路径
    for (const line of virtualLines.value) {
      if (!_lineOccBuf[line.id]) _lineOccBuf[line.id] = []
      _lineOccBuf[line.id].push(lineOccupiedThisFrame[line.id])
      if (_lineOccBuf[line.id].length > OCCUPANCY_WINDOW) {
        _lineOccBuf[line.id].shift()
      }
    }

    // 排队车辆 → 热路径
    computeQueueVehicles(tracks)

    // 清理已消失轨迹
    for (const [id] of trackHistory) {
      if (!currentIds.has(id)) {
        trackHistory.delete(id)
        const firstSeen = trackFirstSeen.get(id)
        if (firstSeen) {
          trackDwellTimes.value.push(now - firstSeen)
          if (trackDwellTimes.value.length > 200) trackDwellTimes.value.shift()
          trackFirstSeen.delete(id)
        }
        trackPositionHistory.delete(id)
        trackEntryLine.delete(id)
        triggeredStopEvents.delete(id)
        triggeredWrongWayEvents.delete(id)
      }
    }

    // 事件检测（每 30 帧）
    if (totalFrames % 30 === 0) {
      checkEvents(tracks, now)
    }

    // 时间序列桶（增量计数，不再 filter 全量数组）
    const bucketMs = 2000
    if (now - lastBucketTime >= bucketMs) {
      lastBucketTime = now
      const timeStr = new Date(now).toLocaleTimeString('zh-CN', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      })
      flowTimeSeries.value.push({ time: timeStr, count: bucketCrossingCount })
      bucketCrossingCount = 0
      if (flowTimeSeries.value.length > 60) flowTimeSeries.value.shift()
    }

    // ★ 10Hz 刷新：热路径 → 响应式
    flushToReactive(now)
  }

  const detectionDuration = computed(() => {
    if (detectionStartTime.value === 0) return 0
    return (Date.now() - detectionStartTime.value) / 1000
  })

  function reset() {
    trackHistory.clear()
    crossings.value = []
    _totalCrossedCount = 0
    totalCrossedRef.value = 0
    Object.keys(classCounts).forEach(k => { classCounts[Number(k)] = 0 })
    Object.keys(lineCounts).forEach(k => delete lineCounts[k])
    flowTimeSeries.value = []
    lastBucketTime = 0
    bucketCrossingCount = 0
    trackEntryLine.clear()
    turns.value = []
    trackFirstSeen.clear()
    trackDwellTimes.value = []
    detectionStartTime.value = 0
    totalFrames = 0
    _dirVehicles.north = _dirVehicles.south = _dirVehicles.east = _dirVehicles.west = 0
    _queueVehicles.north = _queueVehicles.south = _queueVehicles.east = _queueVehicles.west = 0
    directionVehicleCounts.north = directionVehicleCounts.south = directionVehicleCounts.east = directionVehicleCounts.west = 0
    queueVehiclesByDirection.north = queueVehiclesByDirection.south = queueVehiclesByDirection.east = queueVehiclesByDirection.west = 0
    Object.keys(_lineOccBuf).forEach(k => delete _lineOccBuf[k])
    occupancySnapshot.value = {}
    lastFlushTime = 0
    trackPositionHistory.clear()
    trafficEvents.value = []
    eventIdCounter = 0
    triggeredStopEvents.clear()
    triggeredWrongWayEvents.clear()
  }

  function clearEvents() {
    trafficEvents.value = []
  }

  return {
    virtualLines,
    crossings,
    classCounts,
    lineCounts,
    totalCrossed,
    flowTimeSeries,
    directionSummary,
    turns,
    turnSummary,
    TURN_LABELS,
    queueLengthByDirection,
    maxQueueLength,
    occupancyByLine,
    avgOccupancy,
    avgDelay,
    serviceLevelGrade,
    serviceLevelColor,
    directionVehicleCounts,
    detectionDuration,
    trafficEvents,
    processFrame,
    reset,
    clearEvents,
  }
})
