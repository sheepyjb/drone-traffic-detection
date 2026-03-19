"""快速测试 SAM2 pipeline (3张图) - 修复中文路径 + CUDA DLL"""
import os, sys, json, glob, time, traceback
from pathlib import Path

# === 修复 CUDA DLL 路径 ===
import glob as _g
for _d in _g.glob("D:/pytorch/Lib/site-packages/nvidia/*/bin"):
    os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")

import cv2
import numpy as np
import onnxruntime as ort
ort.set_default_logger_severity(3)

def cv2_imread(path_str):
    """支持中文路径的 imread"""
    data = np.fromfile(str(path_str), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

class SAM2Enc:
    def __init__(self, path):
        opts = ort.SessionOptions(); opts.log_severity_level = 3
        self.sess = ort.InferenceSession(path, providers=['CUDAExecutionProvider','CPUExecutionProvider'], sess_options=opts)
        print(f"  Providers: {self.sess.get_providers()}")
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
        self.sess = ort.InferenceSession(path, providers=['CUDAExecutionProvider','CPUExecutionProvider'], sess_options=opts)
        print(f"  Providers: {self.sess.get_providers()}")
        self.enc_size = enc_size; self.orig_size = enc_size; self.sf = 4
        self.in_names = [i.name for i in self.sess.get_inputs()]
        self.out_names = [o.name for o in self.sess.get_outputs()]
    def set_size(self, s): self.orig_size = s
    def __call__(self, emb, hr0, hr1, pts, lbls):
        pc = pts[None].copy().astype(np.float32)
        pl = lbls[None].astype(np.float32)
        pc[...,0] *= self.enc_size[1]/self.orig_size[1]
        pc[...,1] *= self.enc_size[0]/self.orig_size[0]
        mi = np.zeros((1,1,self.enc_size[0]//self.sf,self.enc_size[1]//self.sf),dtype=np.float32)
        hm = np.array([0],dtype=np.float32)
        inp = (emb,hr0,hr1,pc,pl,mi,hm)
        o = self.sess.run(self.out_names, {self.in_names[i]:inp[i] for i in range(len(self.in_names))})
        sc = o[1].squeeze(); ms = o[0][0]
        best = ms[np.argmax(sc)]
        return cv2.resize(best, (self.orig_size[1], self.orig_size[0]))

try:
    print("Loading SAM2 Base+...")
    enc = SAM2Enc("D:/服创/models/sam2/sam2.1_hiera_base_plus.encoder.onnx")
    dec = SAM2Dec("D:/服创/models/sam2/sam2.1_hiera_base_plus.decoder.onnx", enc.in_shape[2:])
    print(f"Encoder input: {enc.in_shape}")

    jsons = sorted(glob.glob("D:/服创/GYU-DET/train/train/images/*.json"))[:3]
    print(f"\nTesting {len(jsons)} images...")

    for jf in jsons:
        stem = Path(jf).stem
        img_dir = Path(jf).parent
        img_path = None
        for ext in [".JPG", ".jpg", ".jpeg", ".png"]:
            p = img_dir / f"{stem}{ext}"
            if p.exists(): img_path = p; break
        if not img_path: print(f"  {stem}: no image"); continue

        img = cv2_imread(img_path)
        if img is None: print(f"  {stem}: imread failed"); continue
        h, w = img.shape[:2]

        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
        shapes = [s for s in data["shapes"] if s.get("shape_type") == "rectangle"]

        t0 = time.time()
        hr0, hr1, emb = enc(img)
        t_enc = time.time() - t0

        print(f"\n  {stem}: {w}x{h} | {len(shapes)} bboxes | encode={t_enc:.2f}s")

        for s in shapes[:2]:
            pts = s["points"]
            x1, y1 = min(p[0] for p in pts), min(p[1] for p in pts)
            x2, y2 = max(p[0] for p in pts), max(p[1] for p in pts)
            cx, cy = (x1+x2)/2, (y1+y2)/2

            dec.set_size((h, w))
            t1 = time.time()
            # bbox + center point for higher precision
            mask = dec(emb, hr0, hr1,
                       np.array([[x1,y1],[x2,y2],[cx,cy]], dtype=np.float32),
                       np.array([2,3,1], dtype=np.float32))
            t_dec = time.time() - t1

            binary = (mask > 0).astype(np.uint8)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                c = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(c)
                approx = cv2.approxPolyDP(c, 0.001*cv2.arcLength(c,True), True)
                print(f"    [{s['label']}] area={area:.0f} pts={len(approx)} dec={t_dec*1000:.0f}ms")
            else:
                print(f"    [{s['label']}] NO MASK (range: {mask.min():.2f}~{mask.max():.2f})")

    # === 保存可视化结果 ===
    print("\nSaving visualizations...")
    vis_dir = Path("D:/服创/scripts/sam2_vis")
    vis_dir.mkdir(exist_ok=True)

    # 重新处理第一张图, 保存所有 bbox 的 mask 叠加
    jf = jsons[0]
    stem = Path(jf).stem
    img_dir = Path(jf).parent
    for ext in [".JPG", ".jpg", ".png"]:
        p = img_dir / f"{stem}{ext}"
        if p.exists(): img_path = p; break
    img = cv2_imread(img_path)
    h, w = img.shape[:2]
    with open(jf, "r", encoding="utf-8") as f:
        data = json.load(f)
    shapes = [s for s in data["shapes"] if s.get("shape_type") == "rectangle"]

    hr0, hr1, emb = enc(img)

    # 颜色表
    colors = [(0,0,255),(255,0,0),(0,165,255),(0,255,0),(255,0,255),(255,255,0)]
    overlay = img.copy()
    mask_vis = np.zeros_like(img)

    for i, s in enumerate(shapes):
        pts = s["points"]
        x1, y1 = min(p[0] for p in pts), min(p[1] for p in pts)
        x2, y2 = max(p[0] for p in pts), max(p[1] for p in pts)
        cx, cy = (x1+x2)/2, (y1+y2)/2
        label = s["label"]
        color = colors[i % len(colors)]

        dec.set_size((h, w))
        mask = dec(emb, hr0, hr1,
                   np.array([[x1,y1],[x2,y2],[cx,cy]], dtype=np.float32),
                   np.array([2,3,1], dtype=np.float32))

        binary = (mask > 0).astype(np.uint8)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            # mask 填充
            cv2.fillPoly(mask_vis, [c], color)
            cv2.fillPoly(overlay, [c], color)
            # 轮廓线
            cv2.drawContours(overlay, [c], -1, color, 2)
            # 标签
            cv2.putText(overlay, label, (int(x1), int(y1)-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        # bbox 虚线框
        cv2.rectangle(overlay, (int(x1),int(y1)), (int(x2),int(y2)), color, 1)

    # 半透明叠加
    result = cv2.addWeighted(img, 0.5, overlay, 0.5, 0)

    # 保存
    def cv2_imwrite(path, img):
        ext = Path(path).suffix
        ok, buf = cv2.imencode(ext, img)
        if ok: buf.tofile(str(path))

    cv2_imwrite(vis_dir / f"{stem}_original.jpg", img)
    cv2_imwrite(vis_dir / f"{stem}_mask.jpg", mask_vis)
    cv2_imwrite(vis_dir / f"{stem}_overlay.jpg", result)

    print(f"Saved to: {vis_dir}")
    print(f"  {stem}_original.jpg  - 原图")
    print(f"  {stem}_mask.jpg      - mask 可视化")
    print(f"  {stem}_overlay.jpg   - 叠加效果")

    print("\n=== TEST PASSED! ===")
except Exception:
    traceback.print_exc()
