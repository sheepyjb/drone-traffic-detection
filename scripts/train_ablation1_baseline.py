"""
消融实验 配置一: YOLO26-S 标准检测头 (P3/P4/P5)
RGB 单模态 Baseline

用法:
  python train_ablation1_baseline.py           # 从头训练
  python train_ablation1_baseline.py --resume   # 断点续训
"""

import sys
import argparse
sys.path.insert(0, "/root/autodl-tmp/yolo26-main/ultralytics-main")

from ultralytics import YOLO

RUN_DIR = "/root/autodl-tmp/runs/detect/ablation1_yolo26s_baseline"


def train(resume=False):
    if resume:
        model = YOLO(f"{RUN_DIR}/weights/last.pt")
        model.train(resume=True)
        return

    model = YOLO("yolo26s.yaml")
    model.load("/root/autodl-tmp/yolo26-main/yolo26s.pt")

    model.train(
        data="/root/autodl-tmp/dataset/data.yaml",
        epochs=200,
        patience=50,
        batch=16,
        imgsz=640,
        device=0,
        lr0=0.01,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3.0,
        warmup_momentum=0.8,
        warmup_bias_lr=0.1,
        cos_lr=True,
        mosaic=1.0,
        close_mosaic=15,
        mixup=0.1,
        copy_paste=0.1,
        degrees=10.0,
        translate=0.2,
        scale=0.5,
        fliplr=0.5,
        flipud=0.5,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        erasing=0.1,
        label_smoothing=0.05,
        multi_scale=True,
        project="/root/autodl-tmp/runs/detect",
        name="ablation1_yolo26s_baseline",
        exist_ok=True,
        save_period=20,
        plots=True,
        workers=8,
        seed=42,
        amp=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="从上次中断处继续训练")
    args = parser.parse_args()
    train(resume=args.resume)
