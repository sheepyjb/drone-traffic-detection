# Drone Traffic Detection System

基于无人机视角的实时交通目标检测与交通流分析系统。

## 功能特性

- **实时目标检测**：基于 YOLO26 模型，支持 5 类交通目标（car / truck / bus / van / freight_car）
- **多目标跟踪**：集成 ByteTrack 算法，实现稳定的多目标在线跟踪
- **多模态融合**：支持 RGB 单模态与 RGB+IR 双模态融合检测
- **交通流分析**：虚拟线圈计数、分方向流量统计、排队长度估计、转向比例分析
- **事件预警**：逆行检测、异常停车、拥堵预警等智能交通事件识别
- **地图监控**：视频流叠加 HUD 信息，配合 ECharts 实时数据看板

## 技术栈

| 层级 | 技术 |
|------|------|
| 检测模型 | YOLO26 (Ultralytics) |
| 跟踪算法 | ByteTrack |
| 后端框架 | FastAPI + WebSocket |
| 前端框架 | Vue 3 + TypeScript + Element Plus |
| 图表可视化 | ECharts |
| 数据集 | DroneVehicle |

## 项目结构

```
├── backend/
│   ├── api/
│   │   ├── routes.py          # REST API 路由
│   │   ├── websocket.py       # WebSocket 视频流处理
│   │   └── traffic_routes.py  # 交通分析 API
│   ├── models/
│   │   ├── detector.py        # YOLO 检测器封装
│   │   └── tracker.py         # ByteTrack 跟踪器
│   ├── services/              # 业务逻辑
│   ├── config.py              # 配置文件
│   ├── main.py                # 后端入口
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/             # 页面组件
│   │   ├── components/        # UI 组件
│   │   ├── stores/            # Pinia 状态管理
│   │   ├── composables/       # 组合式函数
│   │   └── types/             # TypeScript 类型定义
│   ├── package.json
│   └── vite.config.ts
├── scripts/                   # 训练/数据处理脚本
├── deploy/                    # 部署配置
└── README.md
```

## 快速开始

### 环境要求

- Python 3.10+（需要 PyTorch + CUDA）
- Node.js 18+
- NVIDIA GPU（推荐 RTX 4050 及以上）

### 模型权重

将以下模型文件放在项目根目录：

| 文件 | 说明 |
|------|------|
| `ep00_best.pt` | RGB 单模态检测模型 |
| `ep01_best(1).pt` | RGB+IR 双模态融合模型 |

### 后端启动

```bash
cd backend
pip install -r requirements.txt
python main.py
# 服务运行在 http://localhost:8000
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## 性能优化

系统针对实时视频流场景做了全链路性能优化：

- **后端**：漏桶算法匀速帧发送、跳帧推理（INFER_INTERVAL=2）、异步 FrameReader
- **前端**：shallowRef 避免深度代理、requestAnimationFrame 渲染对齐、HUD 节流 200ms、ECharts 节流 500ms
- **状态管理**：hot/cold path 分离，高频数据用普通变量，低频 flush 到响应式状态

## 赛题背景

第 17 届中国大学生服务外包创新创业大赛 A 类赛题（杭州师范大学 — 多模态小目标检测）
