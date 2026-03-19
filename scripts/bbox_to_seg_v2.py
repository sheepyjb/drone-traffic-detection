"""
GYU-DET bbox -> YOLO-seg 高精度批量转换 (v2 - 混合策略)
==========================================================
混合推理策略:
  - 大目标 (feature map > 50px): 全图编码, bbox prompt 解码
  - 小目标 (feature map <= 50px): 局部裁剪放大到 1024, 单独编码解码

用法 (云服务器):
    python bbox_to_seg_v2.py --root /data/GYU-DET --models /data/models/sam2
用法 (本地 Windows):
    python bbox_to_seg_v2.py --root D:/服创/GYU-DET --models D:/服创/models/sam2
"""

import argparse
import json
import glob
import os
import sys
import time
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np

import onnxruntime as ort
ort.set_default_logger_severity(3)

from tqdm import tqdm


# ===================== 参数解析 =====================

def parse_args():
    p = argparse.ArgumentParser(description="GYU-DET bbox -> YOLO-seg (SAM2 hybrid)")
    p.add_argument("--root", type=str, required=True,
                   help="GYU-DET dataset root (contains train/valid/test)")
    p.add_argument("--models", type=str, required=True,
                   help="SAM2 ONNX models directory")
    p.add_argument("--model-size", type=str, default="large",
                   choices=["large", "base_plus"],
                   help="SAM2 model size (default: large)")
    p.add_argument("--device", type=str, default="gpu",
                   choices=["gpu", "cpu"],
                   help="Inference device (default: gpu)")
    p.add_argument("--splits", type=str, nargs="+", default=["train", "valid", "test"],
                   help="Dataset splits to process")
    p.add_argument("--resume", action="store_true",
                   help="Skip already processed files (resume from interruption)")
    p.add_argument("--small-threshold", type=int, default=50,
                   help="Feature map bbox size threshold for crop mode (default: 50px)")
    p.add_argument("--crop-padding", type=float, default=0.3,
                   help="Padding ratio around bbox for crop mode (default: 0.3)")
    p.add_argument("--bbox-padding", type=float, default=0.05,
                   help="Bbox expansion for full-image mode (default: 0.05)")
    p.add_argument("--epsilon", type=float, default=0.001,
                   help="Polygon simplification coefficient (default: 0.001)")
    p.add_argument("--min-area", type=int, default=50,
                   help="Minimum contour area in pixels (default: 50)")
    p.add_argument("--min-points", type=int, default=4,
                   help="Minimum polygon vertices (default: 4)")
    p.add_argument("--clip-padding", type=float, default=0.02,
                   help="Bbox clip padding ratio (default: 0.02)")
    return p.parse_args()


# ===================== 类别定义 =====================

CLASS_MAP = {
    "crack": 0,
    "spalling": 1,
    "rebar_exposure": 2,
    "corrosion": 3,
    "efflorescence": 4,
    "water_seepage": 5,
}


# ===================== 图片 I/O =====================

def imread_safe(path_str):
    """兼容中文路径的 imread"""
    path_str = str(path_str)
    # 尝试标准 imread
    img = cv2.imread(path_str)
    if img is not None:
        return img
    # fallback: numpy fromfile (Windows 中文路径)
    try:
        data = np.fromfile(path_str, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def imwrite_safe(path_str, img):
    """兼容中文路径的 imwrite"""
    path_str = str(path_str)
    ok = cv2.imwrite(path_str, img)
    if not ok:
        ext = Path(path_str).suffix
        ok, buf = cv2.imencode(ext, img)
        if ok:
            buf.tofile(path_str)


# ===================== SAM2 ONNX =====================

class SAM2ONNX:
    """SAM2 encoder + decoder, 支持全图和局部裁剪两种推理模式"""

    def __init__(self, encoder_path, decoder_path, device="gpu"):
        providers = ["CPUExecutionProvider"]
        if device == "gpu":
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        opts = ort.SessionOptions()
        opts.log_severity_level = 3

        print(f"Loading encoder: {Path(encoder_path).name}")
        self.enc = ort.InferenceSession(encoder_path, providers=providers, sess_options=opts)
        print(f"  Providers: {self.enc.get_providers()}")

        print(f"Loading decoder: {Path(decoder_path).name}")
        self.dec = ort.InferenceSession(decoder_path, providers=providers, sess_options=opts)
        print(f"  Providers: {self.dec.get_providers()}")

        enc_inp = self.enc.get_inputs()
        self.enc_in_name = enc_inp[0].name
        self.enc_shape = enc_inp[0].shape  # [1, 3, 1024, 1024]
        self.enc_h = self.enc_shape[2]
        self.enc_w = self.enc_shape[3]
        self.enc_out_names = [o.name for o in self.enc.get_outputs()]

        self.dec_in_names = [i.name for i in self.dec.get_inputs()]
        self.dec_out_names = [o.name for o in self.dec.get_outputs()]
        self.scale_factor = 4

        print(f"Encoder input: {self.enc_shape}")

    def _preprocess(self, img):
        """BGR image -> normalized tensor [1,3,H,W]"""
        x = cv2.resize(img, (self.enc_w, self.enc_h))
        x = (x / 255.0 - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
        x = x.transpose(2, 0, 1)[None].astype(np.float32)
        return x

    def encode(self, img):
        """编码图片, 返回 (hr0, hr1, embedding)"""
        x = self._preprocess(img)
        outputs = self.enc.run(self.enc_out_names, {self.enc_in_name: x})
        return outputs[0], outputs[1], outputs[2]

    def decode(self, emb, hr0, hr1, points, labels, orig_size):
        """解码 mask
        points: [N, 2] 像素坐标
        labels: [N] (1=正点, 2=bbox左上, 3=bbox右下)
        orig_size: (h, w) 原始图片尺寸
        """
        pc = points[None].copy().astype(np.float32)
        pl = labels[None].astype(np.float32)

        # 坐标映射到 encoder 空间
        pc[..., 0] *= self.enc_w / orig_size[1]
        pc[..., 1] *= self.enc_h / orig_size[0]

        mi = np.zeros((1, 1, self.enc_h // self.scale_factor,
                        self.enc_w // self.scale_factor), dtype=np.float32)
        hm = np.array([0], dtype=np.float32)

        inputs = (emb, hr0, hr1, pc, pl, mi, hm)
        outputs = self.dec.run(
            self.dec_out_names,
            {self.dec_in_names[i]: inputs[i] for i in range(len(self.dec_in_names))}
        )

        scores = outputs[1].squeeze()
        masks = outputs[0][0]
        best_mask = masks[np.argmax(scores)]
        best_mask = cv2.resize(best_mask, (orig_size[1], orig_size[0]))
        return best_mask


# ===================== 混合推理策略 =====================

class HybridPredictor:
    """混合推理: 大目标全图, 小目标局部裁剪"""

    def __init__(self, sam2, args):
        self.sam2 = sam2
        self.small_thresh = args.small_threshold
        self.crop_padding = args.crop_padding
        self.bbox_padding = args.bbox_padding

    def is_small_target(self, bbox, img_w, img_h):
        """判断 bbox 在 feature map 中是否为小目标"""
        x1, y1, x2, y2 = bbox
        fw = (x2 - x1) / img_w * 1024
        fh = (y2 - y1) / img_h * 1024
        return fw < self.small_thresh or fh < self.small_thresh

    def predict_full_image(self, embedding, bbox, img_h, img_w):
        """全图模式: 用已有 embedding, bbox prompt 解码"""
        hr0, hr1, emb = embedding
        x1, y1, x2, y2 = bbox

        # bbox 外扩
        bw, bh = x2 - x1, y2 - y1
        px, py = bw * self.bbox_padding, bh * self.bbox_padding
        px1 = max(0, x1 - px)
        py1 = max(0, y1 - py)
        px2 = min(img_w, x2 + px)
        py2 = min(img_h, y2 + py)

        cx, cy = (px1 + px2) / 2, (py1 + py2) / 2
        points = np.array([[px1, py1], [px2, py2], [cx, cy]], dtype=np.float32)
        labels = np.array([2, 3, 1], dtype=np.float32)

        mask = self.sam2.decode(emb, hr0, hr1, points, labels, (img_h, img_w))
        return mask

    def predict_crop(self, img, bbox):
        """局部裁剪模式: 裁剪 bbox 周围区域, 单独编码解码"""
        h, w = img.shape[:2]
        x1, y1, x2, y2 = bbox
        bw, bh = x2 - x1, y2 - y1

        # 大比例 padding, 给 SAM2 充足上下文
        pad = self.crop_padding
        px, py = bw * pad, bh * pad
        cx1 = int(max(0, x1 - px))
        cy1 = int(max(0, y1 - py))
        cx2 = int(min(w, x2 + px))
        cy2 = int(min(h, y2 + py))

        crop = img[cy1:cy2, cx1:cx2]
        crop_h, crop_w = crop.shape[:2]

        if crop_h < 10 or crop_w < 10:
            return None

        # 在 crop 坐标系中的 bbox
        local_x1 = x1 - cx1
        local_y1 = y1 - cy1
        local_x2 = x2 - cx1
        local_y2 = y2 - cy1
        local_cx = (local_x1 + local_x2) / 2
        local_cy = (local_y1 + local_y2) / 2

        # 单独编码这个 crop
        hr0, hr1, emb = self.sam2.encode(crop)

        points = np.array([[local_x1, local_y1], [local_x2, local_y2],
                           [local_cx, local_cy]], dtype=np.float32)
        labels = np.array([2, 3, 1], dtype=np.float32)

        local_mask = self.sam2.decode(emb, hr0, hr1, points, labels, (crop_h, crop_w))

        # 还原到原图坐标
        full_mask = np.zeros((h, w), dtype=local_mask.dtype)
        full_mask[cy1:cy2, cx1:cx2] = local_mask
        return full_mask

    def predict(self, img, embedding, bbox):
        """自动选择推理策略"""
        h, w = img.shape[:2]

        if self.is_small_target(bbox, w, h):
            mask = self.predict_crop(img, bbox)
            if mask is not None:
                return mask, "crop"

        # 大目标 or crop 失败 -> 全图模式
        mask = self.predict_full_image(embedding, bbox, h, w)
        return mask, "full"


# ===================== mask -> polygon =====================

def mask_to_polygon(mask, epsilon, min_area, min_points):
    """二值 mask -> 多边形顶点, 失败返回 None"""
    binary = (mask > 0.5).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < min_area:
        return None
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon * peri, True)
    if len(approx) < min_points:
        return None
    return approx.squeeze()


def clip_mask_to_bbox(mask, bbox, img_h, img_w, padding=0.02):
    """将 mask 限制在 bbox 区域内 (含轻微外扩保留边缘细节)"""
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    pad_x = bw * padding
    pad_y = bh * padding
    cx1 = int(max(0, x1 - pad_x))
    cy1 = int(max(0, y1 - pad_y))
    cx2 = int(min(img_w, x2 + pad_x))
    cy2 = int(min(img_h, y2 + pad_y))

    clipped = np.zeros_like(mask)
    clipped[cy1:cy2, cx1:cx2] = mask[cy1:cy2, cx1:cx2]
    return clipped


def polygon_to_yolo_seg(polygon, img_w, img_h):
    """多边形 -> YOLO-seg 归一化坐标"""
    norm = polygon.astype(float)
    norm[:, 0] = np.clip(norm[:, 0] / img_w, 0, 1)
    norm[:, 1] = np.clip(norm[:, 1] / img_h, 0, 1)
    return " ".join(f"{x:.6f} {y:.6f}" for x, y in norm)


def bbox_to_rect_polygon(bbox, img_w, img_h):
    """bbox -> 矩形多边形 (fallback)"""
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(x1, img_w))
    y1 = max(0, min(y1, img_h))
    x2 = max(0, min(x2, img_w))
    y2 = max(0, min(y2, img_h))
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]])


# ===================== 读标注 =====================

ID_TO_CLASS = {v: k for k, v in CLASS_MAP.items()}


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


def read_yolo_bbox_txt(txt_path, img_w, img_h):
    """读取 YOLO bbox 格式 txt, 返回 [(label, [x1,y1,x2,y2]), ...]
    YOLO 格式: class_id x_center y_center width height (归一化)
    """
    bboxes = []
    with open(txt_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            class_id = int(parts[0])
            xc, yc, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            # 归一化 -> 像素坐标
            x1 = (xc - bw / 2) * img_w
            y1 = (yc - bh / 2) * img_h
            x2 = (xc + bw / 2) * img_w
            y2 = (yc + bh / 2) * img_h
            label = ID_TO_CLASS.get(class_id, str(class_id))
            bboxes.append((label, [x1, y1, x2, y2]))
    return bboxes


def find_image(img_dir, stem):
    """找对应的图片文件"""
    for ext in [".JPG", ".jpg", ".jpeg", ".png", ".PNG", ".bmp"]:
        p = img_dir / f"{stem}{ext}"
        if p.exists():
            return p
    return None


# ===================== 主处理 =====================

def detect_split_dirs(dataset_root, split_name):
    """自动检测目录结构:
       结构A (本地): root/train/train/images/
       结构B (服务器): root/train/images/
    """
    # 尝试结构 A: root/split/split/images/
    path_a = dataset_root / split_name / split_name / "images"
    if path_a.exists():
        base = dataset_root / split_name / split_name
        return base / "images", base / "labels", base / "labels_seg"

    # 尝试结构 B: root/split/images/
    path_b = dataset_root / split_name / "images"
    if path_b.exists():
        base = dataset_root / split_name
        return base / "images", base / "labels", base / "labels_seg"

    return None, None, None


def process_split(predictor, args, split_name, dataset_root):
    """处理一个 split"""
    img_dir, lbl_dir, out_dir = detect_split_dirs(dataset_root, split_name)
    if img_dir is None:
        print(f"Skipping {split_name}: images dir not found")
        return {"total": 0, "sam2_full": 0, "sam2_crop": 0, "fallback": 0, "skip": 0}
    out_dir.mkdir(parents=True, exist_ok=True)

    # 自动检测标注来源: JSON (LabelMe) 或 TXT (YOLO bbox)
    json_files = sorted(glob.glob(str(img_dir / "*.json")))
    txt_files = sorted(glob.glob(str(lbl_dir / "*.txt"))) if lbl_dir.exists() else []

    if json_files:
        ann_mode = "json"
        ann_files = json_files
        print(f"Annotation source: LabelMe JSON ({len(json_files)} files)")
    elif txt_files:
        ann_mode = "yolo_txt"
        ann_files = txt_files
        print(f"Annotation source: YOLO bbox TXT ({len(txt_files)} files)")
    else:
        print(f"Skipping {split_name}: no annotations found")
        return {"total": 0, "sam2_full": 0, "sam2_crop": 0, "fallback": 0, "skip": 0}

    print(f"\n{'='*60}")
    print(f"Split: {split_name} | Annotations: {len(ann_files)}")
    print(f"Output: {out_dir}")
    print(f"Strategy: full-image (bbox>{args.small_threshold}px) + crop (bbox<={args.small_threshold}px)")
    print(f"{'='*60}")

    stats = {"total": 0, "sam2_full": 0, "sam2_crop": 0, "fallback": 0, "skip": 0, "resumed": 0}

    for ann_path in tqdm(ann_files, desc=f"[{split_name}]"):
        ann_path = Path(ann_path)
        stem = ann_path.stem

        # --resume: 跳过已处理的文件
        if args.resume and (out_dir / f"{stem}.txt").exists():
            stats["resumed"] += 1
            continue

        img_path = find_image(img_dir, stem)
        if img_path is None:
            stats["skip"] += 1
            continue

        img = imread_safe(img_path)
        if img is None:
            stats["skip"] += 1
            continue
        h, w = img.shape[:2]

        if ann_mode == "json":
            bboxes = read_labelme_json(str(ann_path))
        else:
            bboxes = read_yolo_bbox_txt(str(ann_path), w, h)

        if not bboxes:
            stats["skip"] += 1
            continue

        # 全图编码 (大目标共用)
        embedding = predictor.sam2.encode(img)

        lines = []
        for label, bbox in bboxes:
            if label not in CLASS_MAP:
                continue
            class_id = CLASS_MAP[label]
            stats["total"] += 1

            try:
                mask, mode = predictor.predict(img, embedding, bbox)
                mask = clip_mask_to_bbox(mask, bbox, h, w, args.clip_padding)
                polygon = mask_to_polygon(mask, args.epsilon, args.min_area, args.min_points)

                if polygon is not None:
                    if mode == "crop":
                        stats["sam2_crop"] += 1
                    else:
                        stats["sam2_full"] += 1
                else:
                    polygon = bbox_to_rect_polygon(bbox, w, h)
                    stats["fallback"] += 1
            except Exception:
                polygon = bbox_to_rect_polygon(bbox, w, h)
                stats["fallback"] += 1

            coords_str = polygon_to_yolo_seg(polygon, w, h)
            lines.append(f"{class_id} {coords_str}")

        label_file = out_dir / f"{stem}.txt"
        with open(label_file, "w") as f:
            f.write("\n".join(lines))

    return stats


def main():
    args = parse_args()

    dataset_root = Path(args.root)
    models_dir = Path(args.models)

    print("=" * 60)
    print("GYU-DET bbox -> YOLO-seg (SAM2 Hybrid v2)")
    print("=" * 60)
    print(f"Dataset:   {dataset_root}")
    print(f"Models:    {models_dir}")
    print(f"Device:    {args.device}")
    print(f"Strategy:  hybrid (threshold={args.small_threshold}px)")
    print(f"Splits:    {args.splits}")

    # 找模型
    size_map = {
        "large": ("sam2.1_hiera_large.encoder.onnx", "sam2.1_hiera_large.decoder.onnx"),
        "base_plus": ("sam2.1_hiera_base_plus.encoder.onnx", "sam2.1_hiera_base_plus.decoder.onnx"),
    }
    enc_name, dec_name = size_map[args.model_size]
    enc_path = str(models_dir / enc_name)
    dec_path = str(models_dir / dec_name)

    if not os.path.exists(enc_path):
        # 自动降级
        if args.model_size == "large":
            print("Large model not found, trying base_plus...")
            enc_name, dec_name = size_map["base_plus"]
            enc_path = str(models_dir / enc_name)
            dec_path = str(models_dir / dec_name)

    if not os.path.exists(enc_path):
        print(f"ERROR: Model not found: {enc_path}")
        sys.exit(1)

    # Windows CUDA DLL 修复 (Linux 上自动跳过)
    if sys.platform == "win32":
        import glob as _g
        for site_pkg in [
            os.path.join(os.path.dirname(sys.executable), "Lib", "site-packages"),
            os.path.join(sys.prefix, "Lib", "site-packages"),
        ]:
            for _d in _g.glob(os.path.join(site_pkg, "nvidia", "*", "bin")):
                os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")

    # 加载模型
    sam2 = SAM2ONNX(enc_path, dec_path, device=args.device)
    predictor = HybridPredictor(sam2, args)

    # 处理
    total_stats = {"total": 0, "sam2_full": 0, "sam2_crop": 0, "fallback": 0, "skip": 0, "resumed": 0}
    t0 = time.time()

    for split in args.splits:
        img_dir, _, _ = detect_split_dirs(dataset_root, split)
        if img_dir is None:
            print(f"Skipping {split}: not found")
            continue
        stats = process_split(predictor, args, split, dataset_root)
        for k in total_stats:
            total_stats[k] += stats[k]

    elapsed = time.time() - t0

    # 汇总
    total = max(total_stats["total"], 1)
    print(f"\n{'='*60}")
    print(f"DONE! Time: {elapsed/60:.1f} min")
    print(f"Total objects: {total_stats['total']}")
    print(f"  Full-image mode: {total_stats['sam2_full']} ({total_stats['sam2_full']/total*100:.1f}%)")
    print(f"  Crop mode:       {total_stats['sam2_crop']} ({total_stats['sam2_crop']/total*100:.1f}%)")
    print(f"  Fallback bbox:   {total_stats['fallback']} ({total_stats['fallback']/total*100:.1f}%)")
    print(f"  Skipped images:  {total_stats['skip']}")
    if total_stats["resumed"] > 0:
        print(f"  Resumed (skipped): {total_stats['resumed']} files")
    print(f"{'='*60}")
    print(f"\nYOLO-seg labels saved to:")
    for split in args.splits:
        _, _, seg_dir = detect_split_dirs(dataset_root, split)
        if seg_dir and seg_dir.exists():
            n = len(list(seg_dir.glob("*.txt")))
            print(f"  {seg_dir}/  ({n} files)")


if __name__ == "__main__":
    main()
