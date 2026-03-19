#!/bin/bash
# ── DroneVehicle 训练启动脚本 ──
# 使用 tmux 后台运行, 关闭 SSH 不影响训练
#
# 用法:
#   bash run_train.sh 1           # 启动消融实验一 (baseline)
#   bash run_train.sh 2           # 启动消融实验二 (P2)
#   bash run_train.sh 1 --resume  # 断点续训消融一
#   bash run_train.sh 2 --resume  # 断点续训消融二
#
# 查看训练:
#   tmux attach -t train          # 进入训练终端
#   Ctrl+B 然后按 D              # 退出但不中断训练
#
# 查看日志:
#   tail -f /root/autodl-tmp/train.log

set -e

ABLATION=${1:-1}
RESUME=${2:-""}
SESSION="train"
LOGFILE="/root/autodl-tmp/train.log"

# 安装 ultralytics (首次)
if ! python -c "import ultralytics" 2>/dev/null; then
    echo "Installing ultralytics..."
    cd /root/autodl-tmp/yolo26-main/ultralytics-main && pip install -e . -q
fi

# 选择脚本
if [ "$ABLATION" = "1" ]; then
    SCRIPT="/root/autodl-tmp/train_ablation1_baseline.py"
    echo ">>> 消融实验一: YOLO26-S Baseline (P3/P4/P5)"
elif [ "$ABLATION" = "2" ]; then
    SCRIPT="/root/autodl-tmp/train_ablation2_p2.py"
    echo ">>> 消融实验二: YOLO26-S + P2 检测头"
else
    echo "用法: bash run_train.sh [1|2] [--resume]"
    exit 1
fi

# 构建命令
CMD="python $SCRIPT"
if [ "$RESUME" = "--resume" ]; then
    CMD="$CMD --resume"
    echo ">>> 模式: 断点续训"
else
    echo ">>> 模式: 从头训练"
fi

# 杀掉旧的 tmux session (如果存在)
tmux kill-session -t $SESSION 2>/dev/null || true

# 在 tmux 中启动训练
echo ">>> 启动 tmux session: $SESSION"
echo ">>> 日志: $LOGFILE"
tmux new-session -d -s $SESSION "$CMD 2>&1 | tee $LOGFILE"

echo ""
echo "✓ 训练已在后台启动!"
echo ""
echo "常用命令:"
echo "  tmux attach -t train        # 查看训练进度"
echo "  Ctrl+B 然后按 D             # 退出终端 (训练继续)"
echo "  tail -f $LOGFILE   # 查看日志"
echo "  tmux kill-session -t train  # 强制停止训练"
