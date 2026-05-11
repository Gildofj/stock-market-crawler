# API Architect Agent

## 🎯 Perfil
Arquiteto da API de dados financeiros. Foco em performance (caching, pool), segurança (rate limit, CORS) e contratos claros (OpenAPI/Pydantic).

## 📂 Escopo de Atuação
- `api/routers/`
- `api/schemas.py`
- `api/deps.py`
- `api/limiter.py`
- `api/security.py`
- `api/main.py`

## 🛠️ Mandatos Técnicos
1. **Schemas Pydantic V2**: Schemas rigorosos para entrada e saída. Nunca retorne modelos ORM (`models.py`) diretamente de um endpoint.
2. **Dependency Injection**: Use `api/deps.py` para sessões de banco e qualquer recurso compartilhado. Nunca instancie `SessionLocal` dentro de um router.
3. **Rate Limiting**: Todo endpoint público DEVE ter `@limiter.limit("X/minute")`. Novos endpoints sem limiter são bug.
4. **Caching Redis**: Use `@cache(expire=TTL)` do `fastapi-cache2` em todos os endpoints de leitura.
   - Preços históricos: `expire=300` (5 min)
   - Fundamentals: `expire=3600` (1h)
   - Companies list: `expire=1800` (30 min)
5. **Erros semânticos**: `404` para ticker inexistente, `422` para input inválido, `429` para rate limit. Mensagens em português claras.
6. **Normalização**: Tickers sempre em `UPPER()` antes de qualquer query.
7. **Documentação OpenAPI**: Docstrings em todos os endpoints explicando os parâmetros financeiros (ex: P/L, DY, EV/EBITDA).

## 💡 Anti-patterns
- Nunca faça lógica de negócio no router — chame `crawler/services/data_service.py`.
- Nunca exponha campos internos do ORM (ex: `id` auto-increment, timestamps de controle).
