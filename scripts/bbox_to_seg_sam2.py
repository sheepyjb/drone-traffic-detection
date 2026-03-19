"""
GYU-DET bbox -> YOLO-seg 高精度批量转换脚本
使用 SAM2.1 Large ONNX 模型将 bbox 标注自动转换为 polygon mask

用法:
    D:/pytorch/python.exe D:/服创/scripts/bbox_to_seg_sam2.py

输出:
    D:/服创/GYU-DET/{split}/{split}/labels_seg/  (YOLO-seg 格式)
"""

import json
import glob
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# === 修复 CUDA DLL 路径 (Windows 中文环境) ===
import glob as _g
for _d in _g.glob("D:/pytorch/Lib/site-packages/nvidia/*/bin"):
    os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")

import onnxruntime as ort
ort.set_default_logger_severity(3)  # 抑制警告

from tqdm import tqdm


# ===================== 配置 =====================

PROJECT_ROOT = Path("D:/服创")
GYU_DET_DIR = PROJECT_ROOT / "GYU-DET"

# SAM2 Large = 最高精度; 如果显存不够可以换 base_plus
SAM2_ENCODER = str(PROJECT_ROOT / "models" / "sam2" / "sam2.1_hiera_large.encoder.onnx")
SAM2_DECODER = str(PROJECT_ROOT / "models" / "sam2" / "sam2.1_hiera_large.decoder.onnx")
# 备选 Base+:
# SAM2_ENCODER = str(PROJECT_ROOT / "models" / "sam2" / "sam2.1_hiera_base_plus.encoder.onnx")
# SAM2_DECODER = str(PROJECT_ROOT / "models" / "sam2" / "sam2.1_hiera_base_plus.decoder.onnx")

# GYU-DET 类别映射 (与 classes.txt 一致)
CLASS_MAP = {
    "crack": 0,
    "spalling": 1,
    "rebar_exposure": 2,
    "corrosion": 3,
    "efflorescence": 4,
    "water_seepage": 5,
}

# === 高精度参数 ===
EPSILON = 0.001          # 多边形简化系数 (越小越精细, 0.001 = 极精细)
MIN_CONTOUR_AREA = 50    # 最小轮廓面积 (像素), 过小的过滤
BBOX_PADDING = 0.05      # bbox 外扩比例 (5%), 给 SAM2 更多上下文
MIN_POLYGON_POINTS = 4   # 最少多边形顶点数

# 处理的数据集分割
SPLITS = ["train", "valid", "test"]


# ===================== 中文路径兼容 =====================

def cv2_imread(path_str):
    """支持中文路径的 imread"""
    data = np.fromfile(str(path_str), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return img


# ===================== SAM2 ONNX 推理 =====================

class SAM2ImageEncoder:
    def __init__(self, path: str, device: str = "gpu"):
        providers = ["CPUExecutionProvider"]
        if device.lower() == "gpu":
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        sess_options = ort.SessionOptions()
        sess_options.log_severity_level = 3
        self.session = ort.InferenceSession(path, providers=providers, sess_options=sess_options)
        # 确认实际使用的 provider
        actual = self.session.get_providers()
        print(f"  Encoder providers: {actual}")
        model_inputs = self.session.get_inputs()
        self.input_names = [inp.name for inp in model_inputs]
        self.input_shape = model_inputs[0].shape
        self.input_height = self.input_shape[2]
        self.input_width = self.input_shape[3]
        model_outputs = self.session.get_outputs()
        self.output_names = [out.name for out in model_outputs]

    def __call__(self, image: np.ndarray):
        input_img = cv2.resize(image, (self.input_width, self.input_height))
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        input_img = (input_img / 255.0 - mean) / std
        input_img = input_img.transpose(2, 0, 1)
        input_tensor = input_img[np.newaxis, :, :, :].astype(np.float32)
        outputs = self.session.run(self.output_names, {self.input_names[0]: input_tensor})
        return outputs[0], outputs[1], outputs[2]


class SAM2ImageDecoder:
    def __init__(self, path: str, device: str, encoder_input_size):
        providers = ["CPUExecutionProvider"]
        if device.lower() == "gpu":
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        sess_options = ort.SessionOptions()
        sess_options.log_severity_level = 3
        self.session = ort.InferenceSession(path, providers=providers, sess_options=sess_options)
        actual = self.session.get_providers()
        print(f"  Decoder providers: {actual}")
        self.encoder_input_size = encoder_input_size
        self.orig_im_size = encoder_input_size
        self.scale_factor = 4
        model_inputs = self.session.get_inputs()
        self.input_names = [inp.name for inp in model_inputs]
        model_outputs = self.session.get_outputs()
        self.output_names = [out.name for out in model_outputs]

    def set_image_size(self, orig_im_size):
        self.orig_im_size = orig_im_size

    def __call__(self, image_embed, high_res_feats_0, high_res_feats_1, point_coords, point_labels):
        input_point_coords = point_coords[np.newaxis, ...].copy().astype(np.float32)
        input_point_labels = point_labels[np.newaxis, ...].astype(np.float32)
        input_point_coords[..., 0] = input_point_coords[..., 0] / self.orig_im_size[1] * self.encoder_input_size[1]
        input_point_coords[..., 1] = input_point_coords[..., 1] / self.orig_im_size[0] * self.encoder_input_size[0]

        num_labels = input_point_labels.shape[0]
        mask_input = np.zeros(
            (num_labels, 1,
             self.encoder_input_size[0] // self.scale_factor,
             self.encoder_input_size[1] // self.scale_factor),
            dtype=np.float32,
        )
        has_mask_input = np.array([0], dtype=np.float32)

        inputs = (image_embed, high_res_feats_0, high_res_feats_1,
                  input_point_coords, input_point_labels, mask_input, has_mask_input)
        outputs = self.session.run(
            self.output_names,
            {self.input_names[i]: inputs[i] for i in range(len(self.input_names))},
        )
        scores = outputs[1].squeeze()
        masks = outputs[0][0]
        best_mask = masks[np.argmax(scores)]
        best_mask = cv2.resize(best_mask, (self.orig_im_size[1], self.orig_im_size[0]))
        return best_mask, scores


class SAM2:
    """SAM2 ONNX 封装"""
    def __init__(self, encoder_path, decoder_path, device="gpu"):
        print(f"Loading SAM2 encoder: {Path(encoder_path).name}")
        self.encoder = SAM2ImageEncoder(encoder_path, device)
        print(f"Loading SAM2 decoder: {Path(decoder_path).name}")
        self.decoder = SAM2ImageDecoder(decoder_path, device, self.encoder.input_shape[2:])
        print(f"SAM2 loaded! Input size: {self.encoder.input_shape}")

    def encode(self, cv_image):
        original_size = cv_image.shape[:2]
        hr0, hr1, embed = self.encoder(cv_image)
        return {
            "high_res_feats_0": hr0,
            "high_res_feats_1": hr1,
            "image_embedding": embed,
            "original_size": original_size,
        }

    def predict_mask(self, embedding, bbox, use_center_point=True):
        """用 bbox + 可选中心点 作为 prompt 预测高精度 mask
        bbox: [x1, y1, x2, y2] 像素坐标
        use_center_point: 额外添加中心点提高精度
        """
        x1, y1, x2, y2 = bbox

        if use_center_point:
            # bbox 两角 + 中心正点 = 更精确的提示
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            points = np.array([[x1, y1], [x2, y2], [cx, cy]], dtype=np.float32)
            labels = np.array([2, 3, 1], dtype=np.float32)  # 2=TL, 3=BR, 1=正点
        else:
            points = np.array([[x1, y1], [x2, y2]], dtype=np.float32)
            labels = np.array([2, 3], dtype=np.float32)

        self.decoder.set_image_size(embedding["original_size"])
        mask, scores = self.decoder(
            embedding["image_embedding"],
            embedding["high_res_feats_0"],
            embedding["high_res_feats_1"],
            points, labels,
        )
        return mask, scores


# ===================== 工具函数 =====================

def pad_bbox(bbox, img_w, img_h, padding=BBOX_PADDING):
    """外扩 bbox, 给 SAM2 更多上下文"""
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    px, py = bw * padding, bh * padding
    return [
        max(0, x1 - px),
        max(0, y1 - py),
        min(img_w, x2 + px),
        min(img_h, y2 + py),
    ]


def mask_to_polygon(mask, epsilon=EPSILON):
    """二值 mask -> 多边形顶点列表 (高精度)"""
    binary = (mask > 0).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    # 取最大轮廓
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < MIN_CONTOUR_AREA:
        return None
    # 多边形简化 (epsilon 越小, 保留越多细节)
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon * peri, True)
    if len(approx) < MIN_POLYGON_POINTS:
        return None
    return approx.squeeze()


def bbox_to_polygon_fallback(bbox, img_w, img_h):
    """SAM2 失败时退化为 bbox 矩形多边形"""
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(x1, img_w))
    y1 = max(0, min(y1, img_h))
    x2 = max(0, min(x2, img_w))
    y2 = max(0, min(y2, img_h))
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]])


def polygon_to_yolo_seg(polygon, img_w, img_h):
    """多边形 -> YOLO-seg 归一化坐标字符串"""
    norm = polygon.astype(float)
    norm[:, 0] = np.clip(norm[:, 0] / img_w, 0, 1)
    norm[:, 1] = np.clip(norm[:, 1] / img_h, 0, 1)
    return " ".join(f"{x:.6f} {y:.6f}" for x, y in norm)


def read_labelme_json(json_path):
    """读取 LabelMe JSON, 返回 [(label, [x1,y1,x2,y2]), ...]"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    bboxes = []
    for shape in data.get("shapes", []):
        label = shape.get("label", "")
        pts = shape.get("points", [])
        if shape.get("shape_type") == "rectangle" and len(pts) >= 2:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            bboxes.append((label, [min(xs), min(ys), max(xs), max(ys)]))
    return bboxes


# ===================== 主处理流程 =====================

def process_split(sam2, split_name):
    """处理一个数据集分割 (train/valid/test)"""
    img_dir = GYU_DET_DIR / split_name / split_name / "images"
    out_dir = GYU_DET_DIR / split_name / split_name / "labels_seg"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 找所有有 JSON 标注的图片
    json_files = sorted(glob.glob(str(img_dir / "*.json")))
    print(f"\n{'='*60}")
    print(f"Split: {split_name} | JSON annotations: {len(json_files)}")
    print(f"Output: {out_dir}")
    print(f"{'='*60}")

    stats = {"total": 0, "sam2_ok": 0, "fallback": 0, "skip": 0}

    for json_path in tqdm(json_files, desc=f"[{split_name}]"):
        json_path = Path(json_path)
        stem = json_path.stem

        # 找对应图片
        img_path = None
        for ext in [".JPG", ".jpg", ".jpeg", ".png", ".PNG"]:
            candidate = img_dir / f"{stem}{ext}"
            if candidate.exists():
                img_path = candidate
                break
        if img_path is None:
            stats["skip"] += 1
            continue

        # 读取图片 (中文路径兼容)
        img = cv2_imread(img_path)
        if img is None:
            stats["skip"] += 1
            continue
        h, w = img.shape[:2]

        # 读取 bbox 标注
        bboxes = read_labelme_json(str(json_path))
        if not bboxes:
            stats["skip"] += 1
            continue

        # 编码图片 (每张图只做一次 encoder)
        embedding = sam2.encode(img)

        lines = []
        for label, bbox in bboxes:
            if label not in CLASS_MAP:
                continue
            class_id = CLASS_MAP[label]
            stats["total"] += 1

            # 外扩 bbox
            padded_bbox = pad_bbox(bbox, w, h)

            try:
                mask, scores = sam2.predict_mask(embedding, padded_bbox, use_center_point=True)
                polygon = mask_to_polygon(mask)
                if polygon is not None:
                    stats["sam2_ok"] += 1
                else:
                    polygon = bbox_to_polygon_fallback(bbox, w, h)
                    stats["fallback"] += 1
            except Exception:
                polygon = bbox_to_polygon_fallback(bbox, w, h)
                stats["fallback"] += 1

            coords_str = polygon_to_yolo_seg(polygon, w, h)
            lines.append(f"{class_id} {coords_str}")

        # 保存 YOLO-seg 标签
        label_file = out_dir / f"{stem}.txt"
        with open(label_file, "w") as f:
            f.write("\n".join(lines))

    return stats


def main():
    print("=" * 60)
    print("GYU-DET bbox -> YOLO-seg (SAM2 High Precision)")
    print("=" * 60)

    # 如果 Large 不存在, 自动降级到 Base+
    global SAM2_ENCODER, SAM2_DECODER
    if not os.path.exists(SAM2_ENCODER):
        alt_enc = str(PROJECT_ROOT / "models" / "sam2" / "sam2.1_hiera_base_plus.encoder.onnx")
        alt_dec = str(PROJECT_ROOT / "models" / "sam2" / "sam2.1_hiera_base_plus.decoder.onnx")
        if os.path.exists(alt_enc):
            print("Large model not found, using Base+ instead")
            SAM2_ENCODER = alt_enc
            SAM2_DECODER = alt_dec
        else:
            print(f"ERROR: No SAM2 model found in {PROJECT_ROOT / 'models' / 'sam2'}")
            sys.exit(1)

    # 加载 SAM2
    sam2 = SAM2(SAM2_ENCODER, SAM2_DECODER, device="gpu")

    # 处理每个分割
    total_stats = {"total": 0, "sam2_ok": 0, "fallback": 0, "skip": 0}
    t0 = time.time()

    for split in SPLITS:
        split_dir = GYU_DET_DIR / split / split / "images"
        if not split_dir.exists():
            print(f"Skipping {split}: directory not found")
            continue
        stats = process_split(sam2, split)
        for k in total_stats:
            total_stats[k] += stats[k]

    elapsed = time.time() - t0

    # 汇总
    print(f"\n{'='*60}")
    print(f"ALL DONE! Time: {elapsed/60:.1f} min")
    print(f"Total objects: {total_stats['total']}")
    print(f"  SAM2 mask OK: {total_stats['sam2_ok']} ({total_stats['sam2_ok']/max(total_stats['total'],1)*100:.1f}%)")
    print(f"  Fallback bbox: {total_stats['fallback']} ({total_stats['fallback']/max(total_stats['total'],1)*100:.1f}%)")
    print(f"  Skipped images: {total_stats['skip']}")
    print(f"{'='*60}")
    print(f"\nYOLO-seg labels saved to:")
    for split in SPLITS:
        p = GYU_DET_DIR / split / split / "labels_seg"
        if p.exists():
            n = len(list(p.glob("*.txt")))
            print(f"  {p}/  ({n} files)")


if __name__ == "__main__":
    main()
