"""YOLO 检测器封装 — 无人机交通目标检测"""
import sys
import time
import cv2
import numpy as np
from pathlib import Path
from typing import Optional

# 注入 ultralytics 路径
from config import ULTRALYTICS_DIR, DEFAULT_MODEL, DEFAULT_CONF, DEFAULT_IOU, DEFAULT_IMGSZ
sys.path.insert(0, str(ULTRALYTICS_DIR))

from ultralytics import YOLO


class Detector:
    """YOLO26 检测器，支持检测和跟踪"""

    def __init__(self, model_path: str = DEFAULT_MODEL):
        self.model_path = model_path
        self.model: Optional[YOLO] = None
        self.conf = DEFAULT_CONF
        self.iou = DEFAULT_IOU
        self.imgsz = DEFAULT_IMGSZ
        self._load_model()

    def _load_model(self):
        print(f"[Detector] Loading model: {self.model_path}")
        self.model = YOLO(self.model_path)
        print(f"[Detector] Model loaded. Classes: {self.model.names}")
        self._warmup()

    @property
    def is_fusion(self) -> bool:
        """检查模型是否为6通道融合模型（第一层 Conv2d in_channels == 6）"""
        try:
            first_layer = self.model.model.model[0]
            if hasattr(first_layer, 'conv'):
                return first_layer.conv.in_channels == 6
        except (AttributeError, IndexError):
            pass
        return False

    def _fuse_inputs(self, rgb: np.ndarray, ir: np.ndarray) -> np.ndarray:
        """将 RGB 和 IR 图像拼接为6通道输入"""
        h, w = rgb.shape[:2]
        if ir.shape[:2] != (h, w):
            ir = cv2.resize(ir, (w, h))
        return np.concatenate([rgb, ir], axis=2)

    def _warmup(self, runs: int = 5):
        """CUDA warmup：用随机数据预热推理管线，消除前几帧卡顿"""
        ch = 6 if self.is_fusion else 3
        dummy = np.random.randint(0, 255, (self.imgsz, self.imgsz, ch), dtype=np.uint8)
        print(f"[Detector] Warming up ({runs} runs)...")
        for _ in range(runs):
            self.model.predict(source=dummy, imgsz=self.imgsz, half=True, verbose=False)
        print(f"[Detector] Warmup complete, device={self.model.device}")

    def switch_model(self, model_path: str):
        self.model_path = model_path
        self._load_model()

    def detect(self, source, source_ir=None, conf: Optional[float] = None,
               iou: Optional[float] = None, save: bool = False,
               save_dir: Optional[str] = None) -> list:
        if self.is_fusion and source_ir is not None:
            source = self._fuse_inputs(source, source_ir)
        t0 = time.time()
        results = self.model.predict(
            source=source,
            conf=conf or self.conf,
            iou=iou or self.iou,
            imgsz=self.imgsz,
            half=True,
            verbose=False,
            save=save,
            project=save_dir,
        )
        latency = (time.time() - t0) * 1000
        return self._parse_results(results, latency)

    def track(self, source, source_ir=None, conf: Optional[float] = None,
              persist: bool = True) -> list:
        if self.is_fusion and source_ir is not None:
            source = self._fuse_inputs(source, source_ir)
        t0 = time.time()
        results = self.model.track(
            source=source,
            conf=conf or self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            half=True,
            persist=persist,
            verbose=False,
            tracker="bytetrack.yaml",
        )
        latency = (time.time() - t0) * 1000
        return self._parse_results(results, latency)

    def detect_video(self, video_path: str, save: bool = True, save_dir: Optional[str] = None) -> dict:
        t0 = time.time()
        results = self.model.predict(
            source=video_path,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            half=True,
            save=save,
            project=save_dir or str(Path("results")),
            verbose=False,
        )
        total_time = time.time() - t0
        total_objects = 0
        frame_count = 0
        class_counts: dict[int, int] = {}
        for r in results:
            frame_count += 1
            boxes = r.boxes
            if boxes is not None:
                total_objects += len(boxes)
                for cls_id in boxes.cls.cpu().numpy().astype(int):
                    class_counts[int(cls_id)] = class_counts.get(int(cls_id), 0) + 1

        return {
            "frames": frame_count,
            "total_objects": total_objects,
            "class_counts": class_counts,
            "total_time_s": round(total_time, 2),
            "avg_fps": round(frame_count / total_time, 1) if total_time > 0 else 0,
        }

    def _parse_results(self, results, latency_ms: float) -> list:
        """将 ultralytics Results 解析为标准 dict 列表"""
        parsed = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                parsed.append({"tracks": [], "latency_ms": round(latency_ms, 1)})
                continue

            # 检查是否有分割 mask（交通检测通常不需要，但保留兼容性）
            has_masks = hasattr(r, 'masks') and r.masks is not None
            masks_xyn = r.masks.xyn if has_masks else None

            tracks = []
            xyxy = boxes.xyxyn.cpu().numpy() if boxes.xyxyn is not None else np.zeros((0, 4))
            confs = boxes.conf.cpu().numpy() if boxes.conf is not None else np.zeros(0)
            cls_ids = boxes.cls.cpu().numpy().astype(int) if boxes.cls is not None else np.zeros(0, dtype=int)
            track_ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else None

            names = self.model.names or {}

            for i in range(len(cls_ids)):
                mask_poly = None
                if masks_xyn is not None and i < len(masks_xyn):
                    poly = masks_xyn[i]
                    if len(poly) > 0:
                        mask_poly = [[round(float(p[0]), 4), round(float(p[1]), 4)] for p in poly]

                track = {
                    "track_id": int(track_ids[i]) if track_ids is not None else i,
                    "class_id": int(cls_ids[i]),
                    "class_name": names.get(int(cls_ids[i]), str(cls_ids[i])),
                    "bbox": [float(v) for v in xyxy[i]],
                    "confidence": round(float(confs[i]), 3),
                    "age": 0,
                    "mask": mask_poly,
                }
                tracks.append(track)

            parsed.append({
                "tracks": tracks,
                "latency_ms": round(latency_ms / len(results), 1),
            })

        return parsed

    @property
    def class_names(self) -> dict:
        return self.model.names if self.model else {}
