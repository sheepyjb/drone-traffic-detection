"""FastAPI 后端入口 — 无人机交通检测系统"""
import sys
from pathlib import Path

# 确保可以导入本地模块
sys.path.insert(0, str(Path(__file__).parent))

from config import ULTRALYTICS_DIR, HOST, PORT

# 注入 ultralytics
sys.path.insert(0, str(ULTRALYTICS_DIR))

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from models.detector import Detector
from api.routes import router as api_router, set_detector
from api.websocket import ws_detect_handler
from api.traffic_routes import router as traffic_router
from config import RESULT_DIR, UPLOAD_DIR

# 创建 FastAPI 应用
app = FastAPI(
    title="无人机交通检测系统",
    description="基于 YOLO26 的无人机视角交通目标检测 API",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件 (检测结果可直接访问)
app.mount("/static/results", StaticFiles(directory=str(RESULT_DIR)), name="results")
app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# 初始化检测器
detector = Detector()
set_detector(detector)

# 注册 REST 路由
app.include_router(api_router, prefix="/api")
app.include_router(traffic_router, prefix="/api")


# WebSocket 端点
@app.websocket("/ws/detect")
async def websocket_detect(websocket: WebSocket):
    await ws_detect_handler(websocket, detector)


@app.get("/")
async def root():
    return {
        "service": "无人机交通检测系统 API",
        "version": "2.0.0",
        "model": detector.model_path,
        "classes": detector.class_names,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
