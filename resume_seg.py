from ultralytics import YOLO

model = YOLO("runs/segment/yolo26m-seg/weights/last.pt")
model.train(resume=True)
