from ultralytics import YOLO

model = YOLO("runs/detect/runs/detect/yolo26m3/weights/last.pt")
model.train(resume=True)
