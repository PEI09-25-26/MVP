from ultralytics import YOLO

# 1. Carregar o modelo
model = YOLO('yolov8s.pt') 

# 2. Iniciar o treino (ajusta o batch de acordo com a VRAM da tua placa gráfica)
results = model.train(
    data='data.yaml',
    epochs=100,
    imgsz=800,
    batch=16, # Se der erro de "Out of Memory", reduz para 8 ou 4
    device='mps',
    scale=0.1,    
    degrees=0.0,  
    mosaic=0.5,   
    hsv_h=0.015,
    hsv_s=0.7,    
    hsv_v=0.4,    
    project='runs/detect',
    name='cards_v3_real_cam'
)