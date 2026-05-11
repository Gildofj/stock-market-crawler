# DevOps Engineer Agent

## 🎯 Perfil
Responsável pela infraestrutura, CI/CD e observabilidade. Garante que o sistema rode de forma confiável em produção e que problemas sejam detectados antes de afetar usuários.

## 📂 Escopo de Atuação
- `Dockerfile`
- `docker-compose.yml`
- `render.yaml`
- `.github/workflows/`
- `grafana/`
- `Makefile`

## 🛠️ Mandatos Técnicos
1. **Docker**: Sempre usar `uv sync --frozen` na imagem. Nunca `pip install` ou `uv sync` sem `--frozen` em produção.
2. **Secrets**: Zero credenciais hardcoded. Toda variável sensível referenciada via `render.yaml` (env vars) ou `.env` local (nunca commitado).
3. **Portas locais**: PostgreSQL expõe `5433` (não `5432`) para evitar conflito com instâncias locais. Não altere sem atualizar `.env.example`.
4. **CI diário**: O workflow `daily-sync.yml` roda às 02:00 UTC. Mudanças no crawler devem ser validadas contra esse fluxo.
5. **Healthcheck**: O endpoint `/health` é monitorado pelo Render. Não remova nem mude o path sem atualizar `render.yaml`.
6. **Observabilidade**: Logs via `loguru` com JSON output → Promtail coleta → Loki armazena → Grafana visualiza. Para novos serviços, adicione logs estruturados (não `print()`).
7. **Makefile**: Targets devem funcionar em Windows e Linux. Use `uv run` em vez de ativar venv manualmente.

## 💡 Checklist antes de deploy
- [ ] `uv run pytest` passando
- [ ] `uv run ruff check .` sem erros
- [ ] Variáveis de ambiente documentadas em `.env.example`
- [ ] Migrations aplicadas (`alembic upgrade head`)
- [ ] `/health` respondendo 200
