# Guia de Implantação na VPS Oracle

Este guia descreve os passos necessários para implantar, configurar e operar o `stock-market-crawler` em um servidor VPS (como a VM Always Free da Oracle com 4 núcleos e 24GB de RAM).

A arquitetura de implantação foi otimizada para equilibrar o desempenho máximo do hardware com a economia de recursos de memória (já que a VM é compartilhada com outros serviços):
- **Banco de Dados**: Mantido no **Supabase** (remoto). A conexão utiliza pools otimizados (`pool_size=5`, `max_overflow=10`).
- **Cache**: Redis local rodando em container (~15MB RAM), acelerando leituras e mantendo o cache ativo após reinicializações.
- **Workers**: O Uvicorn está configurado com 4 processos paralelos tanto na API pública quanto no Crawler Worker para aproveitar totalmente os 4 núcleos de CPU.
- **Agendador de Tarefas**: O container `ofelia` gerencia e executa as rotinas cron de scraping internamente no Docker.
- **Observabilidade**: Grafana, Loki, Promtail e Tempo foram movidos para um profile opcional (`observability`), poupando mais de 1.5GB de RAM em produção.

---

## 📋 Pré-requisitos

No seu servidor VPS Oracle, garanta que possui instalado:
1. **Docker** (v20.10+) e **Docker Compose** (v2.0+)
2. **Git**
3. Conexão configurada e credenciais da sua instância no **Supabase**

---

## 🚀 Passo a Passo para Implantação

### 1. Configuração de Variáveis de Ambiente e CI/CD (GitHub Actions)

O arquivo `.env` na VPS é **gerado e sincronizado automaticamente** a cada deploy pelo workflow do GitHub Actions (`deploy.yml`). Você não precisa criar ou editar manualmente o `.env` no servidor em produções subsequentes.

Configure as seguintes variáveis no seu repositório GitHub em **Settings -> Secrets and variables -> Actions**:

#### 🔒 Repository Secrets (Dados Sensíveis)
- `DATABASE_URL`: URL de conexão do Supabase Transaction Pooler (porta 6543)
- `API_KEY`: Chave de API secreta para autenticação nos endpoints
- `VPS_HOST`, `VPS_USERNAME`, `VPS_SSH_KEY`, `VPS_PORT`, `VPS_PROJECT_PATH`: Credenciais de acesso SSH à VPS
- `R2_ACCOUNT_ID`, `R2_API_TOKEN`: (Opcional) Credenciais Cloudflare R2
- `CRAWLER_HTTP_PROXY`, `CRAWLER_HTTPS_PROXY`: (Opcional) Proxies de acesso

#### ⚙️ Repository Variables (Configurações Gerais)
- `ALLOWED_ORIGINS`: Origens permitidas para CORS (ex: `https://app.exemplo.com`)
- `LOG_LEVEL`: Nível de log (default: `INFO`)
- `LOG_FORMAT`: Formato de logs (`human` ou `gcp`)
- `OTEL_ENABLED`: Habilitar OpenTelemetry (`true` ou `false`)

> [!NOTE]
> No primeiro setup manual antes de rodar o CI/CD, você pode copiar `.env.example` para `.env` apenas para validação inicial local.


### 2. Iniciar a Infraestrutura Docker
Execute a stack utilizando o arquivo de compose de produção:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Isso criará e iniciará os seguintes containers em segundo plano:
- `stock_market_crawler_redis` (Porta local 6379)
- `stock_market_crawler_tasks_emulator` (Porta local 8123)
- `stock_market_crawler_api` (Porta local 8000)
- `stock_market_crawler_worker` (Interno, Chromium instalado)
- `stock_market_crawler_scheduler` (Ofelia Cron daemon)

### 3. Rodar as Migrações de Banco de Dados
Com os containers rodando, execute as migrações do Alembic para atualizar o schema do Supabase:

```bash
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

---

## ⏰ Agendamento e Cron (Ofelia)

O container `scheduler` (`ofelia`) está configurado para inspecionar os labels do container `api` e executar as tarefas nos seguintes horários UTC:

- **02:00:00 UTC** (`0 0 2 * * *`): Descobre tickers ativos e enfileira as tarefas diárias (Macro-data e cotações).
- **05:00:00 UTC** (`0 0 5 * * *`): Enfileira a extração diária de notícias da LagoAI e documentos de RI no crawler.

Você pode acompanhar a execução do scheduler nos logs:

```bash
docker logs -f stock_market_crawler_scheduler
```

---

## 🔍 Monitoramento e Verificação

### Verificar Logs dos Workers e API
Como o Uvicorn executa com 4 workers em cada container, você pode filtrar logs gerais do serviço:

```bash
docker logs -f stock_market_crawler_api
docker logs -f stock_market_crawler_worker
```

### Testar Conectividade do Redis
Para inspecionar chaves em cache no Redis local:

```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli KEYS "*"
```

### Acionar Rotinas Manualmente
Caso precise acionar os scrapers fora do cron do scheduler:

```bash
# Executa a descoberta e agendamento de tickers diários
docker compose -f docker-compose.prod.yml exec api python -m scripts.runbooks.enqueue_daily_jobs

# Executa o agendamento de notícias e RI
docker compose -f docker-compose.prod.yml exec api python -m scripts.runbooks.enqueue_lake_jobs
```

---

## 📊 Ativando a Observabilidade (Opcional)

Caso precise rodar o Grafana, Loki, Promtail e Tempo para depurar traces de requisições ou logs na VPS, adicione o profile `observability`:

```bash
# Iniciar stack completa com observabilidade
docker compose -f docker-compose.prod.yml --profile observability up -d

# Parar a stack (incluindo observabilidade)
docker compose -f docker-compose.prod.yml --profile observability down
```

> [!WARNING]
> Ativar o profile de observabilidade consome cerca de **1.5GB a 2GB de RAM adicionais** na VPS. Lembre-se de pará-lo quando concluir a depuração se precisar otimizar o consumo do servidor compartilhado.
