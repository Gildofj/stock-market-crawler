# Skill: New Spider Implementation

Procedimento completo para criar uma nova spider em `crawler/spiders/`.

## 📋 Checklist de Implementação

### 1. Criar o arquivo
`crawler/spiders/{target}_spider.py`

### 2. Estrutura mínima obrigatória
```python
from crawler.spiders.base_spider import BaseSpider
from crawler.models.contract import CrawlResult

class TargetSpider(BaseSpider):
    name = "target"
    base_url = "https://target.com.br"

    def parse(self, ticker: str, html: str) -> CrawlResult:
        """Extrai dados do HTML e retorna CrawlResult."""
        try:
            soup = BeautifulSoup(html, "lxml")
            # ... extração com CSS selectors
            return CrawlResult(symbol=ticker, ...)
        except Exception as e:
            logger.warning(f"[{self.name}] Parse falhou para {ticker}: {e}")
            return CrawlResult(symbol=ticker)  # parcial, não None

    def get_items(self, ticker: str) -> CrawlResult:
        """Faz a request e chama parse()."""
        html = self.request_manager.get(f"{self.base_url}/{ticker}")
        return self.parse(ticker, html)
```

### 3. CrawlResult — regras
- Sempre retorne um `CrawlResult`, mesmo em falha (retorne parcial).
- Nunca retorne `None`, `dict`, ou objetos raw.
- Campos ausentes ficam `None` — o engine de enriquecimento completa via fallback.

### 4. Registrar no engine
Em `crawler/engine/crawler_engine.py`, adicione a spider na posição correta da chain:
- **Primário** (fonte principal): posição 0
- **Fallback #1**: posição 1 (enriquece campos `None` do resultado primário)
- **Fallback #2**: posição 2 (último recurso)

### 5. Teste unitário
Criar `tests/unit/test_{target}_spider.py`:
```python
def test_parse_returns_crawl_result(mocker):
    spider = TargetSpider()
    mocker.patch.object(spider.request_manager, "get", return_value=FIXTURE_HTML)
    result = spider.get_items("PETR4")
    assert isinstance(result, CrawlResult)
    assert result.symbol == "PETR4"

def test_parse_returns_partial_on_malformed_html(mocker):
    spider = TargetSpider()
    mocker.patch.object(spider.request_manager, "get", return_value="<html></html>")
    result = spider.get_items("PETR4")
    assert result is not None  # nunca deve lançar exceção
    assert result.symbol == "PETR4"
```

## ⚠️ Regras
- Nunca instancie `httpx`/`requests` diretamente — use `self.request_manager`.
- CSS selectors por padrão. XPath apenas para DOM complexo.
- Antes de escrever seletores, peça o HTML atual do site (não assuma que a estrutura é estável).
