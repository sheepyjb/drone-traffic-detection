"""
GYU-DET SAM2 seg 标签质量检查 + 自动修复 + 可视化报告
转换完成后运行:
  1. 检查所有 labels_seg 文件的质量问题
  2. 校验归一化坐标 [0,1] + 类别 ID 对齐
  3. 自动修复有问题的标注
  4. 生成 50 张修复前后对比图 (展示素材)

用法 (云服务器):
    python qa_fix_seg_labels.py --root /data/GYU-DET --models /data/models/sam2
用法 (本地 Windows):
    python qa_fix_seg_labels.py --root D:/服创/GYU-DET --models D:/服创/models/sam2
"""
import argparse
import os, json, glob, time, traceback, random, shutil, sys
from pathlib import Path
from collections import defaultdict

# Windows CUDA DLL fix (Linux 自动跳过)
if sys.platform == "win32":
    import glob as _g
    for site_pkg in [
        os.path.join(os.path.dirname(sys.executable), "Lib", "site-packages"),
        os.path.join(sys.prefix, "Lib", "site-packages"),
    ]:
        for _d in _g.glob(os.path.join(site_pkg, "nvidia", "*", "bin")):
            os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")

import cv2
import numpy as np
import onnxruntime as ort
ort.set_default_logger_severity(3)
from tqdm import tqdm


# ===================== 参数解析 =====================

def parse_args():
    p = argparse.ArgumentParser(description="QA check + fix for SAM2 seg labels")
    p.add_argument("--root", type=str, required=True,
                   help="GYU-DET dataset root")
    p.add_argument("--models", type=str, required=True,
                   help="SAM2 ONNX models directory")
    p.add_argument("--device", type=str, default="gpu", choices=["gpu", "cpu"])
    p.add_argument("--splits", type=str, nargs="+", default=["train", "valid", "test"])
    p.add_argument("--n-visual", type=int, default=50,
                   help="Number of before/after comparison images to generate")
    return p.parse_args()

# ===================== 配置 =====================

GYU_DET_DIR = None  # set from args
MODELS_DIR = None
SPLITS = ["train", "valid", "test"]

CLASS_MAP = {
    "crack": 0, "spalling": 1, "rebar_exposure": 2,
    "corrosion": 3, "efflorescence": 4, "water_seepage": 5,
}
ID_TO_CLASS = {v: k for k, v in CLASS_MAP.items()}

# 质量阈值
MIN_POLYGON_POINTS = 4       # 多边形最少顶点
MAX_POLYGON_POINTS = 2000    # 多边形最多顶点 (太多说明噪声)
BBOX_RECT_THRESHOLD = 5      # <=5 个点且呈矩形 = fallback bbox
MIN_AREA_RATIO = 0.05        # mask 面积 / bbox 面积 < 5% = 欠分割
MAX_AREA_RATIO = 3.0         # mask 面积 / bbox 面积 > 300% = 过分割
EPSILON_RETRY = 0.002         # 修复时用的简化系数 (稍宽松)
BBOX_PADDING_RETRY = 0.08    # 修复时外扩比例 (更大)


# ===================== 目录检测 =====================

def detect_split_dirs(split_name):
    """自动检测目录结构:
       结构A (本地): root/train/train/images/
       结构B (服务器): root/train/images/
    """
    path_a = GYU_DET_DIR / split_name / split_name / "images"
    if path_a.exists():
        return path_a, GYU_DET_DIR / split_name / split_name / "labels_seg"
    path_b = GYU_DET_DIR / split_name / "images"
    if path_b.exists():
        return path_b, GYU_DET_DIR / split_name / "labels_seg"
    return None, None


# ===================== 工具 =====================

def cv2_imread(path_str):
    data = np.fromfile(str(path_str), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def parse_yolo_seg_line(line):
    """解析 YOLO-seg 格式一行: class_id x1 y1 x2 y2 ..."""
    parts = line.strip().split()
    if len(parts) < 7:  # class_id + 至少 3 个点 (6 个坐标)
        return None
    class_id = int(parts[0])
    coords = list(map(float, parts[1:]))
    points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
    return class_id, points


def is_rectangle(points, tol=0.01):
    """判断多边形是否为矩形 (bbox fallback 的特征)"""
    if len(points) != 4:
        return False
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    # 矩形特征: 只有 2 个唯一的 x 值和 2 个唯一的 y 值
    unique_x = len(set(round(x, 4) for x in xs))
    unique_y = len(set(round(y, 4) for y in ys))
    return unique_x <= 2 and unique_y <= 2


def polygon_area_normalized(points):
    """计算归一化坐标多边形面积 (Shoelace formula)"""
    n = len(points)
    if n < 3:
        return 0
    area = 0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    return abs(area) / 2


def bbox_area_from_json(json_path, label_filter=None):
    """从 JSON 读取 bbox 面积 (归一化)"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    img_w = data.get("imageWidth", 1)
    img_h = data.get("imageHeight", 1)
    result = []
    for s in data.get("shapes", []):
        if s.get("shape_type") != "rectangle":
            continue
        label = s.get("label", "")
        if label not in CLASS_MAP:
            continue
        pts = s["points"]
        x1, y1 = min(p[0] for p in pts), min(p[1] for p in pts)
        x2, y2 = max(p[0] for p in pts), max(p[1] for p in pts)
        # 归一化面积
        norm_area = ((x2 - x1) / img_w) * ((y2 - y1) / img_h)
        result.append({
            "label": label,
            "class_id": CLASS_MAP[label],
            "bbox": [x1, y1, x2, y2],
            "bbox_area_norm": norm_area,
            "img_w": img_w,
            "img_h": img_h,
        })
    return result


# ===================== SAM2 重新推理 =====================

class SAM2Retry:
    """用于修复的 SAM2 推理器"""
    def __init__(self):
        self.enc = None
        self.dec = None
        self.loaded = False

    def load(self):
        if self.loaded:
            return
        print("\nLoading SAM2 for retry...")
        # 优先 Large, 否则 Base+
        enc_path = str(MODELS_DIR / "sam2.1_hiera_large.encoder.onnx")
        dec_path = str(MODELS_DIR / "sam2.1_hiera_large.decoder.onnx")
        if not os.path.exists(enc_path):
            enc_path = str(MODELS_DIR / "sam2.1_hiera_base_plus.encoder.onnx")
            dec_path = str(MODELS_DIR / "sam2.1_hiera_base_plus.decoder.onnx")

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        self.enc_sess = ort.InferenceSession(enc_path,
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider'],
            sess_options=opts)
        inp = self.enc_sess.get_inputs()
        self.enc_in_names = [i.name for i in inp]
        self.enc_in_shape = inp[0].shape
        self.enc_out_names = [o.name for o in self.enc_sess.get_outputs()]

        self.dec_sess = ort.InferenceSession(dec_path,
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider'],
            sess_options=opts)
        self.dec_in_names = [i.name for i in self.dec_sess.get_inputs()]
        self.dec_out_names = [o.name for o in self.dec_sess.get_outputs()]
        self.enc_size = (self.enc_in_shape[2], self.enc_in_shape[3])
        self.sf = 4
        self.loaded = True
        print(f"  SAM2 loaded: {Path(enc_path).name}")

    def encode(self, img):
        h, w = self.enc_in_shape[2], self.enc_in_shape[3]
        x = cv2.resize(img, (w, h))
        x = (x / 255.0 - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
        x = x.transpose(2, 0, 1)[None].astype(np.float32)
        o = self.enc_sess.run(self.enc_out_names, {self.enc_in_names[0]: x})
        return o[0], o[1], o[2]

    def decode(self, emb, hr0, hr1, pts, lbls, orig_size):
        pc = pts[None].copy().astype(np.float32)
        pl = lbls[None].astype(np.float32)
        pc[..., 0] *= self.enc_size[1] / orig_size[1]
        pc[..., 1] *= self.enc_size[0] / orig_size[0]
        mi = np.zeros((1, 1, self.enc_size[0]//self.sf, self.enc_size[1]//self.sf), dtype=np.float32)
        hm = np.array([0], dtype=np.float32)
        inp = (emb, hr0, hr1, pc, pl, mi, hm)
        o = self.dec_sess.run(self.dec_out_names,
            {self.dec_in_names[i]: inp[i] for i in range(len(self.dec_in_names))})
        sc = o[1].squeeze()
        ms = o[0][0]
        best = ms[np.argmax(sc)]
        return cv2.resize(best, (int(orig_size[1]), int(orig_size[0])))

    def retry_mask(self, img, bbox, padding=BBOX_PADDING_RETRY):
        """用更大的外扩重试 mask 生成"""
        h, w = img.shape[:2]
        x1, y1, x2, y2 = bbox
        bw, bh = x2 - x1, y2 - y1
        px, py = bw * padding, bh * padding
        px1 = max(0, x1 - px)
        py1 = max(0, y1 - py)
        px2 = min(w, x2 + px)
        py2 = min(h, y2 + py)

        hr0, hr1, emb = self.encode(img)

        # 策略1: bbox + center point (标准)
        cx, cy = (px1 + px2) / 2, (py1 + py2) / 2
        mask1 = self.decode(emb, hr0, hr1,
            np.array([[px1, py1], [px2, py2], [cx, cy]], dtype=np.float32),
            np.array([2, 3, 1], dtype=np.float32),
            (h, w))

        # 策略2: 仅 bbox (无中心点, 有时对不规则形状更好)
        mask2 = self.decode(emb, hr0, hr1,
            np.array([[px1, py1], [px2, py2]], dtype=np.float32),
            np.array([2, 3], dtype=np.float32),
            (h, w))

        # 选择面积更合理的 mask (更接近 bbox 面积)
        bbox_area = bw * bh
        a1 = np.sum(mask1 > 0)
        a2 = np.sum(mask2 > 0)
        r1 = a1 / max(bbox_area, 1)
        r2 = a2 / max(bbox_area, 1)

        # 选比例更接近 0.5~1.0 的
        d1 = abs(r1 - 0.7)
        d2 = abs(r2 - 0.7)
        best_mask = mask1 if d1 <= d2 else mask2

        return best_mask


def mask_to_yolo_seg(mask, class_id, img_w, img_h, epsilon=EPSILON_RETRY):
    """mask -> YOLO-seg 格式字符串"""
    binary = (mask > 0).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 50:
        return None
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon * peri, True)
    if len(approx) < MIN_POLYGON_POINTS:
        return None
    pts = approx.squeeze().astype(float)
    pts[:, 0] = np.clip(pts[:, 0] / img_w, 0, 1)
    pts[:, 1] = np.clip(pts[:, 1] / img_h, 0, 1)
    coords_str = " ".join(f"{x:.6f} {y:.6f}" for x, y in pts)
    return f"{class_id} {coords_str}"


# ===================== 主流程 =====================

def check_split(split_name):
    """检查一个分割的标签质量"""
    img_dir, seg_dir = detect_split_dirs(split_name)
    if img_dir is None:
        print(f"  {split_name}: images dir not found, skip")
        return {"issues": [], "stats": {}}

    seg_files = sorted(seg_dir.glob("*.txt"))
    json_files = {p.stem: p for p in img_dir.glob("*.json")}

    issues = []
    stats = defaultdict(int)
    stats["total_files"] = len(seg_files)

    for sf in seg_files:
        stem = sf.stem
        lines = sf.read_text().strip().split("\n")
        lines = [l for l in lines if l.strip()]

        if not lines:
            issues.append({"file": stem, "type": "empty", "detail": "空标签文件"})
            stats["empty"] += 1
            continue

        # 获取对应 JSON 中的 bbox 信息
        json_bboxes = []
        if stem in json_files:
            json_bboxes = bbox_area_from_json(str(json_files[stem]))

        for li, line in enumerate(lines):
            parsed = parse_yolo_seg_line(line)
            if parsed is None:
                issues.append({"file": stem, "type": "parse_error",
                               "line": li, "detail": f"解析失败: {line[:80]}"})
                stats["parse_error"] += 1
                continue

            class_id, points = parsed
            n_pts = len(points)
            stats["total_objects"] += 1

            # 检查 1: 顶点过少
            if n_pts < MIN_POLYGON_POINTS:
                issues.append({"file": stem, "type": "too_few_pts",
                               "line": li, "class_id": class_id,
                               "detail": f"顶点仅 {n_pts} 个"})
                stats["too_few_pts"] += 1

            # 检查 2: 矩形 fallback
            elif is_rectangle(points):
                issues.append({"file": stem, "type": "rect_fallback",
                               "line": li, "class_id": class_id,
                               "detail": "退化为矩形 (bbox fallback)"})
                stats["rect_fallback"] += 1

            # 检查 3: 顶点过多 (噪声)
            elif n_pts > MAX_POLYGON_POINTS:
                issues.append({"file": stem, "type": "too_many_pts",
                               "line": li, "class_id": class_id,
                               "detail": f"顶点 {n_pts} 个 (可能有噪声)"})
                stats["too_many_pts"] += 1

            # 检查 4: 面积比异常
            if li < len(json_bboxes):
                bbox_info = json_bboxes[li]
                mask_area = polygon_area_normalized(points)
                bbox_area = bbox_info["bbox_area_norm"]
                if bbox_area > 0:
                    ratio = mask_area / bbox_area
                    if ratio < MIN_AREA_RATIO:
                        issues.append({"file": stem, "type": "under_seg",
                                       "line": li, "class_id": class_id,
                                       "detail": f"欠分割: mask/bbox={ratio:.3f}"})
                        stats["under_seg"] += 1
                    elif ratio > MAX_AREA_RATIO:
                        issues.append({"file": stem, "type": "over_seg",
                                       "line": li, "class_id": class_id,
                                       "detail": f"过分割: mask/bbox={ratio:.2f}"})
                        stats["over_seg"] += 1

            # 检查 5: 归一化校验 — 所有坐标必须在 [0, 1]
            out_of_range = [(x, y) for x, y in points if x < 0 or x > 1 or y < 0 or y > 1]
            if out_of_range:
                issues.append({"file": stem, "type": "coord_out_of_range",
                               "line": li, "class_id": class_id,
                               "detail": f"坐标越界: {len(out_of_range)}个点不在[0,1], 例: {out_of_range[0]}"})
                stats["coord_out_of_range"] += 1

            # 检查 6: 类别 ID 对齐 — class_id 必须在 [0, 5]
            if class_id not in ID_TO_CLASS:
                issues.append({"file": stem, "type": "invalid_class_id",
                               "line": li, "class_id": class_id,
                               "detail": f"无效类别ID: {class_id} (有效范围: 0-5)"})
                stats["invalid_class_id"] += 1

            # 检查 6b: 类别 ID 与 JSON 标注对齐
            if li < len(json_bboxes):
                expected_id = json_bboxes[li]["class_id"]
                if class_id != expected_id:
                    issues.append({"file": stem, "type": "class_id_mismatch",
                                   "line": li, "class_id": class_id,
                                   "detail": f"类别ID不匹配: 标签={class_id}({ID_TO_CLASS.get(class_id,'?')}), "
                                             f"JSON={expected_id}({ID_TO_CLASS.get(expected_id,'?')})"})
                    stats["class_id_mismatch"] += 1

    return {"issues": issues, "stats": dict(stats)}


def fix_issues(all_issues):
    """修复有问题的标注"""
    # 按文件分组
    by_file = defaultdict(list)
    fixable_types = {"rect_fallback", "under_seg", "over_seg", "too_few_pts"}
    for issue in all_issues:
        if issue["type"] in fixable_types:
            by_file[issue["file"]].append(issue)

    if not by_file:
        print("没有需要修复的问题!")
        return 0

    print(f"\n需要修复 {len(by_file)} 个文件中的 {sum(len(v) for v in by_file.values())} 个问题")

    sam2 = SAM2Retry()
    sam2.load()

    fixed_count = 0
    fixed_files_record = {}  # {stem: {"split": str, "before": [lines], "after": [lines]}}

    for split in SPLITS:
        img_dir, seg_dir = detect_split_dirs(split)
        if seg_dir is None or not seg_dir.exists():
            continue

        # 找这个 split 里有问题的文件
        split_files = {p.stem for p in seg_dir.glob("*.txt")}
        to_fix = {f: issues for f, issues in by_file.items() if f in split_files}

        if not to_fix:
            continue

        print(f"\n[{split}] 修复 {len(to_fix)} 个文件...")

        for stem, issues in tqdm(to_fix.items(), desc=f"Fix [{split}]"):
            # 找图片
            img_path = None
            for ext in [".JPG", ".jpg", ".jpeg", ".png", ".PNG"]:
                p = img_dir / f"{stem}{ext}"
                if p.exists():
                    img_path = p
                    break
            if img_path is None:
                continue

            # 找 JSON
            json_path = img_dir / f"{stem}.json"
            if not json_path.exists():
                continue

            img = cv2_imread(img_path)
            if img is None:
                continue
            h, w = img.shape[:2]

            bboxes = bbox_area_from_json(str(json_path))
            if not bboxes:
                continue

            # 读取现有标签
            seg_file = seg_dir / f"{stem}.txt"
            existing_lines = seg_file.read_text().strip().split("\n")
            existing_lines = [l for l in existing_lines if l.strip()]

            # 找出需要修复的行号
            fix_lines = {iss["line"] for iss in issues if "line" in iss}

            new_lines = list(existing_lines)  # 拷贝
            before_snapshot = list(existing_lines)  # 修复前快照
            need_encode = True
            hr0 = hr1 = emb = None

            for line_idx in sorted(fix_lines):
                if line_idx >= len(existing_lines) or line_idx >= len(bboxes):
                    continue

                bbox_info = bboxes[line_idx]
                bbox = bbox_info["bbox"]
                class_id = bbox_info["class_id"]

                # 延迟 encode (只在真正需要时)
                if need_encode:
                    try:
                        hr0, hr1, emb = sam2.encode(img)
                        need_encode = False
                    except Exception:
                        break

                try:
                    mask = sam2.retry_mask(img, bbox)
                    new_line = mask_to_yolo_seg(mask, class_id, w, h)
                    if new_line is not None:
                        new_lines[line_idx] = new_line
                        fixed_count += 1
                except Exception:
                    pass  # 修复失败, 保留原始标注

            # 写回
            with open(seg_file, "w") as f:
                f.write("\n".join(new_lines))

            # 记录修复信息 (用于可视化)
            if new_lines != before_snapshot:
                fixed_files_record[stem] = {
                    "split": split,
                    "before": before_snapshot,
                    "after": new_lines,
                }

    return fixed_count, fixed_files_record


# ===================== 可视化对比报告 =====================

def cv2_imwrite(path, img):
    ext = Path(path).suffix
    ok, buf = cv2.imencode(ext, img)
    if ok: buf.tofile(str(path))


def draw_seg_on_image(img, seg_lines, json_bboxes=None):
    """在图片上绘制 seg 多边形 + bbox"""
    overlay = img.copy()
    colors = [(0,0,255),(255,0,0),(0,165,255),(0,255,0),(255,0,255),(255,255,0)]
    h, w = img.shape[:2]

    for li, line in enumerate(seg_lines):
        parsed = parse_yolo_seg_line(line)
        if parsed is None:
            continue
        class_id, points = parsed
        color = colors[class_id % len(colors)]

        # 反归一化
        pts_px = np.array([(int(x*w), int(y*h)) for x, y in points], dtype=np.int32)
        if len(pts_px) >= 3:
            cv2.fillPoly(overlay, [pts_px], color)
            cv2.drawContours(overlay, [pts_px], -1, color, 2)

        label = ID_TO_CLASS.get(class_id, str(class_id))
        if len(pts_px) > 0:
            cv2.putText(overlay, label, (pts_px[0][0], pts_px[0][1]-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # 画原始 bbox (白色)
        if json_bboxes and li < len(json_bboxes):
            bbox = json_bboxes[li]["bbox"]
            cv2.rectangle(overlay, (int(bbox[0]),int(bbox[1])),
                          (int(bbox[2]),int(bbox[3])), (255,255,255), 1)

    result = cv2.addWeighted(img, 0.5, overlay, 0.5, 0)
    return result


def generate_visual_report(fixed_files, n_samples=50):
    """生成修复前后对比图 (展示素材)"""
    vis_dir = GYU_DET_DIR.parent / "scripts" / "qa_visual_report"
    if not vis_dir.parent.exists():
        vis_dir = GYU_DET_DIR / "qa_visual_report"
    vis_dir.mkdir(parents=True, exist_ok=True)
    vis_dir.mkdir(exist_ok=True)

    if not fixed_files:
        print("没有修复记录, 跳过可视化")
        return

    stems = list(fixed_files.keys())
    random.shuffle(stems)
    samples = stems[:n_samples]

    print(f"\n生成 {len(samples)} 张修复前后对比图...")

    for idx, stem in enumerate(tqdm(samples, desc="Visualize")):
        info = fixed_files[stem]
        split = info["split"]
        before_lines = info["before"]
        after_lines = info["after"]

        img_dir, _ = detect_split_dirs(split)
        json_path = img_dir / f"{stem}.json"

        img_path = None
        for ext in [".JPG", ".jpg", ".jpeg", ".png", ".PNG"]:
            p = img_dir / f"{stem}{ext}"
            if p.exists():
                img_path = p
                break
        if img_path is None:
            continue

        img = cv2_imread(img_path)
        if img is None:
            continue

        json_bboxes = None
        if json_path.exists():
            json_bboxes = bbox_area_from_json(str(json_path))

        before_vis = draw_seg_on_image(img, before_lines, json_bboxes)
        after_vis = draw_seg_on_image(img, after_lines, json_bboxes)

        cv2.putText(before_vis, "BEFORE (raw)", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 2)
        cv2.putText(after_vis, "AFTER (fixed)", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,0), 2)

        target_h = 600
        ratio_b = target_h / before_vis.shape[0]
        ratio_a = target_h / after_vis.shape[0]
        before_r = cv2.resize(before_vis, (int(before_vis.shape[1]*ratio_b), target_h))
        after_r = cv2.resize(after_vis, (int(after_vis.shape[1]*ratio_a), target_h))

        sep = np.full((target_h, 4, 3), 255, dtype=np.uint8)
        combined = np.hstack([before_r, sep, after_r])
        cv2_imwrite(vis_dir / f"{idx+1:03d}_{stem}_compare.jpg", combined)

    # 总览网格 (前10张, 2列排列)
    grid_imgs = []
    for idx, stem in enumerate(samples[:10]):
        p = vis_dir / f"{idx+1:03d}_{stem}_compare.jpg"
        if p.exists():
            im = cv2_imread(p)
            if im is not None:
                tw = 800
                ratio = tw / im.shape[1]
                grid_imgs.append(cv2.resize(im, (tw, int(im.shape[0]*ratio))))

    if grid_imgs:
        max_h = max(im.shape[0] for im in grid_imgs)
        padded = []
        for im in grid_imgs:
            if im.shape[0] < max_h:
                pad = np.zeros((max_h - im.shape[0], im.shape[1], 3), dtype=np.uint8)
                im = np.vstack([im, pad])
            padded.append(im)
        rows = []
        for i in range(0, len(padded), 2):
            if i+1 < len(padded):
                row = np.hstack([padded[i], padded[i+1]])
            else:
                blank = np.zeros_like(padded[i])
                row = np.hstack([padded[i], blank])
            rows.append(row)
        overview = np.vstack(rows)
        cv2_imwrite(vis_dir / "overview_grid.jpg", overview)
        print(f"  总览大图: {vis_dir / 'overview_grid.jpg'}")

    print(f"  对比图保存到: {vis_dir}/")
    print(f"  共 {len(samples)} 张 (左=修复前, 右=修复后, 白框=原始bbox)")


def main():
    args = parse_args()
    global GYU_DET_DIR, MODELS_DIR, SPLITS
    GYU_DET_DIR = Path(args.root)
    MODELS_DIR = Path(args.models)
    SPLITS = args.splits

    print("=" * 60)
    print("GYU-DET SAM2 seg 标签质量检查 + 自动修复 + 可视化报告")
    print(f"Dataset: {GYU_DET_DIR}")
    print(f"Models:  {MODELS_DIR}")
    print("=" * 60)

    all_issues = []
    all_stats = {}

    for split in SPLITS:
        print(f"\n--- Checking {split} ---")
        result = check_split(split)
        all_issues.extend(result["issues"])
        all_stats[split] = result["stats"]

        stats = result["stats"]
        if stats:
            print(f"  文件: {stats.get('total_files', 0)}")
            print(f"  标注对象: {stats.get('total_objects', 0)}")
            print(f"  空文件: {stats.get('empty', 0)}")
            print(f"  矩形 fallback: {stats.get('rect_fallback', 0)}")
            print(f"  欠分割: {stats.get('under_seg', 0)}")
            print(f"  过分割: {stats.get('over_seg', 0)}")
            print(f"  顶点过少: {stats.get('too_few_pts', 0)}")
            print(f"  顶点过多: {stats.get('too_many_pts', 0)}")
            print(f"  坐标越界: {stats.get('coord_out_of_range', 0)}")
            print(f"  无效类别ID: {stats.get('invalid_class_id', 0)}")
            print(f"  类别ID不匹配: {stats.get('class_id_mismatch', 0)}")
            print(f"  解析错误: {stats.get('parse_error', 0)}")

    # 汇总
    total_issues = len(all_issues)
    print(f"\n{'='*60}")
    print(f"总问题数: {total_issues}")

    fixed_files_record = {}

    if total_issues > 0:
        # 按类型统计
        by_type = defaultdict(int)
        for iss in all_issues:
            by_type[iss["type"]] += 1
        print("问题分布:")
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")

        # 保存问题报告
        report_path = GYU_DET_DIR / "qa_report.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"GYU-DET SAM2 seg Quality Report\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"CLASS_MAP (data.yaml 必须一致):\n")
            for name, cid in CLASS_MAP.items():
                f.write(f"  {cid}: {name}\n")
            f.write(f"\n")
            for split in SPLITS:
                s = all_stats.get(split, {})
                f.write(f"[{split}]\n")
                for k, v in s.items():
                    f.write(f"  {k}: {v}\n")
                f.write("\n")
            f.write(f"\nDetailed issues ({total_issues}):\n")
            f.write(f"{'-'*60}\n")
            for iss in all_issues:
                f.write(f"  {iss['file']} | {iss['type']} | {iss.get('detail','')}\n")
        print(f"报告已保存: {report_path}")

        # 尝试修复 (只修复 mask 质量问题, 不修复 ID/坐标问题)
        fixable = [i for i in all_issues if i["type"] in
                    {"rect_fallback", "under_seg", "over_seg", "too_few_pts"}]
        print(f"\n可修复问题 (mask质量): {len(fixable)}")

        # 坐标越界问题: 直接 clip 修复
        coord_issues = [i for i in all_issues if i["type"] == "coord_out_of_range"]
        if coord_issues:
            print(f"坐标越界: {len(coord_issues)} 个 -> 自动 clip 到 [0,1]")
            clip_coord_fixes(coord_issues)

        if fixable:
            print("\n开始自动修复 mask 质量问题...")
            fixed, fixed_files_record = fix_issues(all_issues)
            print(f"\n修复完成! 成功修复: {fixed}/{len(fixable)}")

            # 生成修复前后对比图
            generate_visual_report(fixed_files_record, n_samples=args.n_visual)

            # 修复后重新检查
            print("\n--- 修复后重新检查 ---")
            remaining = 0
            for split in SPLITS:
                result = check_split(split)
                n = len(result["issues"])
                remaining += n
                if n > 0:
                    by_t = defaultdict(int)
                    for iss in result["issues"]:
                        by_t[iss["type"]] += 1
                    detail = ", ".join(f"{t}:{c}" for t, c in by_t.items())
                    print(f"  {split}: 仍有 {n} 个问题 ({detail})")
            if remaining == 0:
                print("  所有问题已解决!")
    else:
        print("所有标签质量正常! 无需修复")

    print(f"\n{'='*60}")
    print("质量检查完成!")
    print(f"  报告: {GYU_DET_DIR / 'qa_report.txt'}")
    if fixed_files_record:
        print(f"  对比图: {GYU_DET_DIR / 'qa_visual_report/'}")
    print(f"  (可直接用于项目展示视频)")


def clip_coord_fixes(coord_issues):
    """修复坐标越界: clip 到 [0, 1]"""
    files_to_fix = defaultdict(set)
    for iss in coord_issues:
        files_to_fix[iss["file"]].add(iss.get("line", -1))

    for split in SPLITS:
        seg_dir = GYU_DET_DIR / split / split / "labels_seg"
        if not seg_dir.exists():
            continue
        for stem, line_idxs in files_to_fix.items():
            seg_file = seg_dir / f"{stem}.txt"
            if not seg_file.exists():
                continue
            lines = seg_file.read_text().strip().split("\n")
            new_lines = []
            for li, line in enumerate(lines):
                if not line.strip():
                    new_lines.append(line)
                    continue
                parts = line.strip().split()
                class_id = parts[0]
                coords = list(map(float, parts[1:]))
                # clip all coords to [0, 1]
                clipped = [max(0.0, min(1.0, c)) for c in coords]
                new_line = class_id + " " + " ".join(f"{c:.6f}" for c in clipped)
                new_lines.append(new_line)
            with open(seg_file, "w") as f:
                f.write("\n".join(new_lines))


if __name__ == "__main__":
    main()
