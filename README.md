# B3 Stock Market Crawler

Serviço automatizado para coleta de dados fundamentalistas e históricos da B3.

## Funcionalidades
- **Ticker Discovery**: Descobre automaticamente todas as empresas listadas na B3 via StatusInvest.
- **Fundamental Analysis**: Coleta indicadores como P/L, P/VP, DY, ROE, ROIC, Margem Líquida e Dívida Líquida/EBITDA.
- **Preços Históricos**: Busca o histórico de preços dos últimos 3 trimestres via Yahoo Finance.
- **Valuation**: Calcula Preço Justo de Graham, Bazin e um Score de Qualidade customizado.
- **Automação**: Configurado para rodar diariamente via GitHub Actions.

## Como usar

### Localmente
1. Instale as dependências:
   ```bash
   npm install
   ```
2. Execute o crawler:
   ```bash
   npm start
   ```
   *Para limitar o número de tickers (teste):*
   ```powershell
   $env:MAX_TICKERS=10; npm start
   ```

### GitHub Actions
O serviço está configurado em `.github/workflows/daily-sync.yml` para rodar todos os dias às 02:00 UTC. Os resultados são salvos na pasta `output/` do repositório.

## Tecnologias
- **Node.js (LTS)**
- **TypeScript**
- **Cheerio** (Crawler)
- **Yahoo-Finance2** (Dados de mercado)
- **Zod** (Validação de dados)
- **GitHub Actions** (Agendamento)

## Baixo Custo e Eficiência
O projeto utiliza apenas fontes gratuitas e ferramentas de código aberto, garantindo custo zero de manutenção e facilidade de escala.
