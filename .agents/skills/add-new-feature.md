# Skill: Add New Feature (Cross-Domain)

Fluxo completo para adicionar uma feature end-to-end: desde o modelo até a API exposta.

## 🗺️ Ordem de Implementação

### Fase 1 — Domínio de Dados (Data Master)
1. Definir ou atualizar o modelo em `crawler/models/models.py`
2. Atualizar `CrawlResult` em `crawler/models/contract.py` se a feature expõe novos campos
3. Gerar e revisar migração → ver skill `db-migration.md`

### Fase 2 — Extração (Crawler Specialist)
4. Criar ou atualizar spider em `crawler/spiders/` → ver skill `new-spider.md`
5. Registrar na chain em `crawler/engine/crawler_engine.py`

### Fase 3 — Serviços
6. Adicionar método CRUD em `crawler/services/data_service.py`
7. Adicionar lógica de limpeza/validação em `crawler/services/etl_service.py` se necessário

### Fase 4 — API (API Architect)
8. Criar schema de resposta em `api/schemas.py`
9. Criar endpoint no router adequado em `api/routers/` → ver skill `api-standard-endpoint.md`
10. Registrar router em `api/main.py` se for novo arquivo

### Fase 5 — Testes (Test Guardian)
11. `tests/unit/test_{spider_name}_spider.py` — parsing e fallback
12. `tests/unit/test_{service_name}.py` — CRUD e ETL
13. `tests/integration/` — fluxo completo se a feature é crítica

### Fase 6 — Validação Final
14. `uv run ruff check .` → zero erros
15. `uv run pytest` → todos passando
16. Testar manualmente: `uv run python main.py`
17. Testar API: `uv run uvicorn api.main:app --reload`

## ⚠️ Regras de Ordem
- **Nunca implemente API antes do modelo** — o schema depende do modelo.
- **Nunca escreva spider sem CrawlResult** — o engine espera esse contrato.
- **Nunca faça merge sem testes passando** — CI irá falhar de qualquer forma.

## 🤖 Agentes por Fase
| Fase | Agente |
|---|---|
| Modelo + Migração | Data Master |
| Spider + ETL | Crawler Specialist |
| Serviços CRUD | Data Master ou Crawler Specialist |
| API + Schemas | API Architect |
| Testes | Test Guardian |
| Docker/CI | DevOps Engineer |
