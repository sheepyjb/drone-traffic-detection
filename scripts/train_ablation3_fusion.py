"""
消融实验 配置三: YOLO26-S + P2 + 双流 RGB-IR 早期融合 (6通道输入)

方案: 将 RGB(3ch) + IR(3ch) 在输入层拼接为 6ch,
修改第一层 Conv 为 6ch 输入, 其余结构不变。
通过子类化 YOLODataset 和 DetectionTrainer 实现, 不修改 ultralytics 源码。

用法:
  python train_ablation3_fusion.py           # 从头训练
  python train_ablation3_fusion.py --resume  # 断点续训
"""

import sys
import argparse
import cv2
import numpy as np
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, "/root/autodl-tmp/yolo26-main/ultralytics-main")

from ultralytics import YOLO
from ultralytics.data.dataset import YOLODataset
from ultralytics.data.base import imread
from ultralytics.models.yolo.detect.train import DetectionTrainer
from ultralytics.nn.tasks import DetectionModel
from ultralytics.utils import LOGGER
import math

RUN_DIR = "/root/autodl-tmp/runs/detect/ablation3_yolo26s_fusion"


class DualStreamDataset(YOLODataset):
    """
    双流数据集: 加载 RGB + IR 图像, 拼接为 6 通道。
    IR 图像路径通过将 RGB 路径中的 /images/ 替换为 /images_ir/ 获得。
    """

    def load_image(self, i, rect_mode=True):
        """加载 RGB + IR 并拼接为 6 通道"""
        im, f, fn = self.ims[i], self.im_files[i], self.npy_files[i]

        if im is None:
            # 加载 RGB
            rgb = imread(f, flags=self.cv2_flag)
            if rgb is None:
                raise FileNotFoundError(f"Image Not Found {f}")

            # 构造 IR 路径: images/ -> images_ir/
            ir_path = f.replace("/images/", "/images_ir/").replace("\\images\\", "\\images_ir\\")
            ir = imread(ir_path, flags=self.cv2_flag)

            if ir is None:
                # IR 缺失时用零填充
                LOGGER.warning(f"IR image not found: {ir_path}, using zeros")
                ir = np.zeros_like(rgb)

            # 确保 RGB 和 IR 尺寸一致
            if rgb.shape[:2] != ir.shape[:2]:
                ir = cv2.resize(ir, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)

            # 拼接为 6 通道 (BGR_rgb + BGR_ir)
            im = np.concatenate([rgb, ir], axis=2)  # (H, W, 6)

            h0, w0 = im.shape[:2]
            if rect_mode:
                r = self.imgsz / max(h0, w0)
                if r != 1:
                    w, h = (min(math.ceil(w0 * r), self.imgsz), min(math.ceil(h0 * r), self.imgsz))
                    im = cv2.resize(im, (w, h), interpolation=cv2.INTER_LINEAR)
            elif not (h0 == w0 == self.imgsz):
                im = cv2.resize(im, (self.imgsz, self.imgsz), interpolation=cv2.INTER_LINEAR)

            if self.augment:
                self.ims[i], self.im_hw0[i], self.im_hw[i] = im, (h0, w0), im.shape[:2]
                self.buffer.append(i)
                if 1 < len(self.buffer) >= self.max_buffer_length:
                    j = self.buffer.pop(0)
                    if self.cache != "ram":
                        self.ims[j], self.im_hw0[j], self.im_hw[j] = None, None, None

            return im, (h0, w0), im.shape[:2]

        return im, self.im_hw0[i], self.im_hw[i]


class DualStreamTrainer(DetectionTrainer):
    """自定义 Trainer, 使用双流数据集"""

    def build_dataset(self, img_path, mode="train", batch=None):
        """用 DualStreamDataset 替换默认数据集"""
        gs = max(int(self.model.stride.max() if hasattr(self.model, "stride") else 32), 32)
        return DualStreamDataset(
            img_path=img_path,
            imgsz=self.args.imgsz,
            batch_size=batch,
            augment=mode == "train",
            hyp=self.args,
            rect=self.args.rect if mode == "val" else False,
            cache=self.args.cache or None,
            single_cls=self.args.single_cls,
            stride=int(gs),
            pad=0.5 if mode == "val" else 0.0,
            prefix=f"{mode}: ",
            task=self.args.task,
            classes=self.args.classes,
            data=self.data,
            fraction=self.args.fraction if mode == "train" else 1.0,
        )

    def get_model(self, cfg=None, weights=None, verbose=True):
        """创建 6 通道模型"""
        model = DetectionModel(cfg, ch=6, nc=self.data["nc"], verbose=verbose and self.RANK == -1)
        if weights:
            model.load(weights, verbose=verbose)
        return model


def train(resume=False):
    if resume:
        model = YOLO(f"{RUN_DIR}/weights/last.pt")
        model.train(resume=True)
        return

    # 使用自定义 Trainer
    args = dict(
        model="yolo26s-p2.yaml",
        data="/root/autodl-tmp/dataset/data.yaml",
        epochs=200,
        patience=50,
        batch=32,
        imgsz=640,
        device=0,
        lr0=0.01,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=5.0,
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
        project="/root/autodl-tmp/runs/detect",
        name="ablation3_yolo26s_fusion",
        exist_ok=True,
        save_period=20,
        plots=True,
        workers=8,
        seed=42,
        amp=True,
    )

    trainer = DualStreamTrainer(overrides=args)

    # 手动加载预训练权重 (只加载匹配的层, 第一层 6ch Conv 会跳过)
    trainer.train()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    train(resume=args.resume)
