# Skill: Debug Spider

Fluxo para diagnosticar e corrigir falhas em spiders.

## 🔍 Diagnóstico pelo Sintoma

| Sintoma | Causa provável |
|---|---|
| `CrawlResult` vazio ou todos `None` | Seletor CSS/XPath não encontra elementos |
| `CrawlResult` parcial (alguns campos) | Site mudou estrutura em parte da página |
| Exception na request | Bloqueio de IP, rate limit, SSL, timeout |
| Dados inconsistentes (valores errados) | Lógica de parsing ou ETL incorreta |
| Teste passa mas produção falha | Mock HTML desatualizado |

## 🛠️ Passo a Passo

### 1. Coletar HTML atual (SEMPRE primeiro)
```python
import httpx
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."}
r = httpx.get("https://site.com/ticker/PETR4", headers=headers)
print(r.status_code)
print(r.text[:500])  # primeiros 500 chars para identificar estrutura
```

### 2. Isolar o parsing
```python
from crawler.spiders.target_spider import TargetSpider
spider = TargetSpider()
result = spider.parse("PETR4", html_capturado)
print(result)
```

### 3. Testar seletores isoladamente
```python
from bs4 import BeautifulSoup
soup = BeautifulSoup(html_capturado, "lxml")

# CSS selector
print(soup.select("table.some-class td"))      # retorna lista

# XPath (via lxml direto)
from lxml import etree
tree = etree.HTML(html_capturado)
print(tree.xpath("//table[@class='some-class']//td/text()"))
```

### 4. Comparar seletor antigo vs HTML novo
Se a lista retornar vazia, o seletor está errado para o HTML atual.
Inspecione o HTML capturado e atualize o seletor para o novo padrão.

### 5. Atualizar fixture do teste
Após corrigir o seletor, atualize o `FIXTURE_HTML` no teste unitário com o HTML atual capturado.

## ⚠️ Regras
- Nunca corrija seletores sem ter o HTML atual em mãos.
- Nunca atualize testes com HTML antigo — o teste vai passar mas a prod vai falhar.
- Endpoints públicos (CVM Dados Abertos, B3 arquivos, RSS) podem alterar schema/CSV. Sempre verifique a fonte oficial antes de corrigir parser.
- Se o bloqueio for por IP: tente com `curl_cffi` ou cabeçalhos de browser real no `request_manager`.
