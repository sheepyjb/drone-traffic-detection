"""
DroneVehicle RGB 单模态 Baseline 训练脚本
模型: YOLO26-M + P2 小目标检测头
数据集: DroneVehicle (5类车辆)

针对无人机航拍小目标场景调优的超参数:
- P2 检测头: stride=4, 保留极小目标特征
- 大输入分辨率: 864 (接近原图 840x712, 且能被32整除)
- 强 mosaic + copy_paste 增强密集场景
- cos_lr + warmup 稳定训练
- 类别权重平衡长尾分布
"""

import sys
sys.path.insert(0, "/root/autodl-tmp/yolo26-main/ultralytics-main")

from ultralytics import YOLO


def train():
    # ── 模型: YOLO26-M + P2 检测头 ──────────────────────
    # P2 头输出 160x160 特征图 (stride=4), 极大提升小目标召回率
    # 先加载预训练权重, 再切换到 P2 架构
    model = YOLO("/root/autodl-tmp/yolo26-main/ultralytics-main/ultralytics/cfg/models/26/yolo26-p2.yaml")
    model = model.load("/root/autodl-tmp/yolo26-main/yolo26m.pt")

    # ── 训练 ────────────────────────────────────────────
    model.train(
        data="/root/autodl-tmp/dataset/data.yaml",

        # ── 基础参数 ──
        epochs=200,
        patience=50,           # 早停: 50 epoch 无提升则停止
        batch=8,               # P2 头显存占用大, 4090 24GB 用 batch=8
        imgsz=864,             # 接近原图尺寸 840x712, 32 的倍数
        device=0,

        # ── 优化器 (YOLO26 默认 MuSGD) ──
        # optimizer="MuSGD",   # YOLO26 内置, 无需手动指定
        lr0=0.01,              # 初始学习率
        lrf=0.01,              # 最终学习率 = lr0 * lrf = 0.0001
        momentum=0.937,
        weight_decay=0.0005,   # L2 正则化
        warmup_epochs=3.0,     # 预热 3 个 epoch
        warmup_momentum=0.8,
        warmup_bias_lr=0.1,

        # ── 学习率调度 ──
        cos_lr=True,           # 余弦退火

        # ── 数据增强 (针对密集小目标优化) ──
        mosaic=1.0,            # Mosaic: 提升密集场景泛化
        close_mosaic=15,       # 最后 15 epoch 关闭 mosaic 精调
        mixup=0.1,             # MixUp 混合增强
        copy_paste=0.1,        # Copy-Paste: 增加稀有类实例
        degrees=10.0,          # 旋转 ±10° (无人机视角旋转)
        translate=0.2,         # 平移 20%
        scale=0.5,             # 缩放 ±50% (模拟不同飞行高度)
        fliplr=0.5,            # 水平翻转
        flipud=0.5,            # 垂直翻转 (航拍无方向性)
        hsv_h=0.015,           # 色调扰动
        hsv_s=0.7,             # 饱和度扰动
        hsv_v=0.4,             # 亮度扰动 (模拟光照变化)
        erasing=0.1,           # 随机擦除

        # ── 正则化 ──
        label_smoothing=0.05,  # 标签平滑 (5类不需要太强)

        # ── 多尺度训练 ──
        multi_scale=True,      # 每轮随机缩放输入尺寸, 学习尺度不变性

        # ── 输出 ──
        project="/root/autodl-tmp/runs/detect",
        name="yolo26m_p2_rgb_baseline",
        exist_ok=True,
        save=True,
        save_period=20,        # 每 20 epoch 保存一次 checkpoint
        plots=True,            # 生成训练曲线和混淆矩阵
        val=True,

        # ── 其他 ──
        workers=8,
        seed=42,
        verbose=True,
        amp=True,              # 混合精度训练: 加速 + 省显存
    )


if __name__ == "__main__":
    train()
