#!/bin/bash
# 云服务器环境快速安装
echo "Installing dependencies..."
pip install -r /data/scripts/requirements.txt

# 验证
python3 -c "
import cv2, numpy, onnxruntime, tqdm
print('All dependencies OK')
print(f'  CUDA providers: {onnxruntime.get_available_providers()}')
"
