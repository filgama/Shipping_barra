# Design — Expansão para portos da Europa (UI em inglês)

Data: 2026-07-19. Estado: aprovado por diretiva do utilizador ("agora quero
isto para todos os portos da europa, altera o site de acordo… acho que deve
ficar em inglês"). Decisões de detalhe tomadas autonomamente pelo
orquestrador; podem ser revistas.

## Objetivo

Transformar o painel de janelas de manobra — hoje exclusivo da barra do
Porto de Lisboa — num painel multi-porto que cobre os principais portos
comerciais da Europa, com a interface em inglês. O valor central mantém-se:
cruzar previsão meteo-oceanográfica com um motor de regras transparente
(verde/âmbar/vermelho) e mostrar o resultado num site estático mobile-first.

## Interpretação do âmbito

"Todos os portos da Europa" lê-se como **catálogo extensível dos ~45
principais portos comerciais europeus** (Roterdão, Antuérpia, Hamburgo,
Algeciras, Valência, Pireu, Gdansk, …, mantendo os portugueses). Cobrir
literalmente todos os portos e marinas (milhares) não é viável nem útil.
Acrescentar um porto passa a ser acrescentar uma entrada num TOML.

## Abordagens consideradas

1. **Página única com todos os portos** — rejeitada: ilegível em mobile
   com 40+ portos; tempo de carregamento e scroll absurdos.
2. **Landing page + página estática por porto (escolhida)** — mantém o
   modelo "estático no GitHub Pages, zero backend"; escala para dezenas de
   portos; Lisboa mantém as secções ricas (APL, AIS) sem as impor aos
   restantes.
3. **SPA com chamadas Open-Meteo no browser** — rejeitada: duplicaria o
   motor de regras em JS, violando a regra de ouro (limiares num só sítio)
   e a convenção stdlib/sem-frameworks.

## Arquitetura

### Novo ficheiro `portos.toml`

Catálogo de portos, um `[[porto]]` por entrada:

- `slug` (ex.: `rotterdam`) — nome do ficheiro HTML gerado
- `nome` (ex.: `Rotterdam`), `pais` (ISO-2, ex.: `NL`), `bandeira` (emoji)
- `latitude`/`longitude` da **aproximação** ao porto (ponto costeiro para a
  grelha Open-Meteo; precisão ~±0,1° é suficiente — comentário no TOML a
  dizer que são aproximadas e por refinar)
- opcionais: `profundidade_zh` (só onde conhecida; PLACEHOLDER), `ais_bbox`
  (bounding box aisstream; só Lisboa por agora), `apl = true` (só Lisboa —
  ativa chegadas/partidas/em-porto via API APL)

A coordenada em `regras.toml [local]` migra para a entrada de Lisboa em
`portos.toml`; `regras.toml` fica só com limiares de decisão (regra de ouro
intacta).

### Fluxo em `janelas_barra.py` (mantém o nome e o ficheiro único)

```
carregar_regras + carregar_portos
→ para cada porto:
    recolher_meteomar(lat, lon)   # Open-Meteo Marine + Forecast, tz=auto
    avaliar_hora / detetar_estofas / gerar_svg_mare
    se apl: recolher_apl + extrair_navios + filtrar_em_porto + avaliar_ukc
    se ais_bbox e AISSTREAM_KEY: recolher_ais
    gerar_html_porto → ports/<slug>.html
→ gerar_html_landing → index.html
```

- Falha de rede num porto degrada **só esse porto**: a página dele mostra o
  aviso de dados indisponíveis e o cartão na landing marca "no data" — a
  corrida nunca aborta por causa de um porto.
- Cortesia com a API: pequena pausa (~0,3 s) entre portos. Carga: ~45
  portos × 2 pedidos × 48 corridas/dia ≈ 4300 pedidos/dia, dentro do free
  tier do Open-Meteo (10k/dia).
- Fuso horário: `timezone=auto` no Open-Meteo por porto; horas mostradas em
  hora local do porto (nota no rodapé de cada página).

### Landing page (`index.html`)

- Título: **"Port Approach Windows — Europe"**; banner de aviso obrigatório
  em inglês (ver abaixo).
- Grelha de cartões agrupada por país (países por ordem alfabética):
  bandeira + nome, estado atual (farol verde/âmbar/vermelho da hora
  corrente), próxima janela verde ("next green window: Sat 14:00"), link
  para a página do porto.
- Filtro de texto client-side minimalista (input + meia dúzia de linhas de
  JS inline), sem frameworks.

### Página por porto (`ports/<slug>.html`)

- A UI atual traduzida: resumo de agora, timeline interativa de 72 h, curva
  de maré SVG com PM/BM ("HW"/"LW"), tabela "Rules in force", rodapé com
  fontes e dívidas (referencial MSL vs chart datum, etc.).
- **Só Lisboa** acrescenta: Arrivals (ETA) com avaliação UKC por navio,
  Departures, In port, e "In the estuary now (AIS)". UKC por navio só
  existe onde há calados (APL) e profundidade declarada.
- Link "← All ports" para a landing.

### Inglês

- **Toda a UI gerada** passa a inglês, incluindo o banner de aviso:
  "Informal planning aid. Not an operational tool — it does not replace
  port authorities, VTS, pilotage, official tide tables or local
  regulations." (proibido remover ou suavizar, como hoje).
- `descricao` em `regras.toml` traduzem-se (são UI-facing); chaves e campos
  `fonte` mantêm-se como estão.
- Código, comentários, commits e docs continuam em **português europeu**
  (convenção do projeto; CLAUDE.md será atualizado para registar a exceção
  "UI em inglês").
- Nota nova no banner/rodapé: os limiares são **genéricos e não validados
  por porto** — tudo PLACEHOLDER até haver validação local.

### O que NÃO muda

- Motor de regras (`avaliar_hora`, `avaliar_ukc`, estofas) — passa a correr
  por porto mas a lógica é a mesma.
- Cliente WSS do aisstream, API APL, SVG de maré, dark mode, tokens de
  design.
- Stdlib apenas, um ficheiro Python, HTML por f-string.
- CI a cada 30 min; workflow passa a incluir `ports/` no artefacto Pages.

## Testes (`teste_offline.py`)

- Fixtures atuais adaptadas a asserts em inglês.
- Novos testes: geração da landing (cartões, estados, "no data"),
  página de porto genérico (sem secções APL/AIS), página de Lisboa (com
  APL/AIS), `carregar_portos` (validação de campos obrigatórios do
  catálogo).

## Riscos e dívidas assumidas

- Coordenadas de aproximação dos ~45 portos são aproximadas (para o ponto
  de grelha meteo) — refinar com o tempo; não são limiares de decisão.
- Limiares globais aplicados a portos muito diferentes (Báltico vs
  Atlântico) — assumido e sinalizado; a personalização por porto é evolução
  natural do catálogo (`[porto.regras]` overrides, fora deste âmbito).
- Maré continua nível modelado Open-Meteo (dívida nº 1 do roadmap,
  agora multiplicada por porto).
- `janelas_barra.py` vai crescer para ~1800 linhas — aceite; a separação em
  módulos (WSS, HTML) passa a ser a próxima fronteira, registada no
  CLAUDE.md.
