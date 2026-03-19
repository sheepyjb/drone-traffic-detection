from ultralytics import YOLO

model = YOLO("yolo26m.pt")
model.train(
    data="/root/autodl-tmp/dataset/data.yaml",
    epochs=200,
    imgsz=640,
    batch=16,
    device=0,
    project="runs/detect",
    name="yolo26m",
    cos_lr=True,
    patience=50,
    label_smoothing=0.1,
    mixup=0.15,
    close_mosaic=15,
)
