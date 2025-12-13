from ultralytics import YOLO
import numpy as np

class CardClassifier:
    def __init__(self, model_path=None):
        if model_path is None or not model_path:
            # fallback to a default model if not given
            model_path = 'yolov5nu.pt'
        self.model = YOLO(model_path)
        # Class names (update if your model/class order is different)
        self.classnames = [
            "10c", "10d", "10h", "10s", "2c", "2d", "2h", "2s",
            "3c", "3d", "3h", "3s", "4c", "4d", "4h", "4s",
            "5c", "5d", "5h", "5s", "6c", "6d", "6h", "6s",
            "7c", "7d", "7h", "7s", "8c", "8d", "8h", "8s",
            "9c", "9d", "9h", "9s", "Ac", "Ad", "Ah", "As",
            "Jc", "Jd", "Jh", "Js", "Kc", "Kd", "Kh", "Ks",
            "Qc", "Qd", "Qh", "Qs"
        ]
    
    def classify(self, img, conf_threshold=0.5):
        # img: cropped card (numpy array)
        results = self.model(img, conf=conf_threshold, verbose=False)
        boxes = results[0].boxes
        if boxes is not None and len(boxes) > 0:
            # Take the highest confidence detection as card class
            best_box = max(boxes, key=lambda b: b.conf[0] if hasattr(b, "conf") else 0)
            class_id = int(best_box.cls[0])
            confidence = float(best_box.conf[0])
            label = self.classnames[class_id] if class_id < len(self.classnames) else str(class_id)
            return label, confidence
        else:
            return None, 0.0
