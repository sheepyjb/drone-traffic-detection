from ultralytics import YOLO

model = YOLO("yolo26m-seg.pt")
model.train(
    data="/root/autodl-tmp/dataset/data.yaml",
    task="segment",
    epochs=200,
    imgsz=640,
    batch=16,
    device=0,
    project="runs/segment",
    name="yolo26m-seg",
    patience=50,
    mixup=0.15,
    close_mosaic=15,
    cos_lr=True,
)
