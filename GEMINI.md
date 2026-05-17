# GEMINI.md - Project Governance

Este arquivo define as regras de arquitetura, padrões e orquestração de IA para o projeto `stock-market-crawler`.

## 🏗️ Princípios de Arquitetura
1. **Agnostic Data Lake**: Este projeto é um reservatório agnóstico de dados financeiros e inteligência de mercado (LagoAI). Ele **não** gerencia usuários, planos ou portfolios. Essas responsabilidades pertencem ao serviço `rendaraq`.
2. **Crawler Engine**: Segue um padrão similar ao Scrapy, com `spiders` isoladas, um `engine` central e `services` para persistência e processamento.
2. **API (FastAPI)**: Camada de exposição de dados. Deve manter separação clara entre roteadores, schemas (Pydantic) e lógica de dependência.
3. **Data Flow**: Spiders -> Services (DataService/ETL) -> Database (PostgreSQL via SQLAlchemy/Alembic).
4. **Testing**: TDD é mandatório. Testes unitários para lógica de spiders/serviços e integração para fluxos de banco de dados.

## 🤖 Agentes Especializados do Projeto
Os agentes abaixo são extensões locais e devem ser adotados para tarefas específicas.

- **Crawler Specialist**: Especialista em `crawler/spiders/` e `crawler/engine/`. Focado em extração de dados, gestão de seletores (XPath/CSS) e resiliência de requests.
- **API Architect (Stock)**: Focado em `api/`. Especialista em FastAPI, performance de endpoints e segurança de dados financeiros.
- **Data & Migration Master**: Responsável por `crawler/models/` e `alembic/`. Garante integridade referencial e performance de queries.

## 🛠️ Procedimentos Técnicos (Skills)
- `new-spider`: Guia para implementação de novas spiders respeitando a `BaseSpider`.
- `db-migration-flow`: Processo padrão para alterações de schema via Alembic.
- `api-standard-endpoint`: Padrão para novos endpoints financeiros.

## 📜 Regras de Prompting & Eficiência
- **Contexto Cirúrgico**: Sempre use caminhos absolutos e evite buscas globais recursivas (`**/*`) sem necessidade.
- **Token Economy**: O arquivo `.geminiignore` está configurado para ignorar o diretório `output/` e artefatos de build. Se precisar analisar um arquivo de saída, peça-o explicitamente.
- **Broken Selectors**: Ao corrigir spiders, sempre peça um fragmento do HTML atual antes de tentar adivinhar o novo seletor. Compare com o seletor antigo documentado na spider.
- **Dry-Run**: Ao testar spiders, use flags de `limit` se disponíveis para evitar logs massivos no terminal.

## 🧪 Estratégia de Testes
1. **Mocks**: Use mocks para chamadas de rede nas spiders (`pytest-mock`).
2. **Database Clean-up**: Garanta que testes de integração limpem o banco de teste após a execução (veja `tests/conftest.py`).
