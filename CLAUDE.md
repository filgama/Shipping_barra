# CLAUDE.md — Port Approach Windows (Europa)

Contexto de projeto para assistentes de IA (Claude Code ou similar) e para
humanos. Lê isto antes de tocar no código.

## O que é isto

Planeador informal de **janelas de aproximação/manobra em ~50 portos
europeus** (expansão 2026-07-19 do projeto original "Janelas da Barra",
que cobria só a barra do Porto de Lisboa — ver
`docs/2026-07-19-expansao-europa-design.md`). Site estático mobile-first
**em inglês**: uma landing page (`index.html`) com o estado de cada porto e
uma página de detalhe por porto (`ports/<slug>.html`). Fontes:

1. **`portos.toml`** — catálogo dos portos (slug, nome, país, coordenada de
   aproximação; opcionais: `apl`, `ais_bbox`, `profundidade_zh`)
2. **Open-Meteo** (Marine + Forecast) — swell, mar total, período, direção,
   nível do mar modelado e vento, na coordenada de aproximação de CADA
   porto (`timezone=auto` → horas na hora local do porto)
3. **`regras.toml`** — motor de regras com limiares editáveis que classifica
   cada hora como **verde / âmbar / vermelho** e avalia UKC por navio
4. **APL** (portodelisboa.pt) — chegadas (ETA), navios em porto, partidas
   (ETD) — **só para Lisboa** (`apl = true` no catálogo); os outros portos
   não têm fonte equivalente de escalas

Publicação: GitHub Actions corre o script a cada 30 min e publica em
GitHub Pages (`index.html` + `ports/`). O utilizador final abre um link no
telemóvel.

## O que isto NÃO é (não-objetivos)

- **Não é ferramenta operacional.** Em nenhum porto substitui a autoridade
  portuária, o VTS, a pilotagem, as tabelas de maré oficiais nem os
  regulamentos locais (em Lisboa: JUP, VTS-Lisboa, Capitania, IH). O banner
  de aviso no HTML é obrigatório em TODAS as páginas — nunca o remover nem
  suavizar; desde a expansão Europa diz também que os limiares são
  genéricos e não validados por porto.
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
├── regras.toml               # ÚNICO sítio onde vivem limiares numéricos de decisão
├── portos.toml               # catálogo de portos (coordenadas, apl/ais_bbox/profundidade)
├── index.html                # landing gerada; não editar à mão
├── ports/                    # páginas por porto geradas; em .gitignore (CI regenera)
├── requirements.txt
├── docs/                     # documentos de apoio (análise, specs/plans de features)
│   ├── analise_manobrabilidade_lisboa_v2.md
│   ├── 2026-07-19-expansao-europa-design.md
│   └── 2026-07-19-expansao-europa-plan.md
├── .github/workflows/atualizar.yml
├── README.md                 # setup para humanos
└── CLAUDE.md                 # este ficheiro
```

Fluxo em `janelas_barra.py` (por ordem no ficheiro, funções auxiliares
privadas `_get_json`/`_momento`/`cardeal_seta` omitidas):
`carregar_regras`/`carregar_portos` → por porto: `recolher_meteomar(porto)`
→ `avaliar_hora`/`avaliar_ukc` → (se `apl`) `recolher_apl` →
`extrair_navios` → `filtrar_em_porto` → (se `ais_bbox`) `recolher_ais` →
`gerar_svg_mare` → `gerar_html_porto` → `ports/<slug>.html`; no fim,
`gerar_html_landing` → `index.html`. Tudo em `main`.

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
- **Fuso horário**: pedimos `timezone=auto` ao Open-Meteo, por porto — cada
  página mostra a hora LOCAL do porto (o rodapé di-lo); as ETAs da APL são
  hora de Lisboa, que coincide com a hora local dessa página. A landing usa
  UTC explícito no "Updated at". Sem conversões manuais.
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

- **UI em inglês** (desde a expansão Europa, por decisão do utilizador):
  todas as strings visíveis nas páginas geradas, incluindo os campos
  `descricao` de `regras.toml` (são mostrados tal-e-qual). Terminologia
  náutica inglesa correta (draught, UKC, HW/LW, slack water, NM).
- **Código, comentários, identificadores, commits e docs em português
  europeu.** Os identificadores internos (`verde`/`ambar`/`vermelho`,
  `PM`/`BM`, `entrada`/`saída`, classes CSS) ficam em PT — a tradução
  acontece só na apresentação (`ESTADO_ROTULO`, `ESTOFA_ROTULO`,
  `SENTIDO_ROTULO`). Os campos `fonte` de `[[regra]]` em `regras.toml`
  (mostrados na tabela "Rules in force" de cada página de porto) estão em
  **inglês** — são conteúdo visível do site, tal como `descricao`. Os
  restantes `fonte` do ficheiro (`[ukc]`, `[estofa]`, `[dimensoes]`,
  `[[regra_navio]]`, `[notas_regulamentares]`) nunca são renderizados em
  HTML nenhum e continuam em português europeu (proveniência interna, como
  o resto do código/docs).
- Um só ficheiro Python enquanto for razoável — o limite de ~1000 linhas é
  indicativo, não rígido; ultrapassar é tolerável se o ficheiro continuar
  coerente (em 2026-07-19, ~1600 linhas após a expansão Europa; os blocos
  candidatos a módulo próprio, se crescer mais, são o cliente WSS do AIS
  (~250 linhas) e a geração de HTML (`gerar_html_porto`+`gerar_html_landing`)).
  Sem frameworks nem dependências externas; stdlib apenas (3.11+: `tomllib`).
- HTML gerado por f-string no próprio script; sem templates externos.
  Design tokens: tinta `#1B2A38`, água `#DCEBF1`, papel `#F7F5EF`,
  magenta `#B0257C`; estados verde `#1E7A5A` / âmbar `#E2B93B` /
  vermelho `#C0392B`.
- Falhas de rede degradam com aviso, nunca com crash silencioso: painel
  parcial é aceitável, painel enganador não é.

## Comandos

```bash
python janelas_barra.py                # todos os portos → ports/*.html + index.html
python janelas_barra.py --porto lisboa --porto rotterdam   # só estes (teste rápido)
python janelas_barra.py --sem-apl      # saltar API APL (Lisboa fica só meteo-mar)
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
- [x] Expansão Europa (2026-07-19): catálogo `portos.toml` (~50 portos),
      geração multi-porto (`ports/<slug>.html` + landing), UI em inglês.
      Lisboa mantém em exclusivo APL + AIS. Ver
      `docs/2026-07-19-expansao-europa-design.md` e o plano irmão.
- [ ] UKC mistura referenciais ZH/MSL (ver acima) e ignora squat e resposta
      vertical à ondulação — é UKC estático simplificado (agora com margem
      de ondulação aproximada, também PLACEHOLDER).
- [ ] Todos os limiares de swell/vento/período/visibilidade/corrente são
      PLACEHOLDER — e desde a expansão são GLOBAIS: os mesmos números para
      Gdansk e para Algeciras, sem calibração por porto (o banner do site
      avisa). Personalização por porto é o caminho natural (overrides no
      catálogo).
- [ ] `profundidade_zh = 15.0` de Lisboa (portos.toml) é ilustrativo —
      confirmar com carta IH; os outros portos nem têm o campo (UKC não
      avaliado fora de Lisboa).
- [ ] Coordenadas de aproximação dos portos novos são aproximadas (~±0,1°),
      escolhidas para o ponto de grelha meteo — refinar com o tempo.
- [ ] Estofa derivada de PM/BM do nível modelado (Open-Meteo), não da
      estofa real da corrente — desfasamento local não calibrado.
- [ ] O estado "atual" dos cartões da landing usa a hora local da máquina
      do CI como aproximação da hora local de cada porto (desvio máximo
      ~2-3 h nos extremos da Europa) — detalhe autoritativo na página do
      porto.
- [ ] As `[notas_regulamentares]` são específicas de Lisboa mas aparecem em
      todos os portos (assinaladas como tal) — notas por porto são trabalho
      futuro.

## Roadmap (por ordem de valor)

1. Limiares/overrides por porto no catálogo (`[porto.regras]`) — hoje as
   regras são globais para toda a Europa, o que é a maior fraqueza do
   painel multi-porto.
2. Substituir nível do mar Open-Meteo por previsões de maré oficiais
   (IH para PT; equivalentes por país) ou calibrar offsets MSL↔datum.
   A curva SVG existe mas continua alimentada pelo modelo.
3. Sessão com piloto(s): validar/preencher `regras.toml` (e, por porto,
   as futuras overrides); registar cada decisão no campo `fonte`.
4. `profundidade_zh` e `ais_bbox` para mais portos do catálogo (hoje só
   Lisboa tem UKC e AIS).
5. Alertas (e-mail/Telegram) quando um navio da lista de Lisboa cai em
   janela vermelha.
6. Regras por classe de navio (LOA/calado/tipo) em vez de globais.
7. Fontes de escalas (ETA/ETD) para outros portos, se existirem APIs
   públicas equivalentes à da APL.

Concluído entretanto: ~~reintegrar snapshot AIS~~ (2026-07-19, aisstream.io,
secret `AISSTREAM_KEY`).
