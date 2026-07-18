# CLAUDE.md — Janelas da Barra

Contexto de projeto para assistentes de IA (Claude Code ou similar) e para
humanos. Lê isto antes de tocar no código.

## O que é isto

Planeador informal de **janelas de manobra na barra do Porto de Lisboa**.
Cruza três fontes e produz um painel estático mobile-first (`index.html`):

1. **APL** (portodelisboa.pt) — chegadas (ETA), navios em porto, partidas (ETD)
2. **Open-Meteo** (Marine + Forecast) — swell, mar total, período, direção,
   nível do mar modelado e vento, na coordenada da aproximação à Barra Sul
3. **`regras.toml`** — motor de regras com limiares editáveis que classifica
   cada hora como **verde / âmbar / vermelho** e avalia UKC por navio

Publicação: GitHub Actions corre o script a cada 30 min e publica em
GitHub Pages. O utilizador final abre um link no telemóvel.

## O que isto NÃO é (não-objetivos)

- **Não é ferramenta operacional.** Não substitui JUP, VTS-Lisboa, Capitania,
  tabelas do Instituto Hidrográfico nem o juízo do piloto. O banner de aviso
  no HTML é obrigatório — nunca o remover nem suavizar.
- Não é um clone do MarineTraffic. O valor está no **cruzamento** de fontes e
  nas **regras codificadas**, não no tracking.
- Não faz AIS em direto (ficou no projeto irmão `painel_barra.py`; pode ser
  reintegrado — ver Roadmap).

## Estrutura

```
janelas-barra/
├── janelas_barra.py          # script único: recolha + regras + HTML
├── regras.toml               # ÚNICO sítio onde vivem limiares numéricos
├── index.html                # gerado; não editar à mão
├── requirements.txt
├── .github/workflows/atualizar.yml
├── README.md                 # setup para humanos
└── CLAUDE.md                 # este ficheiro
```

Fluxo em `janelas_barra.py` (por ordem no ficheiro):
`carregar_regras` → `recolher_meteomar` → `avaliar_hora`/`avaliar_ukc`
→ `recolher_apl` → `extrair_navios` → `gerar_html` → `main`.

## A regra de ouro deste projeto

**Nenhum número de decisão entra no código.** Todos os limiares vivem em
`regras.toml`, cada um com um campo `fonte` de três tipos:

| fonte             | significado                                           |
|-------------------|-------------------------------------------------------|
| `APL/Capitania`   | regulamento/edital público — citar qual               |
| `PIANC/prática`   | prática internacional razoável como ponto de partida  |
| `PLACEHOLDER`     | defeito conservador inventado — **por validar com o piloto** |

Placeholders aparecem a magenta no painel de propósito: a dívida de validação
deve ser visível. Ao receber limiares reais do piloto, atualizar o valor E a
fonte. Nunca "promover" um placeholder a fonte validada sem confirmação humana
explícita. Nunca inventar profundidades, calados ou critérios de fecho da
barra em texto ou código — se falta um dado, marcar `PLACEHOLDER`.

## Fontes de dados: particularidades

- **APL**: os dados vêm da API JSON pública do portal (Liferay):
  `POST https://www.portodelisboa.pt/api/jsonws/invoke` com corpo
  `{"/apl.processosweb/get-chegadas": {"dataIni": "YYYY-MM-DD", "dataFim": ...}}`
  (idem `get-partidas`; existe ainda
  `/apl.processoswebemporto/get-navios-em-porto`, sem parâmetros, não usado).
  Responde a `urllib` simples — **não é preciso browser headless**; o
  Playwright foi removido em 2026-07-18 depois de descobrir a API (os
  serviços estão visíveis no JS público das páginas de chegadas/partidas).
  Campos úteis: `navio`, `eta`/`etd`, `ata`/`atd` (reais — se preenchidos, a
  escala já se concretizou), `caladoMaxEntrada`/`caladoMaxSaida`,
  `nv_tipoNavio`, `zona`, `imo`. A resposta pode incluir duplicados — o
  próprio portal deduplica por (navio, eta); `extrair_navios` faz o mesmo.
  A consulta é a um endpoint público; se o projeto crescer, o caminho certo é
  pedir acesso formal aos dados à APL.
- **Open-Meteo**: grátis, sem chave, CORS aberto. `sea_level_height_msl` é
  **maré modelada relativa ao MSL**, não a tabela oficial do IH — o cálculo
  de UKC soma `canal.profundidade_zh + nivel_mar`, o que mistura referenciais
  (ZH vs MSL). É uma aproximação assumida; está no rodapé do painel e é o
  item nº 1 do Roadmap.
- **Fuso horário**: pedimos `Europe/Lisbon` à API; as ETAs da APL são hora
  local. Manter tudo em hora local, sem conversões.

## Convenções

- Português europeu em código, comentários, UI e commits. Terminologia
  náutica correta (calado, UKC, enfiamento, preia-mar/baixa-mar).
- Um só ficheiro Python enquanto for razoável (< ~700 linhas). Sem
  frameworks nem dependências externas; stdlib apenas (3.11+: `tomllib`).
- HTML gerado por f-string no próprio script; sem templates externos.
  Design tokens: tinta `#1B2A38`, água `#DCEBF1`, papel `#F7F5EF`,
  magenta `#B0257C`; estados verde `#1E7A5A` / âmbar `#E2B93B` /
  vermelho `#C0392B`.
- Falhas de rede degradam com aviso, nunca com crash silencioso: painel
  parcial é aceitável, painel enganador não é.

## Comandos

```bash
python janelas_barra.py                # recolha completa → index.html
python janelas_barra.py --sem-apl      # teste rápido só com meteo-mar
python janelas_barra.py --horas 96     # horizonte alargado
python -m py_compile janelas_barra.py  # sanity check
```

Teste offline (sem rede): construir uma lista `previsao` fictícia e chamar
`avaliar_hora`, `extrair_navios`, `avaliar_ukc` e `gerar_html` diretamente —
ver exemplo no histórico do projeto. Qualquer alteração ao motor de regras ou
ao parser deve passar por este teste antes de commit.

## Estado atual e dívidas conhecidas

- [x] ~~Scraping APL nunca foi corrido contra o site real~~ — resolvido em
      2026-07-18: o site não usa `<table>` (grelha React) e as páginas de
      chegadas/partidas exigem pesquisa por datas; substituído o scraping
      DOM pela API JSON pública (ver "Fontes de dados"), validada em local
      e em produção.
- [ ] UKC mistura referenciais ZH/MSL (ver acima) e ignora squat e resposta
      vertical à ondulação — é UKC estático simplificado.
- [ ] Todos os limiares de swell/vento/período são PLACEHOLDER.
- [ ] `canal.profundidade_zh = 15.0` é ilustrativo — confirmar com carta IH.

## Roadmap (por ordem de valor)

1. Substituir nível do mar Open-Meteo por previsão de marés do IH
   (ou calibrar o offset MSL↔ZH para Cascais/Lisboa).
2. Sessão com o piloto: validar/preencher `regras.toml` e a coordenada
   `[local]`; registar cada decisão no campo `fonte`.
3. Reintegrar snapshot AIS (aisstream.io, chave em secret `AISSTREAM_KEY`)
   para posições em direto no painel.
4. Alertas (e-mail/Telegram) quando um navio da lista cai em janela vermelha.
5. Regras por classe de navio (LOA/calado/tipo) em vez de globais.
