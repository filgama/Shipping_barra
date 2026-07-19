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
- AIS em direto (secção "No estuário agora") é um snapshot informativo de
  ~60 s via aisstream.io, não tracking contínuo — degrada em silêncio sem a
  chave `AISSTREAM_KEY` (ver "Fontes de dados" e Roadmap item 3).

## Estrutura

```
janelas-barra/
├── janelas_barra.py          # script único: recolha + regras + HTML
├── teste_offline.py          # teste sem rede: fixtures + assert (correr antes de commit)
├── regras.toml               # ÚNICO sítio onde vivem limiares numéricos
├── index.html                # gerado; não editar à mão
├── requirements.txt
├── docs/                     # documentos de apoio (análise, specs/plans de features)
│   └── analise_manobrabilidade_lisboa_v2.md
├── .github/workflows/atualizar.yml
├── README.md                 # setup para humanos
└── CLAUDE.md                 # este ficheiro
```

Fluxo em `janelas_barra.py` (por ordem no ficheiro, funções auxiliares
privadas `_get_json`/`_momento`/`cardeal_seta` omitidas):
`carregar_regras` → `recolher_meteomar` → `avaliar_hora`/`avaliar_ukc`
→ `recolher_apl` → `extrair_navios` → `filtrar_em_porto` →
`gerar_svg_mare` → `gerar_html` → `main`.

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
  `/apl.processoswebemporto/get-navios-em-porto`, sem parâmetros — usado
  para a secção "Em porto" do painel).
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
- **aisstream.io** (AIS em direto, secção "No estuário agora"): WebSocket
  (`wss://stream.aisstream.io/v0/stream`), grátis mediante registo — chave em
  `AISSTREAM_KEY` (env local / secret GitHub). Sem dependências externas: o
  cliente WSS (`_ws_handshake`/`_ws_frame`/`_ws_parse_frame`/`_ws_recv_json`)
  é implementado à mão com `socket`+`ssl`+`base64`+`hashlib`+`struct`. Cada
  recolha (`recolher_ais`) subscreve uma bounding box do estuário do Tejo +
  aproximação à Barra Sul e escuta ~60 s, acumulando `PositionReport` e
  `ShipStaticData` por MMSI (`_agregar_ais`). Nunca lança exceção — falhas
  (sem chave, rede, handshake) viram `erro` no dict devolvido e uma nota/
  aviso discreto no painel, nunca crash.

## Convenções

- Português europeu em código, comentários, UI e commits. Terminologia
  náutica correta (calado, UKC, enfiamento, preia-mar/baixa-mar).
- Um só ficheiro Python enquanto for razoável — o limite de ~1000 linhas é
  indicativo, não rígido; ultrapassar é tolerável se o ficheiro continuar
  coerente (em 2026-07-19, ~1460 linhas, após o pacote de UX da timeline/
  navios/maré e o cliente WSS do AIS — este último é o maior bloco isolado,
  ~250 linhas, candidato natural a módulo próprio se o ficheiro crescer mais).
  Sem frameworks nem dependências externas; stdlib apenas (3.11+: `tomllib`).
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
python janelas_barra.py --sem-ais      # saltar snapshot AIS (aisstream.io)
python janelas_barra.py --horas 96     # horizonte alargado
python -m py_compile janelas_barra.py  # sanity check
python teste_offline.py                # teste offline (obrigatório antes de commit)
```

Teste offline (sem rede): `python teste_offline.py` — fixtures sintéticas
para `avaliar_hora` (incl. sectores que cruzam o Norte), `avaliar_ukc`,
`extrair_navios`, `filtrar_em_porto`, `gerar_svg_mare`, `gerar_html`, o
parser de frames WebSocket (`_ws_parse_frame`), a agregação AIS por MMSI
(`_agregar_ais`) e a distância haversine. Obrigatório antes de qualquer
commit que toque no motor de regras, no parser ou no HTML; o CI corre-o
antes de publicar.

## Estado atual e dívidas conhecidas

- [x] ~~Scraping APL nunca foi corrido contra o site real~~ — resolvido em
      2026-07-18: o site não usa `<table>` (grelha React) e as páginas de
      chegadas/partidas exigem pesquisa por datas; substituído o scraping
      DOM pela API JSON pública (ver "Fontes de dados"), validada em local
      e em produção.
- [x] Funcionalidades entretanto acrescentadas ao painel: curva de maré em
      SVG alinhada à timeline com PM/BM anotadas, secção "Em porto" via
      serviço `get-navios-em-porto` da APL, timeline interativa, dark mode
      automático com `theme-color`, e o CI a correr `teste_offline.py`
      antes de publicar em GitHub Pages.
- [x] Fase 1 (2026-07-19): dados horários alargados a visibilidade, `is_day`
      e corrente (Open-Meteo); regras horárias para visibilidade/corrente/
      embarque do piloto; regra por tipo de navio (RO-RO vs vento); margem
      de ondulação no UKC; deteção de janelas de estofa (PM/BM); rótulos
      GO/GO condicional/NO-GO nos textos de detalhe. Todos os novos
      limiares são PLACEHOLDER (por validar com piloto).
- [ ] UKC mistura referenciais ZH/MSL (ver acima) e ignora squat e resposta
      vertical à ondulação — é UKC estático simplificado (agora com margem
      de ondulação aproximada, também PLACEHOLDER).
- [ ] Todos os limiares de swell/vento/período/visibilidade/corrente são
      PLACEHOLDER.
- [ ] `canal.profundidade_zh = 15.0` é ilustrativo — confirmar com carta IH.
- [ ] Estofa derivada de PM/BM do nível modelado (Open-Meteo), não da
      estofa real da corrente — desfasamento local não calibrado.

## Roadmap (por ordem de valor)

1. Substituir nível do mar Open-Meteo por previsão de marés do IH
   (ou calibrar o offset MSL↔ZH para Cascais/Lisboa). Nota: já existe uma
   curva de maré em SVG no painel (`gerar_svg_mare`, alinhada à timeline
   com PM/BM anotadas), mas continua calculada a partir do nível de mar
   modelado pelo Open-Meteo — este item mantém-se por resolver.
2. Sessão com o piloto: validar/preencher `regras.toml` e a coordenada
   `[local]`; registar cada decisão no campo `fonte`.
3. Reintegrar snapshot AIS (aisstream.io, chave em secret `AISSTREAM_KEY`)
   para posições em direto no painel.
4. Alertas (e-mail/Telegram) quando um navio da lista cai em janela vermelha.
5. Regras por classe de navio (LOA/calado/tipo) em vez de globais.
