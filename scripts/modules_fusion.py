"""
跨模态注意力融合模块 (Cross-Modal Attention Fusion, CMAF)
及 双流数据加载器

注册到 ultralytics 的自定义模块系统中使用。
"""

import torch
import torch.nn as nn


class CMAF(nn.Module):
    """
    Cross-Modal Attention Fusion
    输入: 两个同尺寸特征图 (RGB分支, IR分支)
    输出: 融合后的特征图

    机制: 双向通道注意力 + 残差融合
    - 对 RGB 特征做 GAP → MLP → Sigmoid 生成 IR 的通道权重
    - 对 IR 特征做 GAP → MLP → Sigmoid 生成 RGB 的通道权重
    - 交叉加权后相加
    """

    def __init__(self, c1, c2=None, reduction=4):
        super().__init__()
        c2 = c2 or c1
        mid = max(c1 // reduction, 16)

        # RGB -> IR attention
        self.rgb_att = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(c1, mid),
            nn.ReLU(inplace=True),
            nn.Linear(mid, c2),
            nn.Sigmoid(),
        )
        # IR -> RGB attention
        self.ir_att = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(c1, mid),
            nn.ReLU(inplace=True),
            nn.Linear(mid, c2),
            nn.Sigmoid(),
        )

        # 1x1 conv to adjust channels if needed
        self.proj = nn.Conv2d(c1, c2, 1) if c1 != c2 else nn.Identity()

    def forward(self, x):
        """x is a list/tuple of [rgb_feat, ir_feat]"""
        if isinstance(x, (list, tuple)):
            rgb, ir = x[0], x[1]
        else:
            # fallback: split along channel dim
            c = x.shape[1] // 2
            rgb, ir = x[:, :c], x[:, c:]

        # Cross attention weights
        w_ir = self.rgb_att(rgb).unsqueeze(-1).unsqueeze(-1)   # RGB guides IR
        w_rgb = self.ir_att(ir).unsqueeze(-1).unsqueeze(-1)    # IR guides RGB

        # Weighted fusion
        fused = self.proj(rgb) * w_rgb + self.proj(ir) * w_ir
        return fused


class DualConcat(nn.Module):
    """
    简单拼接两个分支的特征用于 YAML 中的 Concat 替代。
    输入: [rgb_feat, ir_feat] (list)
    输出: cat along channel dim
    """
    def __init__(self, dimension=1):
        super().__init__()
        self.d = dimension

    def forward(self, x):
        return torch.cat(x, self.d)
