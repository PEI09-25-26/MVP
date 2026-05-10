from ultralytics import YOLO
import torch

class CardClassifier:
    def __init__(self, model_path, min_conf=0.95, imgsz=224):
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[Classifier] Carregando modelo YOLO em {device}...")
        self.model = YOLO(model_path)
        self.model.to(device)
        self.min_conf = min_conf
        self.imgsz = imgsz
        
        # Warm-up
        dummy = torch.zeros((1, 3, 224, 224)).to(device)
        print("[Classifier] Executando warm-up...")
        _ = self.model(dummy)
        print("[Classifier] Modelo pronto!")

    def classify(self, image, require_min_conf=True):
        # image = numpy array (H,W,3), shape ~224x224
        results = self.model(image, imgsz=self.imgsz, verbose=False)
        # Extrair label e confiança
        if results and len(results) > 0:
            class_label = results[0].names[results[0].probs.top1]
            conf = results[0].probs.top1conf.item()
            if (not require_min_conf) or conf >= self.min_conf:
                return class_label, conf
        return None, 0.0