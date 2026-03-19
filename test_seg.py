from ultralytics import YOLO

model = YOLO("runs/segment/runs/segment/yolo26m-seg/weights/best.pt")
model.val(
    data="/root/autodl-tmp/dataset/data.yaml",
    split="test",
    imgsz=640,
    batch=32,
    device=0,
    project="runs/segment",
    name="yolo26m-seg-test",
)
