# MVP
This repository contains the implementation of the project's Minimal Viable Product (MVP).

## Como Executar

**IMPORTANTE:** Todos os comandos devem ser executados a partir da raiz do projeto e com a venv ativa:
```bash
cd /Users/lucas/Desktop/PEI/MVP
source venv/bin/activate
```

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

### Passo 4: Iniciar o Bot Service (Terminal 4) - Opcional
```bash
cd backend/ComputerVision_1.0
uvicorn bot_service:app --host 0.0.0.0 --port 8003 --reload
```

### Passo 5: Run android-studio

## Arquitetura dos Serviços

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| CV Service | 8001 | Visão computacional para deteção de cartas |
| Middleware | 8000 | Orquestrador de comunicação |
| Game Engine | 8002 | Motor de jogo e árbitro |
| Bot Service | 8003 | IA que joga como jogador |