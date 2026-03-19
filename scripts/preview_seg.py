"""
预览 SAM2 生成的 YOLO-seg 标注效果
同时绘制: 原始 YOLO bbox (白色虚线) + SAM2 seg mask (彩色半透明) + 类别标签

用法:
    python preview_seg.py --root /root/autodl-tmp/dataset --split valid --n 10
    python preview_seg.py --root /root/autodl-tmp/dataset --split train --n 5
"""
import argparse
import random
from pathlib import Path

import cv2
import numpy as np


COLORS = [
    (0, 0, 255),      # crack - 红
    (255, 0, 0),      # spalling - 蓝
    (0, 165, 255),    # rebar_exposure - 橙
    (0, 255, 0),      # corrosion - 绿
    (255, 0, 255),    # efflorescence - 紫
    (255, 255, 0),    # water_seepage - 青
]
NAMES = ['crack', 'spalling', 'rebar_exposure', 'corrosion', 'efflorescence', 'water_seepage']


def find_image(img_dir, stem):
    for ext in ['.jpg', '.JPG', '.jpeg', '.png', '.PNG', '.bmp']:
        p = img_dir / (stem + ext)
        if p.exists():
            return p
    return None


def detect_dirs(root, split):
    """自动检测目录结构, 返回 (img_dir, labels_dir, labels_seg_dir)"""
    # 结构A: root/split/split/images/
    p = root / split / split / 'images'
    if p.exists():
        base = root / split / split
        return p, base / 'labels', base / 'labels_seg'
    # 结构B: root/split/images/
    p = root / split / 'images'
    if p.exists():
        base = root / split
        return p, base / 'labels', base / 'labels_seg'
    return None, None, None


def read_yolo_bbox(txt_path, img_w, img_h):
    """读取 YOLO bbox 格式: class_id xc yc w h (归一化)
    返回 [(class_id, x1, y1, x2, y2), ...]
    """
    bboxes = []
    for line in txt_path.read_text().strip().split('\n'):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        cid = int(parts[0])
        xc, yc, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
        x1 = int((xc - bw / 2) * img_w)
        y1 = int((yc - bh / 2) * img_h)
        x2 = int((xc + bw / 2) * img_w)
        y2 = int((yc + bh / 2) * img_h)
        bboxes.append((cid, x1, y1, x2, y2))
    return bboxes


def draw_one(img_path, seg_path, bbox_path):
    img = cv2.imread(str(img_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    overlay = img.copy()

    # --- 1) 画 SAM2 seg mask (彩色半透明 + 轮廓) ---
    for line in seg_path.read_text().strip().split('\n'):
        if not line.strip():
            continue
        parts = line.split()
        cid = int(parts[0])
        coords = list(map(float, parts[1:]))
        pts = np.array(
            [(int(coords[i] * w), int(coords[i+1] * h)) for i in range(0, len(coords), 2)],
            dtype=np.int32
        )
        color = COLORS[cid % len(COLORS)]

        # 半透明填充
        cv2.fillPoly(overlay, [pts], color)
        # 轮廓线
        cv2.drawContours(img, [pts], -1, color, 2)

    result = cv2.addWeighted(img, 0.6, overlay, 0.4, 0)

    # --- 2) 画原始 YOLO bbox (白色虚线 + 类别标签) ---
    if bbox_path is not None and bbox_path.exists():
        bboxes = read_yolo_bbox(bbox_path, w, h)
        for cid, x1, y1, x2, y2 in bboxes:
            color = COLORS[cid % len(COLORS)]
            name = NAMES[cid] if cid < len(NAMES) else str(cid)

            # 虚线矩形
            draw_dashed_rect(result, (x1, y1), (x2, y2), (255, 255, 255), thickness=2, dash=10)

            # 标签背景 + 文字
            label = f'{name} [bbox]'
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            lx, ly = x1, max(y1 - 6, th + 4)
            cv2.rectangle(result, (lx, ly - th - 4), (lx + tw + 4, ly + 2), (0, 0, 0), -1)
            cv2.putText(result, label, (lx + 2, ly - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # --- 3) 左上角图例 ---
    draw_legend(result)

    return result


def draw_dashed_rect(img, pt1, pt2, color, thickness=2, dash=10):
    """画虚线矩形"""
    x1, y1 = pt1
    x2, y2 = pt2
    edges = [
        ((x1, y1), (x2, y1)),  # 上
        ((x2, y1), (x2, y2)),  # 右
        ((x2, y2), (x1, y2)),  # 下
        ((x1, y2), (x1, y1)),  # 左
    ]
    for (sx, sy), (ex, ey) in edges:
        dist = max(abs(ex - sx), abs(ey - sy))
        if dist == 0:
            continue
        dx = (ex - sx) / dist
        dy = (ey - sy) / dist
        i = 0
        while i < dist:
            s = int(i)
            e = int(min(i + dash, dist))
            p1 = (int(sx + dx * s), int(sy + dy * s))
            p2 = (int(sx + dx * e), int(sy + dy * e))
            cv2.line(img, p1, p2, color, thickness)
            i += dash * 2


def draw_legend(img):
    """左上角图例: bbox=白虚线, mask=彩色"""
    cv2.rectangle(img, (8, 8), (200, 52), (0, 0, 0), -1)
    cv2.rectangle(img, (8, 8), (200, 52), (100, 100, 100), 1)
    cv2.putText(img, '--- bbox (original)', (14, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
    cv2.putText(img, 'seg mask (SAM2)', (14, 46),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 200, 255), 1)


def main():
    parser = argparse.ArgumentParser(description="Preview YOLO bbox + SAM2 seg on images")
    parser.add_argument('--root', type=str, required=True, help='Dataset root')
    parser.add_argument('--split', type=str, default='valid', help='Split to preview (default: valid)')
    parser.add_argument('--n', type=int, default=10, help='Number of images (default: 10)')
    parser.add_argument('--out', type=str, default=None, help='Output directory (default: root/preview)')
    args = parser.parse_args()

    root = Path(args.root)
    img_dir, lbl_dir, seg_dir = detect_dirs(root, args.split)

    if img_dir is None or seg_dir is None or not seg_dir.exists():
        print(f"ERROR: Cannot find dirs for split '{args.split}' in {root}")
        return

    seg_files = list(seg_dir.glob('*.txt'))
    if not seg_files:
        print(f"ERROR: No seg label files in {seg_dir}")
        return

    n = min(args.n, len(seg_files))
    samples = random.sample(seg_files, n)

    out_dir = Path(args.out) if args.out else root / 'preview'
    out_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for sf in samples:
        stem = sf.stem
        img_path = find_image(img_dir, stem)
        if img_path is None:
            print(f"  SKIP: no image for {stem}")
            continue

        # 原始 bbox 标签
        bbox_path = lbl_dir / (stem + '.txt') if lbl_dir else None

        result = draw_one(img_path, sf, bbox_path)
        if result is None:
            print(f"  SKIP: cannot read {img_path}")
            continue

        out_path = out_dir / f'{stem}_vis.jpg'
        cv2.imwrite(str(out_path), result)
        saved += 1
        print(f"  [{saved}/{n}] {out_path.name}")

    print(f"\nDone! {saved} images saved to: {out_dir}")


if __name__ == '__main__':
    main()
