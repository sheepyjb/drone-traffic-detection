"""
DCGF: Dual-modal Channel-wise Gated Fusion module.

Reference: DVIF-Net (Drone Vehicle Infrared-Visible Fusion Network)
Purpose: Fuse RGB and IR feature maps via channel attention gating.

Usage in YAML config:
  - [[-1, ir_layer_idx], 1, DCGFModule, [out_channels]]
"""

import torch
import torch.nn as nn


class DCGFModule(nn.Module):
    """Channel-wise Gated Fusion for RGB and IR feature maps."""

    def __init__(self, c1, c2):
        """
        Args:
            c1: Total input channels (c_rgb + c_ir from Concat).
            c2: Output channels.
        """
        super().__init__()
        # Channel attention: squeeze via GAP, then excite
        self.gap = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(c1, c1 // 4, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(c1 // 4, c1, bias=False),
            nn.Sigmoid(),
        )
        # Project to output channels
        self.project = nn.Sequential(
            nn.Conv2d(c1, c2, 1, bias=False),
            nn.BatchNorm2d(c2),
            nn.SiLU(inplace=True),
        )

    def forward(self, x):
        """
        Args:
            x: Concatenated [F_rgb, F_ir] tensor [B, c1, H, W].
        Returns:
            Fused tensor [B, c2, H, W].
        """
        # Channel attention gating
        B, C, _, _ = x.shape
        w = self.gap(x).view(B, C)
        w = self.fc(w).view(B, C, 1, 1)
        x = x * w
        return self.project(x)
