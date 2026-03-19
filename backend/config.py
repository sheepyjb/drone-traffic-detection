"""全局配置 — 无人机交通检测系统
自动适配 Windows 本地 / Linux 服务器(AutoDL)
通过环境变量 PROJECT_ROOT 覆盖项目根目录
"""
import os
import platform
from pathlib import Path

# ===== 项目路径（自动适配） =====
_default_root = Path(r"D:/服创") if platform.system() == "Windows" else Path("/root/autodl-tmp")
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", str(_default_root)))
BACKEND_DIR = PROJECT_ROOT / "backend"
ULTRALYTICS_DIR = PROJECT_ROOT / "yolo26-main" / "ultralytics-main"

# 模型路径
MODEL_DIR = PROJECT_ROOT / "runs"
DEFAULT_MODEL = str(PROJECT_ROOT / "ep00_best.pt")
PRETRAINED_MODELS = {
    "yolo26s-rgb": str(PROJECT_ROOT / "ep00_best.pt"),
    "yolo26s-fusion": str(PROJECT_ROOT / "ep01_best(1).pt"),
    "yolo26m-baseline": str(PROJECT_ROOT / "yolo26-main" / "yolo26m.pt"),
}

# DroneVehicle 5类交通目标
VEHICLE_CLASSES = {
    0: {"name": "car", "label": "小汽车", "color": "#3B82F6"},
    1: {"name": "truck", "label": "货车", "color": "#EF4444"},
    2: {"name": "bus", "label": "大巴", "color": "#10B981"},
    3: {"name": "van", "label": "厢式货车", "color": "#F59E0B"},
    4: {"name": "freight_car", "label": "货运车", "color": "#8B5CF6"},
}

# 上传和结果目录
UPLOAD_DIR = BACKEND_DIR / "uploads"
RESULT_DIR = BACKEND_DIR / "results"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# 推理配置
DEFAULT_CONF = 0.25
DEFAULT_IOU = 0.45
DEFAULT_IMGSZ = 640
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB

# 服务器配置
HOST = "0.0.0.0"
PORT = 8000

# EMA 平滑系数
EMA_ALPHA = 0.7
