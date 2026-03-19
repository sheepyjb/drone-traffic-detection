"""REST API 路由 — 无人机交通检测"""
import os
import json
import time
import shutil
import uuid
from pathlib import Path
from typing import Optional

import cv2
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse

from config import UPLOAD_DIR, RESULT_DIR, PRETRAINED_MODELS, VEHICLE_CLASSES
from services.video import (
    read_image_file, encode_frame_base64, draw_detections,
    get_video_info, save_detection_json, save_detection_image,
)
from services.metrics import get_model_metrics, get_ablation_data

router = APIRouter()

# 全局检测器引用 (由 main.py 注入)
_detector = None


def set_detector(det):
    global _detector
    _detector = det


def get_detector():
    if _detector is None:
        raise HTTPException(503, "Detector not initialized")
    return _detector


# ========== 模型 ==========

@router.get("/models")
async def list_models():
    """列出可用模型"""
    det = get_detector()
    models = []
    for mid, path in PRETRAINED_MODELS.items():
        models.append({
            "id": mid,
            "path": path,
            "exists": os.path.exists(path),
            "active": path == det.model_path,
            "is_fusion": mid == "yolo26s-fusion",
        })
    return {"models": models, "current": det.model_path, "class_names": det.class_names}


@router.post("/models/switch")
async def switch_model(model_id: str = Form(...)):
    """切换检测模型"""
    if model_id not in PRETRAINED_MODELS:
        raise HTTPException(400, f"Unknown model: {model_id}")
    path = PRETRAINED_MODELS[model_id]
    if not os.path.exists(path):
        raise HTTPException(404, f"Model file not found: {path}")
    det = get_detector()
    det.switch_model(path)
    return {"status": "ok", "model": model_id, "class_names": det.class_names}


# ========== 图片检测 ==========

@router.post("/detect/image")
async def detect_image(
    file: UploadFile = File(...),
    ir_file: UploadFile = File(None),
    conf: float = Query(0.25, ge=0.01, le=1.0),
    save: bool = Query(True),
):
    """单张图片交通目标检测（融合模型可附带红外图像）"""
    det = get_detector()
    contents = await file.read()
    img = read_image_file(contents)
    if img is None:
        raise HTTPException(400, "Cannot decode image")

    ir_img = None
    if ir_file is not None:
        ir_contents = await ir_file.read()
        ir_img = read_image_file(ir_contents)
        if ir_img is None:
            raise HTTPException(400, "Cannot decode IR image")

    results = det.detect(img, source_ir=ir_img, conf=conf)
    if not results:
        raise HTTPException(500, "Detection failed")

    result = results[0]
    tracks = result["tracks"]

    # 保存结果
    result_id = str(uuid.uuid4())[:8]
    response = {
        "result_id": result_id,
        "tracks": tracks,
        "object_count": len(tracks),
        "latency_ms": result["latency_ms"],
    }

    if save:
        save_dir = RESULT_DIR / result_id
        save_dir.mkdir(parents=True, exist_ok=True)
        annotated = draw_detections(img, tracks)
        img_path = str(save_dir / "annotated.jpg")
        cv2.imwrite(img_path, annotated)
        json_path = str(save_dir / "detections.json")
        save_detection_json(tracks, json_path)
        response["annotated_url"] = f"/api/results/{result_id}/annotated.jpg"
        response["json_url"] = f"/api/results/{result_id}/detections.json"

    response["frame_base64"] = encode_frame_base64(draw_detections(img, tracks))

    return response


# ========== 批量图片检测 ==========

@router.post("/detect/batch")
async def detect_batch(
    files: list[UploadFile] = File(...),
    conf: float = Query(0.25, ge=0.01, le=1.0),
    save: bool = Query(True),
):
    """批量交通目标检测"""
    det = get_detector()
    batch_id = str(uuid.uuid4())[:8]
    batch_dir = RESULT_DIR / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    total_objects = 0
    class_counts: dict[int, int] = {}

    for i, file in enumerate(files):
        contents = await file.read()
        img = read_image_file(contents)
        if img is None:
            all_results.append({"file": file.filename, "error": "Cannot decode image"})
            continue

        results = det.detect(img, conf=conf)
        if not results:
            all_results.append({"file": file.filename, "error": "Detection failed"})
            continue

        tracks = results[0]["tracks"]
        total_objects += len(tracks)
        for t in tracks:
            cid = t["class_id"]
            class_counts[cid] = class_counts.get(cid, 0) + 1

        entry = {
            "file": file.filename,
            "index": i,
            "tracks": tracks,
            "object_count": len(tracks),
            "latency_ms": results[0]["latency_ms"],
        }

        if save:
            annotated = draw_detections(img, tracks)
            fname = f"{i:04d}_{Path(file.filename).stem}.jpg"
            cv2.imwrite(str(batch_dir / fname), annotated)
            entry["saved_as"] = fname

        all_results.append(entry)

    summary = {
        "batch_id": batch_id,
        "total_images": len(files),
        "total_objects": total_objects,
        "class_counts": class_counts,
        "results": all_results,
    }
    if save:
        save_detection_json(summary, str(batch_dir / "summary.json"))

    return summary


# ========== CSV 导出 ==========

@router.post("/export/csv")
async def export_csv(tracks: list[dict]):
    """将检测结果导出为 CSV 文件"""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "类别ID", "类别名称", "置信度", "X1", "Y1", "X2", "Y2"])
    for t in tracks:
        bbox = t.get("bbox", [0, 0, 0, 0])
        writer.writerow([
            t.get("track_id", 0),
            t.get("class_id", 0),
            t.get("class_name", ""),
            round(t.get("confidence", 0), 3),
            round(bbox[0], 4), round(bbox[1], 4),
            round(bbox[2], 4), round(bbox[3], 4),
        ])

    from fastapi.responses import StreamingResponse
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=traffic_results.csv"},
    )


# ========== 视频检测 ==========

@router.post("/detect/upload")
async def upload_video(file: UploadFile = File(...)):
    """上传视频文件"""
    filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    save_path = UPLOAD_DIR / filename
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    info = get_video_info(str(save_path))
    return {"filename": filename, "path": str(save_path), **info}


@router.post("/detect/video")
async def detect_video(
    filename: str = Form(...),
    conf: float = Form(0.25),
    save: bool = Form(True),
):
    """对已上传的视频执行离线交通目标检测"""
    video_path = UPLOAD_DIR / filename
    if not video_path.exists():
        raise HTTPException(404, "Video not found")

    det = get_detector()
    result_id = str(uuid.uuid4())[:8]
    save_dir = str(RESULT_DIR / result_id) if save else None
    stats = det.detect_video(str(video_path), save=save, save_dir=save_dir)
    stats["result_id"] = result_id
    if save:
        stats["result_dir"] = save_dir
    return stats


@router.post("/detect/start")
async def start_detect(model: str = Form("yolo26s-rgb"), source: str = Form("upload")):
    """开始交通目标检测"""
    return {"status": "started", "model": model, "source": source}


@router.post("/detect/stop")
async def stop_detect():
    """停止检测"""
    return {"status": "stopped"}


# ========== 统计 ==========

# 交通目标配色 (从 VEHICLE_CLASSES 获取)
_DEFAULT_COLORS = [
    VEHICLE_CLASSES[i]["color"] for i in range(len(VEHICLE_CLASSES))
] + ['#F39C12', '#E91E63', '#00BCD4', '#FF5722', '#1ABC9C']


@router.get("/categories")
async def get_categories():
    """返回当前模型的类别列表"""
    det = get_detector()
    names = det.class_names
    categories = []
    for cid, name in names.items():
        # 优先使用 VEHICLE_CLASSES 中的 label 和 color
        vc = VEHICLE_CLASSES.get(int(cid))
        categories.append({
            "id": int(cid),
            "name": name,
            "label": vc["label"] if vc else name,
            "color": vc["color"] if vc else _DEFAULT_COLORS[int(cid) % len(_DEFAULT_COLORS)],
        })
    return {
        "categories": categories,
        "model": det.model_path,
    }


@router.get("/stats")
async def get_stats():
    """获取当前检测统计"""
    det = get_detector()
    return {
        "model": det.model_path,
        "class_names": det.class_names,
    }


# ========== 评估指标 ==========

@router.get("/metrics/{model_id}")
async def get_metrics(model_id: str):
    """获取模型评估指标"""
    return get_model_metrics(model_id)


@router.get("/metrics")
async def get_all_metrics():
    """获取所有模型指标 + 消融实验"""
    return {
        "ablation": get_ablation_data(),
        "models": {
            mid: get_model_metrics(mid) for mid in PRETRAINED_MODELS
        },
    }


# ========== 导出结果 ==========

@router.get("/results/{result_id}/{filename}")
async def get_result_file(result_id: str, filename: str):
    """获取检测结果文件"""
    file_path = RESULT_DIR / result_id / filename
    if not file_path.exists():
        file_path = RESULT_DIR / f"batch_{result_id}" / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(file_path))


@router.get("/results")
async def list_results():
    """列出所有检测结果"""
    results = []
    for d in RESULT_DIR.iterdir():
        if d.is_dir():
            files = [f.name for f in d.iterdir()]
            results.append({"id": d.name, "files": files})
    return {"results": results}
