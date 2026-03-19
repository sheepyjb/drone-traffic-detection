// ===== 检测相关 =====
export interface Track {
  track_id: number
  class_id: number
  class_name: string
  bbox: [number, number, number, number] // [x1, y1, x2, y2] 归一化坐标
  confidence: number
  age: number
  mask?: number[][] | null // 可选，交通检测通常不需要
}

export interface DetectionFrame {
  frame: string       // base64 JPEG
  frame_id: number
  timestamp: number
  fps: number
  latency_ms: number
  tracks: Track[]
}

// ===== WebSocket 消息 =====
export interface WsDetectionMessage {
  type: 'detection'
  frame: string
  frame_id: number
  timestamp: number
  fps: number
  latency_ms: number
  tracks: Track[]
}

export interface WsStatusMessage {
  type: 'status'
  connected: boolean
  model: string
}

export type WsMessage = WsDetectionMessage | WsStatusMessage

// ===== 模型信息 =====
export interface ModelInfo {
  id: string
  name: string
  description: string
  params: string
  gflops: number
  map50: number
  fps: number
}

// ===== 统计 =====
export interface DetectionStats {
  totalObjects: number
  categoryCounts: Record<number, number>
  fps: number
  latency: number
}

// ===== 类别定义 =====
export interface CategoryDef {
  id: number
  name: string
  label: string
  color: string
}

// ===== 评估指标 =====
export interface AblationRow {
  experiment: string
  backbone: string
  neck: string
  head: string
  map50: number
  map50_95: number
  fps: number
  params: string
}

export interface PRPoint {
  precision: number
  recall: number
}

export interface ClassAP {
  class_name: string
  class_label: string
  ap50: number
  ap50_95: number
}

// ===== 地图相关 =====
export interface DroneParams {
  lat: number
  lng: number
  altitude: number
  pitch: number
  hFov: number
  vFov: number
}

export interface GpsBounds {
  north: number
  south: number
  east: number
  west: number
}

export interface GpsPoint {
  lng: number
  lat: number
}

export interface MapVehicle {
  track_id: number
  class_id: number
  class_name: string
  confidence: number
  position: GpsPoint
}

// ===== 红绿灯 =====
export interface TrafficDirection {
  name: string
  label: string
  vehicleCount: number
  greenSeconds: number
}

export interface TrafficLightState {
  currentPhase: 'NS' | 'EW'
  greenRemaining: number
  cycleLength: number
  directions: TrafficDirection[]
  report: string
  // Webster 参数
  websterParams?: {
    totalLossTime: number       // L: 总损失时间
    sumFlowRatio: number        // Y: 流量比之和
    optimalCycle: number        // C₀: 最优周期
    saturationFlow: number      // 饱和流量 (veh/h/lane)
    phaseFlowRatios: { name: string; flowRatio: number; greenTime: number }[]
    estimatedDelayReduction: number  // 优化后预计减少延误 %
  }
}

// ===== 监管告警 =====
export interface RestrictedZone {
  id: string
  name: string
  polygon: GpsPoint[]
  restrictedClasses: number[]
  color: string
}

export interface ZoneAlert {
  id: string
  zoneName: string
  track_id: number
  class_name: string
  timestamp: number
  position: GpsPoint
}

export interface VehicleThreshold {
  classId: number
  threshold: number
}

// ===== 虚拟线圈流量统计 =====
export interface VirtualLine {
  id: string
  position: number         // 归一化坐标 (0-1)
  orientation: 'horizontal' | 'vertical'  // horizontal→Y轴检测线, vertical→X轴检测线
  name: string
  color: string
}

export interface LineCrossing {
  lineId: string
  trackId: number
  classId: number
  className: string
  direction: 'positive' | 'negative'  // positive=下穿/右穿, negative=上穿/左穿
  timestamp: number
}

// ===== 转向分析 =====
export type TurnType = 'straight' | 'left' | 'right' | 'uturn' | 'unknown'

export interface TrackTurn {
  trackId: number
  classId: number
  className: string
  entryLine: string    // 'north'|'south'|'east'|'west'
  exitLine: string
  turnType: TurnType
  timestamp: number
}

// ===== 交通事件预警 =====
export interface TrafficEvent {
  id: string
  type: 'wrong_way' | 'illegal_stop' | 'long_queue' | 'accident_suspect'
  severity: 'warning' | 'danger'
  message: string
  trackId?: number
  timestamp: number
  position?: { cx: number; cy: number }
}

// ===== 服务水平等级 =====
export type LOSGrade = 'A' | 'B' | 'C' | 'D' | 'E' | 'F'
