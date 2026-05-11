# Skill: DB Migration Flow

Procedimento para alterações seguras no schema do banco de dados.

## 🔄 Fluxo Completo

### 1. Modificar o modelo
Altere as classes em `crawler/models/models.py`.

### 2. Gerar a revisão
```bash
uv run alembic revision --autogenerate -m "descricao_breve_sem_espacos"
```
> Use sempre o `alembic.ini` da **raiz do projeto** (não o de dentro de `alembic/`).

### 3. Revisar o arquivo gerado
Abrir `alembic/versions/{hash}_descricao.py` e verificar:

**Em `upgrade()`:**
- Nenhum `op.drop_column()` ou `op.drop_table()` não intencional
- Novas colunas `NOT NULL` têm `server_default` se a tabela já contém dados
- Índices nomeados seguem convenção: `ix_{table}_{column}`

**Em `downgrade()`:**
- A operação reverte completamente o que `upgrade()` fez
- Se `upgrade()` criou um índice, `downgrade()` o dropa

### 4. Aplicar
```bash
uv run alembic upgrade head
```

### 5. Validar
Verificar estrutura no banco via DBeaver, psql, ou logs da aplicação.

## ⚠️ Checklist de Segurança
- [ ] Nenhum `DROP` não intencional em `upgrade()`
- [ ] Novas colunas NOT NULL têm `server_default` ou são `nullable=True`
- [ ] `downgrade()` é completo e reversível
- [ ] Índices seguem naming convention `ix_{table}_{column}`
- [ ] Constraints seguem `uq_{table}_{column}` e `fk_{table}_{ref_table}`

## 🚨 Operações de Risco
Antes de rodar em produção qualquer migração com:
- `op.drop_column()` — confirmar se coluna não é usada em código
- `op.drop_table()` — confirmar backup ou que dados são descartáveis
- `op.alter_column(nullable=False)` — garantir que não há `NULL` existente na coluna
