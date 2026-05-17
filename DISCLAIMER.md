# Disclaimer & Operator Responsibilities

This repository is a **technical tool** for collecting publicly accessible
financial data from the Brazilian market. The MIT License under which it is
distributed includes an "AS IS, WITHOUT WARRANTY OF ANY KIND" clause: the
author does not guarantee correctness, availability, or suitability for any
particular purpose, and is not liable for how third parties use the code.

If you intend to run this crawler — especially for a commercial product —
read this document in full. The technical posture of the code does **not**
automatically make any specific deployment compliant with the terms of the
sites it touches. Compliance is the **operator's** responsibility.

## Relationship to rendaraq

The author of this repository operates [rendaraq](https://rendaraq.dev), a
commercial product that uses this crawler as one of its data sources. This
repository is **not** the rendaraq application. The crawler is a generic
data-collection engine; rendaraq is one possible consumer of it among many.

Bug reports and contributions should target this repository. Customer
complaints, billing issues, or data takedown requests directed at rendaraq
should go to the rendaraq operator (see the contact channel on the rendaraq
site), not to repository maintainers.

## Data sources and their legal status

The default configuration of this crawler can collect from the following
sources. **Risk** is a rough heuristic; consult a lawyer if you intend to
build a commercial product on top of any of these.

| Source | What it provides | Legal status (informal) | Risk |
|---|---|---|---|
| **CVM** (`dados.cvm.gov.br`) | RI documents (ITR/DFP/IPE), filings | Public acts, [Lei 12.527/2011 (LAI)](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm) and [Lei 9.610/98 Art. 8º, IV](https://www.planalto.gov.br/ccivil_03/leis/l9610.htm) (official acts not subject to copyright) | Low |
| **BCB** (`api.bcb.gov.br`) | Macro indicators (SELIC, IPCA) | Public data, [Banco Central open data policy](https://dadosabertos.bcb.gov.br/) | Low |
| **RSS feeds** (InfoMoney, Valor, Investing, Money Times) | News titles + RSS-published summary + URL | RSS publication implies fair-use re-distribution of the *summary* the publisher chose to expose. **Storing or displaying full article text is not covered.** | Medium |
| **B3** (`arquivos.b3.com.br`) | Listed instruments CSV, historical COTAHIST | Public data published by the exchange itself. Stock prices are facts (not copyrightable). | Low |
| **Yahoo Finance** (`yfinance`) | Quotes, historical prices | Yahoo ToS restricts redistribution; **historical OHLCV is generally tolerated** for educational/personal use. Used only for price history — no proprietary indicators are pulled. | Medium |

> **Removed sources.** Earlier versions of this crawler pulled fundamental
> indicators from third-party aggregators (Fundamentus, StatusInvest). They
> were dropped in 2026-05 because their *databases* (the curated indicator
> rows) are protected as compilations under Lei 9.610/98, even though each
> individual ratio is a numerical fact. The pipeline now reads raw DFP/ITR
> statements from CVM Dados Abertos and computes every indicator locally —
> see [`crawler/services/financial_calculator.py`](./crawler/services/financial_calculator.py).

If you enable a Medium-High risk source for commercial use, you should at a
minimum:

1. **Read and reference the source's ToS** before deployment.
2. **Set `CRAWLER_CONTACT_EMAIL`** in your env so the spider's HTTP `From:`
   header identifies you. This is the RFC 9110 standard signal for "robot
   operator email" and demonstrates good faith if the source ever asks.
3. **Cite the source prominently** in any user-facing surface that displays
   data from it ("via *Source Name*" with a link to the original).
4. **Respect rate limits**. The bundled `RequestManager` already adds
   randomized delays and exponential backoff, but you are responsible for
   tuning them to whatever the source tolerates.
5. **Honor takedown requests promptly** (see below).

## Takedown channel

If you are a publisher whose content has been re-distributed by an instance
of this crawler and you want it removed, contact the **operator** of the
deployment you observed — not the upstream repository maintainer.

For the rendaraq deployment specifically, the takedown channel is documented
on the rendaraq site. For any other operator running this code, ask them
directly (the `CRAWLER_CONTACT_EMAIL` env value, if set, is a good starting
point — its purpose is exactly to be the operator's point of contact).

The upstream repository can disable a source registry entry centrally if a
recurring complaint pattern emerges, but it does not control how individual
operators deploy the code.

## What this document is *not*

- It is **not legal advice**. It is a heuristic checklist by a developer for
  other developers. If you are deploying commercially, consult a lawyer
  specialized in Brazilian copyright law and online ToS enforcement.
- It is **not a license substitute**. The MIT license at `./LICENSE`
  controls; this document is supplementary context.
- It is **not a guarantee** that following every step here will prevent a
  lawsuit. It is a posture: demonstrating good faith and acting in the open
  reduces friction and exposure, but does not eliminate it.
