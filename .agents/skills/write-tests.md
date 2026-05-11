# Skill: Write Tests

Padrões para testes unitários e de integração neste projeto.

## 🧪 Testes Unitários (tests/unit/)

### Fixtures disponíveis (conftest.py)
| Fixture | Tipo | Uso |
|---|---|---|
| `db_session` | `Session` (SQLite) | Queries e persistência em testes |
| `data_service` | `DataService` | CRUD de Company, StockPrice, Fundamental |
| `etl_service` | `ETLService` | Validação e transformação de dados |

### Padrão para spider
```python
from crawler.spiders.target_spider import TargetSpider
from crawler.models.contract import CrawlResult

FIXTURE_HTML = "<html>...</html>"  # HTML real capturado do site

def test_get_items_returns_crawl_result(mocker):
    spider = TargetSpider()
    mocker.patch.object(spider.request_manager, "get", return_value=FIXTURE_HTML)
    result = spider.get_items("PETR4")
    assert isinstance(result, CrawlResult)
    assert result.symbol == "PETR4"

def test_get_items_returns_partial_on_empty_html(mocker):
    spider = TargetSpider()
    mocker.patch.object(spider.request_manager, "get", return_value="<html></html>")
    result = spider.get_items("PETR4")
    assert result is not None
    assert result.symbol == "PETR4"
```

### Padrão para serviço CRUD
```python
from crawler.models.models import Company

def test_save_company_persists(db_session, data_service):
    data_service.save_company(symbol="PETR4", name="Petrobras")
    saved = db_session.query(Company).filter_by(symbol="PETR4").first()
    assert saved is not None
    assert saved.name == "Petrobras"

def test_get_company_not_found_returns_none(data_service):
    result = data_service.get_company("XXXXX")
    assert result is None
```

### Padrão para ETL
```python
def test_etl_rejects_negative_price(etl_service):
    with pytest.raises(ValueError, match="price must be positive"):
        etl_service.validate_price(-1.0)
```

## 🔗 Testes de Integração (tests/integration/)
- Requerem PostgreSQL rodando: `docker-compose up db`
- Cobrem fluxo completo: spider → ETL → `data_service` → query
- Não mockam nada — testam o sistema real

## ⚠️ Regras
- Nunca crie `SessionLocal()` manualmente em testes — use a fixture `db_session`.
- Mocke `request_manager.get()`, não o método `parse()`.
- Um teste = um comportamento verificado. Não acumule múltiplos asserts não relacionados.
- Prefira `assert x == expected, f"got {x}"` para mensagens de erro úteis.
- Nunca use `sleep()` em testes — mocke tempo se necessário.
