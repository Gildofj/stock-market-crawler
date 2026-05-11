# Skill: API Standard Endpoint

Padrão para novos endpoints financeiros na API.

## 🏗️ Estrutura Completa

### 1. Schema (api/schemas.py)
```python
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class TickerDataRead(BaseModel):
    symbol: str
    value: float
    date: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 2. Router (api/routers/{domain}.py)
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session
from api.deps import get_db
from api.limiter import limiter
from api.schemas import TickerDataRead
from crawler.services.data_service import DataService

router = APIRouter(prefix="/{domain}", tags=["{domain}"])

@router.get("/{ticker}", response_model=TickerDataRead)
@cache(expire=300)
@limiter.limit("30/minute")
async def get_ticker_data(
    ticker: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Retorna dados de {domínio} para o ticker informado.

    - **ticker**: Código do ativo (ex: PETR4, VALE3)
    - **value**: Descrição do campo financeiro (ex: P/L = Preço / Lucro por ação)
    """
    normalized = ticker.upper()
    data = DataService(db).get_by_ticker(normalized)
    if not data:
        raise HTTPException(status_code=404, detail=f"Ticker '{normalized}' não encontrado")
    return data
```

### 3. Registrar o router (api/main.py)
```python
from api.routers import {domain}
app.include_router({domain}.router)
```

## 📋 Checklist
- [ ] Schema com `model_config = ConfigDict(from_attributes=True)`
- [ ] `@cache(expire=N)` com TTL adequado (300 para preços, 3600 para fundamentals, 1800 para companies)
- [ ] `@limiter.limit("X/minute")` presente
- [ ] Ticker normalizado para `upper()` antes da query
- [ ] `HTTPException(404)` para ticker inexistente
- [ ] Docstring explicando os campos financeiros do endpoint
- [ ] Router registrado em `api/main.py`

## TTL Reference
| Endpoint type | expire |
|---|---|
| Preços históricos | 300 (5 min) |
| Fundamentals | 3600 (1h) |
| Lista de empresas | 1800 (30 min) |
| Dados macro | 900 (15 min) |
