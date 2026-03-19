#!/bin/bash
# AutoDL 4090 一键部署脚本 — 无人机交通检测后端
# 使用方法：
#   1. 将整个项目上传到 AutoDL: scp -r D:/服创/* root@<autodl-ip>:/root/drone-traffic/
#   2. SSH 登录后执行: bash /root/drone-traffic/deploy/setup_autodl.sh

set -e

PROJECT_ROOT="/root/drone-traffic"
export PROJECT_ROOT

echo "=========================================="
echo "  无人机交通检测系统 — AutoDL 部署"
echo "=========================================="

# 1. 检查 GPU
echo "[1/5] 检查 GPU..."
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || {
    echo "ERROR: 未检测到 GPU"
    exit 1
}

# 2. 安装 Python 依赖
echo "[2/5] 安装 Python 依赖..."
pip install --upgrade pip
pip install fastapi uvicorn[standard] opencv-python-headless numpy PyTurboJPEG
# 如果 AutoDL 镜像已有 PyTorch，跳过；否则：
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 检查 PyTorch + CUDA
python3 -c "import torch; print(f'PyTorch {torch.__version__}, CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"

# 3. 安装 libturbojpeg（加速 JPEG 编码）
echo "[3/5] 安装 TurboJPEG..."
apt-get update -qq && apt-get install -y -qq libturbojpeg 2>/dev/null || true

# 4. 验证模型文件
echo "[4/5] 验证模型文件..."
for model in "ep00_best.pt" "ep01_best(1).pt" "yolo26-main/yolo26m.pt"; do
    if [ -f "$PROJECT_ROOT/$model" ]; then
        echo "  ✓ $model"
    else
        echo "  ✗ $model (未找到，请上传)"
    fi
done

# 5. 启动后端
echo "[5/5] 启动后端..."
echo ""
echo "启动命令："
echo "  cd $PROJECT_ROOT/backend && python main.py"
echo ""
echo "如果要后台运行："
echo "  nohup python main.py > server.log 2>&1 &"
echo ""
echo "AutoDL 端口转发："
echo "  在 AutoDL 控制台 -> 自定义服务 -> 开放 8000 端口"
echo "  或使用 SSH 隧道: ssh -L 8000:localhost:8000 root@<autodl-ip>"
echo ""
echo "前端连接（修改 vite.config.ts 的 proxy target）："
echo "  target: 'http://<autodl-ip>:8000'"
echo ""
echo "=========================================="
echo "  部署准备完成！"
echo "=========================================="
