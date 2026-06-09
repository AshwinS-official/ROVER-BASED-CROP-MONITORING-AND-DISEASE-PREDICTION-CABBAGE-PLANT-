from ultralytics import YOLO

if __name__ == "__main__":
    # Load YOLOv8 medium model
    model = YOLO("traininbase/yolov8n.pt")

    # Train the model
    model.train(
        data="D:\CODE\PYCHARM\SAVE FILES\project1\work\data.yaml",
        epochs=80,  # more learning
        imgsz=640,
        batch=2,
        device=0,
        workers=0,
        single_cls=True,
        patience=20,  # early stop if no improvement
        cos_lr=True,  # smoother convergence
        augment=True
    )
