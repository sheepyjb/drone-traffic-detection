import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useDetectionStore } from './detection'
import { useFlowCountStore } from './flowCount'
import type {
  DroneParams,
  GpsBounds,
  GpsPoint,
  MapVehicle,
  TrafficLightState,
  TrafficDirection,
  RestrictedZone,
  ZoneAlert,
  VehicleThreshold,
} from '@/types'
import axios from 'axios'

export const useMapStore = defineStore('map', () => {
  const detectionStore = useDetectionStore()

  // ===== 无人机参数 =====
  const droneParams = ref<DroneParams>({
    lat: 30.2710,
    lng: 120.1000,
    altitude: 100,
    pitch: -90,
    hFov: 84,
    vFov: 62,
  })

  // ===== 限制区域 (demo) =====
  const restrictedZones = ref<RestrictedZone[]>([
    {
      id: 'zone-1',
      name: '禁行重车区',
      polygon: [
        { lng: 120.0990, lat: 30.2720 },
        { lng: 120.1000, lat: 30.2720 },
        { lng: 120.1000, lat: 30.2710 },
        { lng: 120.0990, lat: 30.2710 },
      ],
      restrictedClasses: [1, 4], // truck, freight_car
      color: '#EF4444',
    },
    {
      id: 'zone-2',
      name: '限速监控区',
      polygon: [
        { lng: 120.1005, lat: 30.2715 },
        { lng: 120.1015, lat: 30.2715 },
        { lng: 120.1015, lat: 30.2705 },
        { lng: 120.1005, lat: 30.2705 },
      ],
      restrictedClasses: [2], // bus
      color: '#F59E0B',
    },
  ])

  // ===== 信号灯 =====
  const trafficLightState = ref<TrafficLightState | null>(null)
  const lightTimerId = ref<number | null>(null)

  // ===== 告警 =====
  const alerts = ref<ZoneAlert[]>([])

  // ===== 阈值 =====
  const thresholds = ref<VehicleThreshold[]>([
    { classId: 0, threshold: 20 },
    { classId: 1, threshold: 5 },
    { classId: 2, threshold: 3 },
    { classId: 3, threshold: 8 },
    { classId: 4, threshold: 3 },
  ])

  // ===== Computed: GPS Bounds =====
  const gpsBounds = computed<GpsBounds>(() => {
    const p = droneParams.value
    const hFovRad = (p.hFov * Math.PI) / 360 // half FOV
    const vFovRad = (p.vFov * Math.PI) / 360
    const groundWidth = 2 * p.altitude * Math.tan(hFovRad)
    const groundHeight = 2 * p.altitude * Math.tan(vFovRad)
    const dLat = groundHeight / 111320
    const dLng = groundWidth / (111320 * Math.cos((p.lat * Math.PI) / 180))
    return {
      north: p.lat + dLat / 2,
      south: p.lat - dLat / 2,
      east: p.lng + dLng / 2,
      west: p.lng - dLng / 2,
    }
  })

  // ===== Computed: Mapped Vehicles =====
  const mappedVehicles = computed<MapVehicle[]>(() => {
    const tracks = detectionStore.tracks
    if (!tracks.length) return []
    const b = gpsBounds.value
    return tracks.map((t) => {
      const cx = (t.bbox[0] + t.bbox[2]) / 2
      const cy = (t.bbox[1] + t.bbox[3]) / 2
      return {
        track_id: t.track_id,
        class_id: t.class_id,
        class_name: t.class_name,
        confidence: t.confidence,
        position: {
          lng: b.west + cx * (b.east - b.west),
          lat: b.north - cy * (b.north - b.south),
        },
      }
    })
  })

  // ===== Computed: Direction Counts =====
  const directionCounts = computed(() => {
    const counts = { north: 0, south: 0, east: 0, west: 0 }
    for (const v of mappedVehicles.value) {
      const cx = (v.position.lng - gpsBounds.value.west) / (gpsBounds.value.east - gpsBounds.value.west)
      const cy = (gpsBounds.value.north - v.position.lat) / (gpsBounds.value.north - gpsBounds.value.south)
      if (cy < 0.5) counts.north++
      else counts.south++
      if (cx < 0.5) counts.west++
      else counts.east++
    }
    return counts
  })

  // ===== Computed: Threshold Alerts =====
  const thresholdAlerts = computed(() => {
    const result: { classId: number; className: string; count: number; threshold: number }[] = []
    const cc = detectionStore.categoryCounts
    for (const th of thresholds.value) {
      const count = cc[th.classId] || 0
      if (count >= th.threshold) {
        const cat = detectionStore.categories.find((c) => c.id === th.classId)
        result.push({
          classId: th.classId,
          className: cat?.label || `Class ${th.classId}`,
          count,
          threshold: th.threshold,
        })
      }
    }
    return result
  })

  // ===== Actions =====

  /**
   * Webster 最优信号配时算法（纯前端计算）
   * C₀ = (1.5L + 5) / (1 - Y)
   * L = 总损失时间（黄灯+启动损失）
   * Y = Σyᵢ, yᵢ = qᵢ / sᵢ
   * gᵢ = (yᵢ / Y) × (C₀ - L)
   */
  function analyzeTrafficWebster() {
    const flowCountStore = useFlowCountStore()
    const dirSummary = flowCountStore.directionSummary
    const duration = flowCountStore.detectionDuration // 秒

    // 两相位：NS（南北）和 EW（东西）
    const SATURATION_FLOW = 1800 // 饱和流量 veh/h/lane
    const PHASES = 2
    const LOSS_PER_PHASE = 4 // 每相位损失时间(s)：黄灯3s + 启动损失1s
    const L = LOSS_PER_PHASE * PHASES // 总损失时间
    const MIN_GREEN = 10 // 最小绿灯时间
    const MAX_CYCLE = 120 // 最大周期

    // 将过线数转换为小时流量 (veh/h)
    const effectiveDuration = Math.max(duration, 10) // 至少10秒，避免除零
    const hourFactor = 3600 / effectiveDuration

    // NS相位流量 = max(北侧, 南侧)
    const qNS = Math.max(dirSummary.north, dirSummary.south) * hourFactor
    // EW相位流量 = max(东侧, 西侧)
    const qEW = Math.max(dirSummary.east, dirSummary.west) * hourFactor

    // 各相位流量比
    const yNS = Math.min(qNS / SATURATION_FLOW, 0.95)
    const yEW = Math.min(qEW / SATURATION_FLOW, 0.95)
    const Y = yNS + yEW

    let optimalCycle: number
    let gNS: number
    let gEW: number

    if (Y >= 0.95) {
      // 过饱和，使用最大周期
      optimalCycle = MAX_CYCLE
      const effectiveGreen = optimalCycle - L
      gNS = Math.round(effectiveGreen * (yNS / (yNS + yEW)))
      gEW = effectiveGreen - gNS
    } else if (Y <= 0.01) {
      // 流量太小，给默认值
      optimalCycle = 40
      gNS = 15
      gEW = 15
    } else {
      // Webster 公式
      optimalCycle = Math.round((1.5 * L + 5) / (1 - Y))
      optimalCycle = Math.min(Math.max(optimalCycle, 30), MAX_CYCLE)
      const effectiveGreen = optimalCycle - L
      gNS = Math.max(Math.round((yNS / Y) * effectiveGreen), MIN_GREEN)
      gEW = Math.max(effectiveGreen - gNS, MIN_GREEN)
      // 如果调整后超出，重算周期
      if (gNS + gEW + L > MAX_CYCLE) {
        gNS = Math.round((MAX_CYCLE - L) * (yNS / Y))
        gEW = MAX_CYCLE - L - gNS
      }
    }

    // 估算延误减少：使用简化的 Webster 延误公式
    // 优化前假设固定配时 60s 周期
    const defaultCycle = 60
    const defaultGreen = (defaultCycle - L) / 2
    const delayBefore = estimateDelay(defaultCycle, defaultGreen, qNS, SATURATION_FLOW)
      + estimateDelay(defaultCycle, defaultGreen, qEW, SATURATION_FLOW)
    const delayAfter = estimateDelay(optimalCycle, gNS, qNS, SATURATION_FLOW)
      + estimateDelay(optimalCycle, gEW, qEW, SATURATION_FLOW)
    const delayReduction = delayBefore > 0
      ? Math.round(((delayBefore - delayAfter) / delayBefore) * 100)
      : 0

    const DIR_LABELS: Record<string, string> = { north: '北', south: '南', east: '东', west: '西' }

    const directions: TrafficDirection[] = [
      { name: 'north', label: DIR_LABELS.north, vehicleCount: dirSummary.north, greenSeconds: gNS },
      { name: 'south', label: DIR_LABELS.south, vehicleCount: dirSummary.south, greenSeconds: gNS },
      { name: 'east',  label: DIR_LABELS.east,  vehicleCount: dirSummary.east,  greenSeconds: gEW },
      { name: 'west',  label: DIR_LABELS.west,  vehicleCount: dirSummary.west,  greenSeconds: gEW },
    ]

    let report = `=== Webster 最优配时分析 ===\n`
    report += `检测时长: ${effectiveDuration.toFixed(0)}s\n`
    report += `饱和流量: ${SATURATION_FLOW} veh/h/lane\n\n`
    report += `南北相位流量: ${Math.round(qNS)} veh/h (y=${yNS.toFixed(3)})\n`
    report += `东西相位流量: ${Math.round(qEW)} veh/h (y=${yEW.toFixed(3)})\n`
    report += `总流量比 Y = ${Y.toFixed(3)}\n`
    report += `总损失时间 L = ${L}s\n\n`
    report += `最优周期 C₀ = ${optimalCycle}s\n`
    report += `南北绿灯: ${gNS}s | 东西绿灯: ${gEW}s\n`
    if (delayReduction > 0) {
      report += `\n预计较固定配时减少延误 ${delayReduction}%`
    }

    trafficLightState.value = {
      currentPhase: 'NS',
      greenRemaining: gNS,
      cycleLength: optimalCycle,
      directions,
      report,
      websterParams: {
        totalLossTime: L,
        sumFlowRatio: Y,
        optimalCycle,
        saturationFlow: SATURATION_FLOW,
        phaseFlowRatios: [
          { name: '南北', flowRatio: yNS, greenTime: gNS },
          { name: '东西', flowRatio: yEW, greenTime: gEW },
        ],
        estimatedDelayReduction: Math.max(delayReduction, 0),
      },
    }

    startLightCycle()
  }

  /** Webster 均匀延误近似: d = C(1-λ)² / 2(1-λx) */
  function estimateDelay(cycle: number, green: number, flow: number, satFlow: number): number {
    const lambda = green / cycle  // 绿信比
    const x = flow / (satFlow * lambda + 0.01) // 饱和度
    if (x >= 1) return cycle // 过饱和
    const d = (cycle * Math.pow(1 - lambda, 2)) / (2 * (1 - lambda * Math.min(x, 0.99)))
    return Math.max(d, 0)
  }

  async function analyzeTraffic() {
    // 优先使用前端 Webster 计算
    const flowCountStore = useFlowCountStore()
    if (flowCountStore.totalCrossed > 0) {
      analyzeTrafficWebster()
      return
    }

    // Fallback: 后端 API
    const vehicles = mappedVehicles.value.map((v) => ({
      track_id: v.track_id,
      class_id: v.class_id,
      class_name: v.class_name,
      confidence: v.confidence,
      cx: (v.position.lng - gpsBounds.value.west) / (gpsBounds.value.east - gpsBounds.value.west),
      cy: (gpsBounds.value.north - v.position.lat) / (gpsBounds.value.north - gpsBounds.value.south),
    }))
    try {
      const { data } = await axios.post('/api/traffic/analyze', {
        vehicles,
        bounds: gpsBounds.value,
      })
      trafficLightState.value = data
      startLightCycle()
    } catch (e) {
      console.error('Traffic analyze failed, falling back to Webster:', e)
      // API 失败也用 Webster
      analyzeTrafficWebster()
    }
  }

  async function checkZoneViolations() {
    const vehicles = mappedVehicles.value.map((v) => ({
      track_id: v.track_id,
      class_id: v.class_id,
      class_name: v.class_name,
      position: v.position,
    }))
    try {
      const { data } = await axios.post('/api/traffic/zone-check', {
        vehicles,
        zones: restrictedZones.value,
      })
      if (data.alerts && data.alerts.length) {
        alerts.value = [...data.alerts, ...alerts.value].slice(0, 100)
      }
      return data.alerts || []
    } catch (e) {
      console.error('Zone check failed:', e)
      return []
    }
  }

  function startLightCycle() {
    stopLightCycle()
    if (!trafficLightState.value) return
    lightTimerId.value = window.setInterval(() => {
      const s = trafficLightState.value
      if (!s) return
      s.greenRemaining--
      if (s.greenRemaining <= 0) {
        s.currentPhase = s.currentPhase === 'NS' ? 'EW' : 'NS'
        const dir = s.directions.find(
          (d) => d.name === (s.currentPhase === 'NS' ? 'north' : 'east')
        )
        s.greenRemaining = dir?.greenSeconds || 30
      }
    }, 1000)
  }

  function stopLightCycle() {
    if (lightTimerId.value !== null) {
      clearInterval(lightTimerId.value)
      lightTimerId.value = null
    }
  }

  function clearAlerts() {
    alerts.value = []
  }

  return {
    droneParams,
    restrictedZones,
    trafficLightState,
    alerts,
    thresholds,
    gpsBounds,
    mappedVehicles,
    directionCounts,
    thresholdAlerts,
    analyzeTraffic,
    checkZoneViolations,
    startLightCycle,
    stopLightCycle,
    clearAlerts,
  }
})
