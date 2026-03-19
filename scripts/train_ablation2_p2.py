"""
消融实验 配置二: YOLO26-S + P2 小目标检测头 (P2/P3/P4/P5)
RGB 单模态, 增加 stride=4 的高分辨率检测层
"""

import sys
sys.path.insert(0, "/root/autodl-tmp/yolo26-main/ultralytics-main")

from ultralytics import YOLO


def train():
    # P2 检测头: 4 层输出, stride=4 捕获极小目标
    model = YOLO("yolo26s-p2.yaml")
    model.load("/root/autodl-tmp/yolo26-main/yolo26s.pt")

    model.train(
        data="/root/autodl-tmp/dataset/data.yaml",

        # 基础
        epochs=200,
        patience=50,
        batch=12,              # P2 多一层特征图, 显存稍大, 用 12
        imgsz=864,             # 更大输入, 接近原图 840x712, 配合 P2 发挥
        device=0,

        # 优化器
        lr0=0.01,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3.0,
        warmup_momentum=0.8,
        warmup_bias_lr=0.1,
        cos_lr=True,

        # 数据增强
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

        # 输出
        project="/root/autodl-tmp/runs/detect",
        name="ablation2_yolo26s_p2",
        exist_ok=True,
        save_period=20,
        plots=True,
        workers=8,
        seed=42,
        amp=True,
    )


if __name__ == "__main__":
    train()
