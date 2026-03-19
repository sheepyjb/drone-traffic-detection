"""对比 bbox 外扩 vs 无外扩 对 SAM2 mask 质量的影响"""
import os, json, glob, time
from pathlib import Path

# === CUDA DLL ===
import glob as _g
for _d in _g.glob("D:/pytorch/Lib/site-packages/nvidia/*/bin"):
    os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")

import cv2
import numpy as np
import onnxruntime as ort
ort.set_default_logger_severity(3)


def cv2_imread(path_str):
    data = np.fromfile(str(path_str), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

def cv2_imwrite(path, img):
    ext = Path(path).suffix
    ok, buf = cv2.imencode(ext, img)
    if ok: buf.tofile(str(path))


class SAM2Enc:
    def __init__(self, path):
        opts = ort.SessionOptions(); opts.log_severity_level = 3
        self.sess = ort.InferenceSession(path,
            providers=['CUDAExecutionProvider','CPUExecutionProvider'],
            sess_options=opts)
        print(f"  Enc providers: {self.sess.get_providers()}")
        inp = self.sess.get_inputs()
        self.in_names = [i.name for i in inp]
        self.in_shape = inp[0].shape
        self.out_names = [o.name for o in self.sess.get_outputs()]

    def __call__(self, img):
        h, w = self.in_shape[2], self.in_shape[3]
        x = cv2.resize(img, (w, h))
        x = (x/255.0 - [0.485,0.456,0.406]) / [0.229,0.224,0.225]
        x = x.transpose(2,0,1)[None].astype(np.float32)
        o = self.sess.run(self.out_names, {self.in_names[0]: x})
        return o[0], o[1], o[2]


class SAM2Dec:
    def __init__(self, path, enc_size):
        opts = ort.SessionOptions(); opts.log_severity_level = 3
        self.sess = ort.InferenceSession(path,
            providers=['CUDAExecutionProvider','CPUExecutionProvider'],
            sess_options=opts)
        print(f"  Dec providers: {self.sess.get_providers()}")
        self.enc_size = enc_size; self.orig_size = enc_size; self.sf = 4
        self.in_names = [i.name for i in self.sess.get_inputs()]
        self.out_names = [o.name for o in self.sess.get_outputs()]

    def set_size(self, s): self.orig_size = s

    def __call__(self, emb, hr0, hr1, pts, lbls):
        pc = pts[None].copy().astype(np.float32)
        pl = lbls[None].astype(np.float32)
        pc[...,0] *= self.enc_size[1]/self.orig_size[1]
        pc[...,1] *= self.enc_size[0]/self.orig_size[0]
        mi = np.zeros((1,1,self.enc_size[0]//self.sf,self.enc_size[1]//self.sf), dtype=np.float32)
        hm = np.array([0], dtype=np.float32)
        inp = (emb, hr0, hr1, pc, pl, mi, hm)
        o = self.sess.run(self.out_names, {self.in_names[i]:inp[i] for i in range(len(self.in_names))})
        sc = o[1].squeeze(); ms = o[0][0]
        best = ms[np.argmax(sc)]
        return cv2.resize(best, (self.orig_size[1], self.orig_size[0]))


def pad_bbox(bbox, img_w, img_h, padding):
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    px, py = bw * padding, bh * padding
    return [max(0, x1-px), max(0, y1-py), min(img_w, x2+px), min(img_h, y2+py)]


def mask_to_contour(mask):
    binary = (mask > 0).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def compute_iou(mask_a, mask_b):
    a = (mask_a > 0).astype(bool)
    b = (mask_b > 0).astype(bool)
    inter = np.sum(a & b)
    union = np.sum(a | b)
    return inter / union if union > 0 else 0


# ===================== main =====================
print("Loading SAM2 Base+ (Large is busy with batch job)...")
enc = SAM2Enc("D:/服创/models/sam2/sam2.1_hiera_base_plus.encoder.onnx")
dec = SAM2Dec("D:/服创/models/sam2/sam2.1_hiera_base_plus.decoder.onnx", enc.in_shape[2:])

vis_dir = Path("D:/服创/scripts/padding_compare")
vis_dir.mkdir(exist_ok=True)

# 取 5 张有代表性的图 (不同病害类型)
jsons = sorted(glob.glob("D:/服创/GYU-DET/train/train/images/*.json"))
# 挑前 5 张有多个 bbox 的
selected = []
for jf in jsons:
    with open(jf, "r", encoding="utf-8") as f:
        data = json.load(f)
    shapes = [s for s in data["shapes"] if s.get("shape_type") == "rectangle"]
    if len(shapes) >= 2:
        selected.append(jf)
    if len(selected) >= 5:
        break

print(f"\nComparing {len(selected)} images, each bbox with 3 conditions:")
print("  A: no padding (0%)")
print("  B: 5% padding (current setting)")
print("  C: 10% padding (aggressive)")

padding_configs = [
    ("no_pad", 0.0),
    ("pad_5pct", 0.05),
    ("pad_10pct", 0.10),
]

all_results = []

for img_idx, jf in enumerate(selected):
    stem = Path(jf).stem
    img_dir = Path(jf).parent
    img_path = None
    for ext in [".JPG", ".jpg", ".jpeg", ".png"]:
        p = img_dir / f"{stem}{ext}"
        if p.exists(): img_path = p; break
    if not img_path:
        continue

    img = cv2_imread(img_path)
    if img is None:
        continue
    h, w = img.shape[:2]

    with open(jf, "r", encoding="utf-8") as f:
        data = json.load(f)
    shapes = [s for s in data["shapes"] if s.get("shape_type") == "rectangle"]

    # encode once
    hr0, hr1, emb = enc(img)
    dec.set_size((h, w))

    print(f"\n{'='*60}")
    print(f"Image {img_idx+1}: {stem} ({w}x{h}) | {len(shapes)} bboxes")
    print(f"{'='*60}")

    # 每种 padding 生成 mask, 做可视化
    colors = [(0,0,255),(255,0,0),(0,165,255),(0,255,0),(255,0,255),(255,255,0)]
    overlays = {}  # padding_name -> overlay image
    masks_by_config = {}  # (config_name, bbox_idx) -> binary_mask

    for cfg_name, pad_val in padding_configs:
        overlay = img.copy()
        for bi, s in enumerate(shapes[:4]):  # 最多 4 个 bbox
            pts = s["points"]
            x1, y1 = min(p[0] for p in pts), min(p[1] for p in pts)
            x2, y2 = max(p[0] for p in pts), max(p[1] for p in pts)
            label = s["label"]
            color = colors[bi % len(colors)]

            # apply padding
            bbox = pad_bbox([x1,y1,x2,y2], w, h, pad_val)
            cx, cy = (bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2

            mask = dec(emb, hr0, hr1,
                       np.array([[bbox[0],bbox[1]],[bbox[2],bbox[3]],[cx,cy]], dtype=np.float32),
                       np.array([2,3,1], dtype=np.float32))

            masks_by_config[(cfg_name, bi)] = mask

            contour = mask_to_contour(mask)
            if contour is not None:
                area = cv2.contourArea(contour)
                approx = cv2.approxPolyDP(contour, 0.001*cv2.arcLength(contour,True), True)
                cv2.drawContours(overlay, [contour], -1, color, 2)
                cv2.fillPoly(overlay, [contour], color)
                # 原始 bbox (白色虚线)
                cv2.rectangle(overlay, (int(x1),int(y1)), (int(x2),int(y2)), (255,255,255), 1)
                # padded bbox (黄色)
                if pad_val > 0:
                    cv2.rectangle(overlay, (int(bbox[0]),int(bbox[1])), (int(bbox[2]),int(bbox[3])), (0,255,255), 1)
                cv2.putText(overlay, f"{label}", (int(x1), int(y1)-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                print(f"  [{cfg_name}] {label}: area={area:.0f} pts={len(approx)}")
            else:
                print(f"  [{cfg_name}] {label}: NO MASK")

        # 半透明叠加
        result = cv2.addWeighted(img, 0.5, overlay, 0.5, 0)
        # 标注 padding 信息
        cv2.putText(result, f"Padding: {pad_val*100:.0f}%", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,255,0), 3)
        overlays[cfg_name] = result

    # === IoU 对比: no_pad vs pad_5pct ===
    print(f"\n  IoU comparison (no_pad vs pad_5pct):")
    for bi, s in enumerate(shapes[:4]):
        m_a = masks_by_config.get(("no_pad", bi))
        m_b = masks_by_config.get(("pad_5pct", bi))
        if m_a is not None and m_b is not None:
            iou = compute_iou(m_a, m_b)
            area_a = np.sum(m_a > 0)
            area_b = np.sum(m_b > 0)
            diff_pct = (area_b - area_a) / max(area_a, 1) * 100
            label = s["label"]
            print(f"    {label}: IoU={iou:.4f} | area_diff={diff_pct:+.1f}%")
            all_results.append({
                "image": stem, "label": label,
                "iou": iou, "area_diff_pct": diff_pct,
                "area_nopad": int(area_a), "area_pad5": int(area_b),
            })

    # 横向拼接 3 种结果
    imgs_row = [overlays[n] for n, _ in padding_configs]
    # resize to same height
    target_h = 600
    resized = []
    for im in imgs_row:
        ratio = target_h / im.shape[0]
        resized.append(cv2.resize(im, (int(im.shape[1]*ratio), target_h)))
    combined = np.hstack(resized)
    cv2_imwrite(vis_dir / f"{stem}_compare.jpg", combined)
    print(f"  Saved: {vis_dir / f'{stem}_compare.jpg'}")

# === 汇总 ===
print(f"\n{'='*60}")
print("SUMMARY: no_pad vs pad_5pct")
print(f"{'='*60}")
ious = [r["iou"] for r in all_results]
diffs = [r["area_diff_pct"] for r in all_results]
print(f"  Samples: {len(all_results)}")
print(f"  IoU mean: {np.mean(ious):.4f} (min={np.min(ious):.4f}, max={np.max(ious):.4f})")
print(f"  Area diff mean: {np.mean(diffs):+.2f}% (min={np.min(diffs):+.2f}%, max={np.max(diffs):+.2f}%)")
if np.mean(ious) > 0.90:
    print("  => 结论: 5% 外扩对 mask 影响极小 (IoU>0.90), 不会显著改变量化结果")
elif np.mean(ious) > 0.80:
    print("  => 结论: 5% 外扩有一定影响但可接受, mask 边界略有调整")
else:
    print("  => 结论: 5% 外扩影响较大, 建议检查具体案例")

print(f"\n可视化对比图已保存到: {vis_dir}/")
print("每张图从左到右: 无外扩 | 5%外扩 | 10%外扩")
print("白色框 = 原始 bbox, 黄色框 = 外扩后 bbox")
