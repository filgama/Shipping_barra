# Painel v2 — timeline interativa, maré, dark mode, navios em porto

Data: 2026-07-18 · Estado: aprovado pelo utilizador · Abordagem: A (servidor
gera tudo; JS vanilla mínimo)

## Objetivo

Tornar o painel verdadeiramente utilizável no telemóvel (a interação atual
por `title=` não funciona em ecrã tátil) e enriquecê-lo com a informação
que já é recolhida mas não mostrada, mantendo a filosofia do projeto:
um script Python, stdlib apenas, HTML autocontido, regras em `regras.toml`.

## Âmbito

### 1. Timeline interativa
- Cada `.cel` ganha `data-t` (hora ISO), `data-estado`, `data-motivos`,
  `data-vals` (swell/nível/vento formatados com setas).
- Painel de detalhe `<div id="detalhe">` sob a timeline; toque/clique numa
  célula preenche-o via JS vanilla inline (~50 linhas). `title=` mantém-se
  (rato/desktop e degradação sem JS).
- Marcador de "agora": o JS procura a célula cuja `data-t` coincide com a
  hora local do dispositivo (não a hora de geração — correto mesmo com
  página em cache), marca-a com contorno magenta e faz
  `scrollIntoView({inline:'center'})`. Sem correspondência → sem marcador.
- Contraste: texto das células âmbar passa a escuro (`--tinta`).
- `<meta http-equiv="refresh" content="900">` (15 min).

### 2. Curva de maré (SVG server-rendered)
- No mesmo contentor de scroll da timeline, alinhada célula a célula
  (largura do SVG = n_células × passo).
- Polilinha de `nivel_mar`; preia-mares/baixa-mares (extremos locais)
  anotadas com hora e altura.
- Rótulo: "nível modelado (rel. MSL)" — mantém a ressalva ZH/MSL.
- Sem dados de nível → secção omitida com aviso.

### 3. Setas de direção
- Função graus → (ponto cardeal 16 sectores, seta unicode). O nome do
  sector é a **proveniência** (convenção náutica: swell de NW); a seta
  aponta o rumo do fluxo (dir + 180°).
- Usadas no painel de detalhe e nos `data-vals`.

### 4. Dark mode
- `@media (prefers-color-scheme: dark)` com variantes dos tokens:
  fundo/papel escuros, texto claro, estados e magenta afinados para
  legibilidade. Automático, sem botão.
- `<meta name="theme-color">` para ambos os esquemas.

### 5. Navios em porto
- `recolher_apl` chama também `/apl.processoswebemporto/get-navios-em-porto`
  (sem parâmetros).
- Filtro (técnico, não limiar de decisão — vive no código com comentário):
  ATA preenchida ∧ ATD vazia ∧ ATA nos últimos 30 dias (o serviço devolve
  registos obsoletos de 2020).
- Secção nova compacta entre navios ETA/ETD e regras: nome · tipo ·
  terminal · ETD prevista, com contagem no título.

### 6. Auditoria + teste offline
- Novo `teste_offline.py` (stdlib, sem pytest; `assert` simples):
  - fixtures sintéticas de previsão (verde/âmbar/vermelho, UKC ok/marginal/
    insuficiente, valores em falta);
  - fixtures APL (duplicados, ATA preenchida, calado inválido, datas
    malformadas);
  - `gerar_html` valida presença de strings-chave (aviso obrigatório,
    cartões, detalhe, curva).
- CI: passo "Teste offline" **antes** de "Gerar painel"; falha → não publica.
- Correção de bug: `avaliar_hora` não suporta sectores direcionais que
  cruzam o Norte (ex.: `dir_min=300, dir_max=60` nunca é verdadeiro com
  `dir_min ≤ d ≤ dir_max`). Passa a sector circular:
  `dir_min ≤ dir_max` → intervalo normal; caso contrário
  `d ≥ dir_min ∨ d ≤ dir_max`.

### 7. Documentação
- `CLAUDE.md`: limite "< ~700" → "< ~1000" linhas; teste offline versionado
  e obrigatório antes de commits ao motor de regras/parser; nova secção UI
  (painel de detalhe, curva, dark mode).
- `README.md`: uma linha sobre a interação por toque.

## Fora do âmbito

Marés do IH, AIS em direto, alertas, regras por classe de navio
(continuam no roadmap do CLAUDE.md).

## Critérios de sucesso

1. `python teste_offline.py` passa; `py_compile` limpo.
2. Recolha real local gera painel com: detalhe a funcionar ao toque
   (verificável no HTML: células com `data-*` e bloco JS presente),
   curva de maré alinhada, secção navios em porto preenchida.
3. Workflow verde; painel publicado com as novas secções.
4. Sem regressões: aviso obrigatório presente, placeholders a magenta,
   degradação graciosa mantida em falha de qualquer fonte.

## Notas de arquitetura

- Tudo continua em `janelas_barra.py` (~750–800 linhas) + `teste_offline.py`.
- Sem dependências novas; JS vanilla inline no f-string, SVG gerado em
  Python.
- Ordem das funções no ficheiro mantém o fluxo documentado no CLAUDE.md.
