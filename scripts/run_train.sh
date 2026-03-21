#!/bin/bash
# ── DroneVehicle 训练启动脚本 ──
# 使用 tmux 后台运行, 关闭 SSH 不影响训练
#
# 用法:
#   bash run_train.sh 1           # 启动消融实验一 (baseline)
#   bash run_train.sh 2           # 启动消融实验二 (P2)
#   bash run_train.sh 3           # 启动消融实验三 (RGB+IR 融合)
#   bash run_train.sh 1 --resume  # 断点续训
#   bash run_train.sh test 1      # 测试消融一
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

# 测试模式
if [ "$ABLATION" = "test" ]; then
    EXP_NUM=${2:-1}
    case $EXP_NUM in
        1) EXP_NAME="ablation1_yolo26s_baseline" ;;
        2) EXP_NAME="ablation2_yolo26s_p2" ;;
        2hr) EXP_NAME="ablation2_yolo26s_p2_hr" ;;
        3) EXP_NAME="ablation3_yolo26s_fusion" ;;
        *) echo "未知实验号: $EXP_NUM"; exit 1 ;;
    esac
    SCRIPT="/root/autodl-tmp/test_ablation.py"
    CMD="python $SCRIPT --exp $EXP_NAME"
    echo ">>> 测试: $EXP_NAME"
    tmux kill-session -t $SESSION 2>/dev/null || true
    echo ">>> 启动 tmux session: $SESSION"
    tmux new-session -d -s $SESSION "$CMD 2>&1 | tee $LOGFILE"
    echo "✓ 测试已在后台启动! tmux attach -t train 查看"
    exit 0
fi

# 选择脚本
if [ "$ABLATION" = "1" ]; then
    SCRIPT="/root/autodl-tmp/train_ablation1_baseline.py"
    echo ">>> 消融实验一: YOLO26-S Baseline (P3/P4/P5)"
elif [ "$ABLATION" = "2" ]; then
    SCRIPT="/root/autodl-tmp/train_ablation2_p2.py"
    echo ">>> 消融实验二: YOLO26-S + P2 检测头"
elif [ "$ABLATION" = "2hr" ]; then
    SCRIPT="/root/autodl-tmp/train_ablation2_p2_hr.py"
    echo ">>> 消融实验二(高分辨率): YOLO26-S + P2, imgsz=864"
elif [ "$ABLATION" = "3" ]; then
    SCRIPT="/root/autodl-tmp/train_ablation3_fusion.py"
    echo ">>> 消融实验三: YOLO26-S + P2 + RGB-IR 融合 (6ch)"
else
    echo "用法: bash run_train.sh [1|2|2hr|3|test] [--resume]"
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
