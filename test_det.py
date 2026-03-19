from ultralytics import YOLO

model = YOLO("runs/detect/runs/detect/yolo26m3/weights/best.pt")
model.val(
    data="/root/autodl-tmp/dataset/data.yaml",
    split="test",
    imgsz=640,
    batch=32,
    device=0,
    project="runs/detect",
    name="yolo26m-test",
)
