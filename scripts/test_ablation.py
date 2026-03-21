"""
通用消融实验测试脚本 — 在 test 集上评估并保存 summary.json

用法:
  python test_ablation.py --exp ablation1_yolo26s_baseline
  python test_ablation.py --exp ablation2_yolo26s_p2
  python test_ablation.py --exp ablation3_yolo26s_fusion
  python test_ablation.py --weights /path/to/best.pt --name custom_test
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "/root/autodl-tmp/yolo26-main/ultralytics-main")

PROJECT = Path("/root/autodl-tmp/runs/detect")
DATA = "/root/autodl-tmp/dataset/data.yaml"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp", type=str, help="实验名, 自动找 best.pt")
    parser.add_argument("--weights", type=str, help="手动指定权重路径")
    parser.add_argument("--name", type=str, help="输出目录名")
    parser.add_argument("--split", default="test", choices=["val", "test"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()

    if args.weights:
        weights = args.weights
    elif args.exp:
        weights = str(PROJECT / args.exp / "weights" / "best.pt")
    else:
        parser.error("需要 --exp 或 --weights")

    if not Path(weights).exists():
        print(f"权重不存在: {weights}")
        return 1

    name = args.name or f"{args.exp}_{args.split}_{datetime.now().strftime('%Y%m%d_%H%M')}"

    from ultralytics import YOLO
    model = YOLO(weights)
    metrics = model.val(
        data=DATA,
        split=args.split,
        imgsz=args.imgsz,
        batch=args.batch,
        device=0,
        project=str(PROJECT),
        name=name,
        exist_ok=True,
        plots=True,
        workers=8,
    )

    box = metrics.box
    speed = metrics.speed or {}
    names = metrics.names or {}

    summary = {
        "weights": weights,
        "split": args.split,
        "imgsz": args.imgsz,
        "mAP50": float(box.map50),
        "mAP50-95": float(box.map),
        "precision": float(box.mp),
        "recall": float(box.mr),
        "speed_ms": {k: float(v) for k, v in speed.items()},
        "per_class": [
            {"class": str(names.get(i, i)), "mAP50-95": float(ap)}
            for i, ap in enumerate(box.maps)
        ],
    }

    out_dir = Path(metrics.save_dir) if hasattr(metrics, "save_dir") else PROJECT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\n{'='*50}")
    print(f"mAP50:    {summary['mAP50']:.4f}")
    print(f"mAP50-95: {summary['mAP50-95']:.4f}")
    print(f"Precision: {summary['precision']:.4f}")
    print(f"Recall:    {summary['recall']:.4f}")
    for c in summary["per_class"]:
        print(f"  {c['class']:12s} mAP50-95={c['mAP50-95']:.4f}")
    print(f"{'='*50}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
