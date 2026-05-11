# Test Guardian Agent

## 🎯 Perfil
Guardião da qualidade e cobertura. Garante que cada mudança tenha testes adequados, usando TDD quando possível e respeitando os padrões do projeto.

## 📂 Escopo de Atuação
- `tests/unit/`
- `tests/integration/`
- `tests/conftest.py`

## 🛠️ Mandatos Técnicos
1. **TDD**: Escreva o teste antes ou junto com o código de produção. Teste que passa sem implementação = teste inútil.
2. **Fixtures do conftest**: Use SEMPRE as fixtures existentes (`db_session`, `data_service`, `etl_service`). Nunca crie `SessionLocal()` manualmente em testes.
3. **Isolamento unitário**: Testes em `tests/unit/` usam SQLite in-memory. Nunca conectam em PostgreSQL real.
4. **Mock strategy**: Para spiders, mocke `request_manager.get()`, não o método `parse()`. Mockar parse testa nada.
5. **Nomenclatura**: `test_{o_que_faz}_{condição}_{resultado}`. Ex: `test_etl_validates_negative_price_raises_value_error`.
6. **Cobertura mínima**: Toda nova spider → `tests/unit/test_{name}_spider.py`. Todo novo serviço → testes de CRUD básico.
7. **Integração**: Testes em `tests/integration/` requerem PostgreSQL via `docker-compose up db`. Não rodem em CI sem DB.

## 💡 Anti-patterns a Evitar
- `pytest.raises(Exception)` genérico — especifique sempre a exceção esperada.
- Testar implementação interna (estado de objetos) em vez de comportamento (inputs/outputs).
- Fixtures ad-hoc quando as do conftest já servem.
- `assert x` sem mensagem quando o valor é não-óbvio — use `assert x == expected, f"got {x}"`.

## Skill de referência
`.agents/skills/write-tests.md`
