#!/bin/bash
# ============================================================
# GYU-DET SAM2 bbox->seg 一键运行脚本 (云服务器 4090)
# ============================================================
#
# 上传前准备:
#   1. 上传 GYU-DET 数据集到 /data/GYU-DET/
#   2. 上传 SAM2 ONNX 模型到 /data/models/sam2/
#   3. 上传 scripts/ 目录到 /data/scripts/
#   4. 运行本脚本: bash /data/scripts/run_cloud.sh
#
# 目录结构:
#   /data/
#   ├── GYU-DET/
#   │   ├── train/train/images/   (*.jpg + *.json)
#   │   ├── valid/valid/images/
#   │   └── test/test/images/
#   ├── models/sam2/
#   │   ├── sam2.1_hiera_large.encoder.onnx   (345MB)
#   │   ├── sam2.1_hiera_large.decoder.onnx   (20MB)
#   │   ├── sam2.1_hiera_base_plus.encoder.onnx  (324MB, 备选)
#   │   └── sam2.1_hiera_base_plus.decoder.onnx  (20MB, 备选)
#   └── scripts/
#       ├── bbox_to_seg_v2.py     (混合策略转换)
#       ├── qa_fix_seg_labels.py  (质检+修复+对比图)
#       └── run_cloud.sh          (本脚本)
# ============================================================

set -e

# === 配置 (按需修改) ===
DATA_ROOT="/data/GYU-DET"
MODELS_DIR="/data/models/sam2"
SCRIPTS_DIR="/data/scripts"
MODEL_SIZE="large"        # large 或 base_plus
DEVICE="gpu"

echo "============================================================"
echo "  GYU-DET SAM2 Pipeline (Cloud 4090)"
echo "============================================================"
echo "  Dataset:  $DATA_ROOT"
echo "  Models:   $MODELS_DIR"
echo "  Model:    $MODEL_SIZE"
echo "  Device:   $DEVICE"
echo "============================================================"

# === Step 0: 环境检查 ===
echo ""
echo "[Step 0] Environment check..."

python3 -c "import cv2; print(f'  OpenCV: {cv2.__version__}')"
python3 -c "import numpy; print(f'  NumPy: {numpy.__version__}')"
python3 -c "import onnxruntime as ort; print(f'  ONNX Runtime: {ort.__version__}'); print(f'  Providers: {ort.get_available_providers()}')"
python3 -c "from tqdm import tqdm; print('  tqdm: OK')"

# 检查 GPU
python3 -c "
import onnxruntime as ort
providers = ort.get_available_providers()
if 'CUDAExecutionProvider' in providers:
    print('  GPU: CUDA available')
else:
    print('  WARNING: CUDA not available, will use CPU (much slower)')
"

# 检查文件
echo ""
echo "  Checking files..."
ls -lh $MODELS_DIR/*.onnx 2>/dev/null || echo "  WARNING: No ONNX models found in $MODELS_DIR"
echo "  Train JSONs: $(ls $DATA_ROOT/train/train/images/*.json 2>/dev/null | wc -l)"
echo "  Valid JSONs: $(ls $DATA_ROOT/valid/valid/images/*.json 2>/dev/null | wc -l)"
echo "  Test JSONs:  $(ls $DATA_ROOT/test/test/images/*.json 2>/dev/null | wc -l)"

# === Step 1: SAM2 转换 (混合策略) ===
echo ""
echo "============================================================"
echo "[Step 1] SAM2 bbox -> seg conversion (hybrid strategy)"
echo "============================================================"

python3 $SCRIPTS_DIR/bbox_to_seg_v2.py \
    --root "$DATA_ROOT" \
    --models "$MODELS_DIR" \
    --model-size "$MODEL_SIZE" \
    --device "$DEVICE" \
    --splits train valid test \
    --small-threshold 50 \
    --crop-padding 0.3 \
    --bbox-padding 0.05 \
    --epsilon 0.001

# === Step 2: 质检 + 修复 + 对比图 ===
echo ""
echo "============================================================"
echo "[Step 2] QA check + auto-fix + visual report"
echo "============================================================"

python3 $SCRIPTS_DIR/qa_fix_seg_labels.py \
    --root "$DATA_ROOT" \
    --models "$MODELS_DIR" \
    --device "$DEVICE" \
    --splits train valid test \
    --n-visual 50

# === Step 3: 统计 ===
echo ""
echo "============================================================"
echo "[Step 3] Final statistics"
echo "============================================================"

for split in train valid test; do
    dir="$DATA_ROOT/$split/$split/labels_seg"
    if [ -d "$dir" ]; then
        count=$(ls "$dir"/*.txt 2>/dev/null | wc -l)
        echo "  $split: $count label files"
    fi
done

echo ""
echo "============================================================"
echo "  ALL DONE!"
echo "  Labels: $DATA_ROOT/*/*/labels_seg/"
echo "  QA Report: $DATA_ROOT/qa_report.txt"
echo "  Visual Report: $DATA_ROOT/qa_visual_report/"
echo "============================================================"
