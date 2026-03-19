"""视频/图片处理服务 — 无人机交通检测"""
import cv2
import base64
import numpy as np
from pathlib import Path
from typing import Optional

from config import VEHICLE_CLASSES


def read_image_file(file_bytes: bytes) -> np.ndarray:
    """从上传的字节读取为 numpy 图像"""
    arr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def encode_frame_base64(frame: np.ndarray, quality: int = 70) -> str:
    """将帧编码为 base64 JPEG"""
    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf).decode('utf-8')


# 交通目标颜色 (BGR)，从 VEHICLE_CLASSES hex 转换
def _hex_to_bgr(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (b, g, r)

_VEHICLE_COLORS = {
    i: _hex_to_bgr(v["color"]) for i, v in VEHICLE_CLASSES.items()
}


def draw_detections(frame: np.ndarray, tracks: list[dict], class_colors: Optional[dict] = None) -> np.ndarray:
    """在帧上绘制检测框"""
    h, w = frame.shape[:2]
    result = frame.copy()
    colors = class_colors or _VEHICLE_COLORS

    for t in tracks:
        bbox = t["bbox"]
        x1, y1, x2, y2 = int(bbox[0] * w), int(bbox[1] * h), int(bbox[2] * w), int(bbox[3] * h)
        cls_id = t["class_id"]
        color = colors.get(cls_id, (200, 200, 200))
        conf = t["confidence"]
        tid = t.get("track_id", 0)
        name = t.get("class_name", str(cls_id))

        # 检测框
        cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)

        # 标签
        label = f"#{tid} {name} {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        ly = max(y1 - 6, th + 4)
        cv2.rectangle(result, (x1, ly - th - 4), (x1 + tw + 6, ly + 2), color, -1)
        cv2.putText(result, label, (x1 + 3, ly - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return result


def get_video_info(video_path: str) -> dict:
    """获取视频基本信息"""
    cap = cv2.VideoCapture(video_path)
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": round(cap.get(cv2.CAP_PROP_FPS), 1),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "duration_s": round(
            cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1), 1
        ),
    }
    cap.release()
    return info


def save_detection_json(tracks, save_path: str):
    """保存检测结果为 JSON"""
    import json
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(tracks, f, ensure_ascii=False, indent=2)


def save_detection_image(frame: np.ndarray, tracks: list[dict], save_path: str):
    """保存标注后的图片"""
    annotated = draw_detections(frame, tracks)
    cv2.imwrite(save_path, annotated)
    return save_path
