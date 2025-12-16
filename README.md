# MVP
This repository contains the implementation of the project's Minimal Viable Product (MVP).

## Como Executar

### Passo 1: Iniciar o CV Service (Terminal 1)
```bash
cd backend/ComputerVision_1.0
uvicorn cv_service:app --host 0.0.0.0 --port 8001 --reload
```

### Passo 2: Iniciar o Middleware (Terminal 2)
```bash
cd middleware
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Passo 3: Iniciar o Game Engine (Terminal 3)
```bash
cd backend/ComputerVision_1.0
uvicorn game_service:app --host 0.0.0.0 --port 8002 --reload
```

### Passo 4: Run android-studio