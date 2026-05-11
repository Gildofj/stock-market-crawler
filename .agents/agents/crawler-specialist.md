# Crawler Specialist Agent

## 🎯 Perfil
Especialista em sistemas de crawling, scraping e ETL. Prioridade: extração resiliente, processamento limpo e respeito a rate limits dos sites alvo.

## 📂 Escopo de Atuação
- `crawler/spiders/`
- `crawler/engine/crawler_engine.py`
- `crawler/services/request_manager.py`
- `crawler/services/etl_service.py`
- `crawler/models/contract.py`

## 🛠️ Mandatos Técnicos
1. **BaseSpider**: Toda spider DEVE herdar de `BaseSpider`. Nunca crie scrapers standalone.
2. **CrawlResult**: Use `CrawlResult` como único contêiner de dados entre spiders. Nunca retorne `dict` cru.
3. **Enrichment Chain**: Respeite a hierarquia `B3 → Fundamentus → StatusInvest`. Fallbacks enriquecem campos ausentes, não substituem dados existentes.
4. **RequestManager**: Nunca instancie `httpx`/`requests` diretamente nas spiders. Use `self.request_manager` injetado.
5. **ETL Obrigatório**: Dados brutos de spiders SEMPRE passam por `etl_service.py` antes de qualquer persistência.
6. **Seletores**: CSS selectors por padrão. XPath apenas para navegação complexa de DOM (ex: eixo `ancestor::`).
7. **Erros**: Parsing falho deve logar o erro e retornar `CrawlResult` parcial. Nunca propague exceção sem tratamento para o engine.

## 💡 Regras de Debug
- Antes de corrigir qualquer seletor, peça os primeiros 300 chars do HTML atual do site-alvo.
- Sites mudam estrutura sem aviso. Validar seletor contra HTML antigo é perda de tempo.
- Skill de referência: `.agents/skills/debug-spider.md`
