# Plano de Implementação — Expansão multi-porto Europa (UI em inglês)

> **Para agentes:** executar tarefa a tarefa, por ordem. Cada tarefa termina
> com `python teste_offline.py` verde. **Os agentes NÃO fazem commit** — a
> verificação final e os commits ficam com o orquestrador. Spec:
> `docs/2026-07-19-expansao-europa-design.md`.

**Objetivo:** transformar o painel (hoje só barra de Lisboa) num site
multi-porto dos ~48 principais portos europeus, UI em inglês, mantendo o
motor de regras e as secções ricas de Lisboa (APL + AIS).

**Arquitetura:** catálogo `portos.toml` → loop de geração por porto
(`ports/<slug>.html`) + landing `index.html` com estado de cada porto.
Um só ficheiro Python, stdlib apenas, HTML por f-string.

## Restrições globais (aplicam-se a TODAS as tarefas)

- Python 3.11+, **stdlib apenas**; sem frameworks nem templates externos.
- **Nenhum limiar numérico de decisão no código** — só em `regras.toml`
  (e agora `portos.toml` para dados de catálogo), com campo `fonte`
  (`PLACEHOLDER` quando não validado).
- Código, comentários e identificadores em **português europeu**; apenas as
  **strings visíveis ao utilizador** passam a inglês. NÃO renomear
  identificadores internos (`verde`/`ambar`/`vermelho`, classes CSS,
  nomes de funções).
- Banner de aviso obrigatório em TODAS as páginas, nunca suavizado:
  «Informal planning aid — NOT an operational tool. It does not replace
  port authorities, VTS, pilotage, official tide tables or local
  regulations. All thresholds are generic placeholders, not validated for
  any specific port.»
- Falhas de rede degradam com aviso, nunca com crash.
- Design tokens mantêm-se: tinta `#1B2A38`, água `#DCEBF1`, papel
  `#F7F5EF`, magenta `#B0257C`, verde `#1E7A5A`, âmbar `#E2B93B`,
  vermelho `#C0392B`.
- Antes de terminar cada tarefa: `python -m py_compile janelas_barra.py`
  e `python teste_offline.py` (tudo OK).

## Glossário de tradução PT→EN (fechado — usar exatamente isto)

| PT (atual) | EN (novo) |
|---|---|
| Janelas da Barra — Porto de Lisboa | Port Approach Windows — {Nome do porto} |
| (landing) | Port Approach Windows — Europe |
| Chegadas (ETA) | Arrivals (ETA) |
| Partidas (ETD) | Departures (ETD) |
| Em porto | In port |
| No estuário agora (AIS) | Live AIS snapshot |
| Regras em vigor | Rules in force |
| GO condicional | conditional GO |
| preia-mar / PM | high water / HW |
| baixa-mar / BM | low water / LW |
| estofa | slack water |
| calado | draught |
| maré | tide |
| janela verde | green window |
| MN (milhas náuticas) | NM |
| «a X MN da barra» | «X NM off the entrance» |
| seg/ter/qua/qui/sex/sáb/dom | Mon/Tue/Wed/Thu/Fri/Sat/Sun |
| Dados APL indisponíveis… | APL data unavailable this run… |
| AIS inativo (sem chave…) | AIS inactive (no AISSTREAM_KEY configured). |
| Recolha AIS falhou nesta ronda | AIS capture failed this run |
| Sem navios em porto nesta recolha. | No vessels in port in this capture. |
| Sem navios AIS captados… | No AIS vessels captured in this listening window. |
| fonte (rótulo UI) | source |
| Atualizado às | Updated at |
| vento | wind |
| ondulação/swell | swell |
| visibilidade | visibility |
| corrente | current |
| nível do mar | sea level |
| «por validar com o piloto» | «pending validation by a local pilot» |

Terminologia que fica igual: UKC, SOG, COG, LOA, ETA/ETD, IMO, MMSI, GO,
NO-GO. Tudo o resto visível ao utilizador: traduzir com inglês náutico
correto. Datas nos rótulos: formato «Sat 14:00».

---

### Tarefa 1 — Catálogo `portos.toml` + `carregar_portos()`

**Ficheiros:** criar `portos.toml`; modificar `janelas_barra.py` (junto a
`carregar_regras`, linha ~79); modificar `teste_offline.py`.

**Produz:** `carregar_portos() -> list[dict]` — lê `portos.toml`, valida
campos obrigatórios (`slug`, `nome`, `pais`, `bandeira`, `latitude`,
`longitude`), devolve lista de dicts por ordem do ficheiro. `ValueError`
com mensagem clara se faltar campo ou houver slug duplicado.

**Passos:**

- [ ] Criar `portos.toml` com o cabeçalho e o catálogo completo abaixo
  (coordenadas de APROXIMAÇÃO, aproximadas ±0,1°, para o ponto de grelha
  meteo — comentário no ficheiro a dizê-lo; não são limiares de decisão).
  Lisboa migra a coordenada exata de `regras.toml [local]` (38.62, -9.38)
  e leva `apl = true`, `ais_bbox = [[[38.35, -9.75], [38.95, -8.85]]]` e
  `profundidade_zh = 15.0` (movida de `regras.toml [canal]` na Tarefa 2 —
  nesta tarefa apenas duplicada com o mesmo comentário PLACEHOLDER).

```toml
# portos.toml — catálogo de portos do painel.
# Coordenadas = ponto de APROXIMAÇÃO ao porto (para a grelha Open-Meteo),
# aproximadas (~±0,1°), por refinar; NÃO são limiares de decisão.
# Campos opcionais: apl (API do Porto de Lisboa), ais_bbox (aisstream.io),
# profundidade_zh (para UKC; PLACEHOLDER até confirmação em carta oficial).

[[porto]]
slug = "lisboa"
nome = "Lisbon"
pais = "PT"
bandeira = "🇵🇹"
latitude = 38.62
longitude = -9.38
apl = true
ais_bbox = [[[38.35, -9.75], [38.95, -8.85]]]
profundidade_zh = 15.0   # PLACEHOLDER — confirmar com carta IH

[[porto]]
slug = "leixoes"
nome = "Leixões"
pais = "PT"
bandeira = "🇵🇹"
latitude = 41.17
longitude = -8.72
```

  Seguem-se, no mesmo formato mínimo (slug/nome/pais/bandeira/lat/lon):
  Sines PT 37.93 -8.88 · Setúbal PT 38.48 -8.93 ·
  Algeciras ES 36.10 -5.43 · Valencia ES 39.43 -0.30 ·
  Barcelona ES 41.34 2.18 · Bilbao ES 43.37 -3.05 · Vigo ES 42.22 -8.78 ·
  Las Palmas ES 28.13 -15.40 · Le Havre FR 49.47 0.05 ·
  Marseille FR 43.28 5.33 · Dunkirk FR 51.05 2.35 ·
  Saint-Nazaire FR 47.25 -2.30 · Antwerp BE 51.40 3.55 ·
  Zeebrugge BE 51.35 3.18 · Rotterdam NL 51.98 4.05 ·
  Amsterdam (IJmuiden) NL 52.47 4.53 · Hamburg DE 53.98 8.65 ·
  Bremerhaven DE 53.87 8.45 · Wilhelmshaven DE 53.62 8.05 ·
  Aarhus DK 56.15 10.25 · Copenhagen DK 55.70 12.65 ·
  Oslo NO 59.05 10.55 · Bergen NO 60.40 5.30 ·
  Gothenburg SE 57.65 11.75 · Stockholm SE 59.35 18.90 ·
  Helsinki FI 60.12 24.95 · Tallinn EE 59.47 24.75 · Riga LV 57.05 24.02 ·
  Klaipėda LT 55.72 21.08 · Gdańsk PL 54.42 18.70 · Gdynia PL 54.55 18.57 ·
  Felixstowe GB 51.93 1.35 · Southampton GB 50.78 -1.30 ·
  London Gateway GB 51.50 0.90 · Liverpool GB 53.45 -3.10 ·
  Immingham GB 53.63 0.20 · Dublin IE 53.34 -6.10 ·
  Genoa IT 44.38 8.92 · Trieste IT 45.62 13.75 · Livorno IT 43.55 10.28 ·
  Naples IT 40.82 14.25 · Gioia Tauro IT 38.43 15.88 ·
  Piraeus GR 37.92 23.60 · Thessaloniki GR 40.58 22.92 ·
  Marsaxlokk MT 35.82 14.55 · Limassol CY 34.65 33.02 ·
  Koper SI 45.55 13.72 · Rijeka HR 45.30 14.40 ·
  Constanța RO 44.15 28.68 · Varna BG 43.18 27.95
  (bandeiras emoji do país respetivo; slugs em minúsculas sem acentos:
  `sines`, `setubal`, `algeciras`, `valencia`, `barcelona`, `bilbao`,
  `vigo`, `las-palmas`, `le-havre`, `marseille`, `dunkirk`,
  `saint-nazaire`, `antwerp`, `zeebrugge`, `rotterdam`, `amsterdam`,
  `hamburg`, `bremerhaven`, `wilhelmshaven`, `aarhus`, `copenhagen`,
  `oslo`, `bergen`, `gothenburg`, `stockholm`, `helsinki`, `tallinn`,
  `riga`, `klaipeda`, `gdansk`, `gdynia`, `felixstowe`, `southampton`,
  `london-gateway`, `liverpool`, `immingham`, `dublin`, `genoa`,
  `trieste`, `livorno`, `naples`, `gioia-tauro`, `piraeus`,
  `thessaloniki`, `marsaxlokk`, `limassol`, `koper`, `rijeka`,
  `constanta`, `varna`.)

- [ ] Em `janelas_barra.py`, logo após `carregar_regras`:

```python
def carregar_portos() -> list[dict]:
    """Lê portos.toml e valida o catálogo. Campos obrigatórios por porto:
    slug, nome, pais, bandeira, latitude, longitude. Slugs únicos."""
    with open(RAIZ / "portos.toml", "rb") as f:
        dados = tomllib.load(f)
    portos = dados.get("porto", [])
    if not portos:
        raise ValueError("portos.toml sem entradas [[porto]]")
    obrigatorios = ("slug", "nome", "pais", "bandeira",
                    "latitude", "longitude")
    vistos = set()
    for p in portos:
        for campo in obrigatorios:
            if campo not in p:
                raise ValueError(f"porto sem campo '{campo}': {p}")
        if p["slug"] in vistos:
            raise ValueError(f"slug duplicado em portos.toml: {p['slug']}")
        vistos.add(p["slug"])
    return portos
```

- [ ] Teste em `teste_offline.py` (adicionar a `TESTES`):

```python
def teste_carregar_portos():
    portos = jb.carregar_portos()
    assert len(portos) >= 45
    slugs = [p["slug"] for p in portos]
    assert len(slugs) == len(set(slugs))
    lisboa = next(p for p in portos if p["slug"] == "lisboa")
    assert lisboa.get("apl") is True and lisboa.get("ais_bbox")
    assert all("latitude" in p and "longitude" in p for p in portos)
```

- [ ] `python teste_offline.py` → tudo OK.

---

### Tarefa 2 — Motor por-porto (meteo, AIS, regras sem `[local]`)

**Ficheiros:** `janelas_barra.py`, `regras.toml`, `teste_offline.py`.

**Consome:** `carregar_portos()` (T1).
**Produz:** `recolher_meteomar(porto: dict, horas: int) -> list[dict]`;
`recolher_ais(chave, porto, segundos=60) -> dict`;
`_agregar_ais(mensagens, porto) -> list[dict]` (usa
`porto["latitude"]/["longitude"]`); `avaliar_ukc(..., profundidade_zh)`
recebe a profundidade como argumento em vez de a ler de
`regras["canal"]`.

**Passos:**

- [ ] `recolher_meteomar` (linha ~93): trocar `regras["local"]` por
  `porto["latitude"]/porto["longitude"]`; pedir `timezone=auto` (em vez de
  `Europe/Lisbon`) para as DUAS chamadas (Marine e Forecast). Horas
  continuam em hora local — agora do porto.
- [ ] AIS: apagar a constante `AIS_BBOX` (linha ~386); `recolher_ais`
  passa a `recolher_ais(chave, porto, segundos=60)` e usa
  `porto["ais_bbox"]` na subscrição; `_agregar_ais(mensagens, porto)` usa
  `porto["latitude"]/["longitude"]` como referência de distância.
- [ ] `avaliar_ukc` (linha ~192): assinatura
  `avaliar_ukc(calado, nivel_mar, regras, onda_altura=None, profundidade_zh=None)`;
  se `profundidade_zh is None` devolve o mesmo formato mas com avaliação
  «sem dados» (o chamador só invoca quando o porto tem profundidade — o
  argumento existe para o teste ser explícito). Os limiares de folga
  continuam em `regras["ukc"]`.
- [ ] `regras.toml`: remover `[local]` e `[canal]` (migrados para
  `portos.toml` em T1); atualizar comentários. NÃO mexer nos limiares.
- [ ] `teste_offline.py`: fixture nova
  `PORTO_TESTE = {"slug": "teste", "nome": "Testport", "pais": "PT", "bandeira": "🏳", "latitude": 38.62, "longitude": -9.38, "profundidade_zh": 15.0, "ais_bbox": [[[38.35, -9.75], [38.95, -8.85]]]}`;
  adaptar chamadas a `_agregar_ais`/`avaliar_ukc` (o fixture `REGRAS` do
  teste deixa de precisar de `local`/`canal`).
- [ ] `python teste_offline.py` → tudo OK.

---

### Tarefa 3 — `gerar_html_porto` em inglês

**Ficheiros:** `janelas_barra.py` (função `gerar_html`, linhas ~899-1413,
mais `ESTADO_ROTULO`, `DIAS_SEMANA_ABREV`, `resumo_janelas`,
`_fmt_dia_hora`, `JS_PAINEL` se tiver strings visíveis), `regras.toml`
(campos `descricao` e `[notas_regulamentares]` → inglês), `teste_offline.py`.

**Consome:** T1/T2.
**Produz:** `gerar_html_porto(porto, previsao, avaliacoes, navios, apl,
regras, ais=None) -> str` (renomeação de `gerar_html` com parâmetro novo
`porto` à cabeça).

**Passos:**

- [ ] Renomear `gerar_html` → `gerar_html_porto` com `porto` como primeiro
  parâmetro. Título: `Port Approach Windows — {porto['nome']}` (com
  `{porto['bandeira']}`). Link no topo: `<a href="../index.html">← All
  ports</a>`. Nota no rodapé: «All times are local port time.»
- [ ] Secções condicionais: Arrivals/Departures/In port só se
  `porto.get("apl")`; «Live AIS snapshot» só se `porto.get("ais_bbox")`
  (mantendo os estados inativo/erro atuais quando a chave falta). Portos
  sem APL não mostram as secções nem os marcadores de navios na timeline.
- [ ] Traduzir TODAS as strings visíveis usando o glossário do topo do
  plano (inclui `ESTADO_ROTULO[1] = "conditional GO"`,
  `DIAS_SEMANA_ABREV = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]`,
  rótulos PM/BM → HW/LW no SVG da maré, textos de `resumo_janelas`, notas
  AIS «X NM off the entrance», banner obrigatório com o texto exato das
  Restrições Globais). Identificadores internos e classes CSS ficam.
- [ ] `regras.toml`: traduzir os valores de `descricao` (UI-facing) e os
  itens de `[notas_regulamentares]` para inglês; chaves e campos `fonte`
  intactos (o conteúdo de `fonte` fica em PT — é proveniência interna,
  mostrada tal-e-qual; acrescentar ao rodapé: «Threshold provenance notes
  are kept in Portuguese.»).
- [ ] `teste_offline.py`: atualizar asserts PT→EN (ex.: `"No estuário
  agora"` → `"Live AIS snapshot"`, `"AIS: a 3.4 MN da barra"` →
  `"AIS: 3.4 NM off the entrance"`, `"Dados APL indisponíveis"` →
  `"APL data unavailable"`, etc.); todos os `gerar_html(...)` passam a
  `gerar_html_porto(PORTO_TESTE, ...)`. Teste novo:

```python
def teste_html_porto_sem_apl():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    porto_min = {"slug": "rotterdam", "nome": "Rotterdam", "pais": "NL",
                 "bandeira": "🇳🇱", "latitude": 51.98, "longitude": 4.05}
    out = jb.gerar_html_porto(porto_min, prev, avals, [], {}, REGRAS)
    assert "Rotterdam" in out and "Arrivals" not in out
    assert "Live AIS snapshot" not in out
    assert "NOT an operational tool" in out          # banner obrigatório
```

- [ ] `python teste_offline.py` → tudo OK.

---

### Tarefa 4 — Landing page `gerar_html_landing`

**Ficheiros:** `janelas_barra.py` (nova função antes de `main`),
`teste_offline.py`.

**Consome:** estados por porto calculados no loop do `main` (T5); nesta
tarefa a função é pura e testável offline.
**Produz:** `gerar_html_landing(resultados, regras) -> str`, em que
`resultados` é uma lista de dicts:
`{"porto": <dict do catálogo>, "estado_atual": 0|1|2|None, "proxima_verde": str|None, "erro": str|None}`
(`estado_atual=None` + `erro` preenchido = «no data this run»;
`proxima_verde` já formatado, ex.: `"Sat 14:00"` ou `"now"`).

**Passos:**

- [ ] Implementar a função: título «Port Approach Windows — Europe»,
  mesmo `<head>`/tokens/dark-mode das páginas de porto, banner
  obrigatório, cartões agrupados por país (cabeçalho por país com
  bandeira + nome EN do país a partir de um dict módulo-nível
  `PAISES = {"PT": "Portugal", "ES": "Spain", …}` com TODOS os países do
  catálogo — PT ES FR BE NL DE DK NO SE FI EE LV LT PL GB IE IT GR MT CY
  SI HR RO BG —, países por ordem alfabética do nome EN). Cada cartão:
  farol com a cor de `estado_atual` (cinzento `#5C6E7C` se `None`),
  nome + bandeira como link para `ports/<slug>.html`, linha
  «next green window: {proxima_verde}» ou «no green window in 72 h» ou
  «no data this run». Filtro: `<input id="filtro" placeholder="Filter
  ports…">` + JS inline (~10 linhas) que esconde cartões/países sem match
  (case-insensitive, por nome do porto ou país).
- [ ] Rodapé da landing: mesmas fontes/disclaimers das páginas + «Updated
  at {hora} UTC» (na landing usar UTC explícito, porque os portos têm
  fusos diferentes).
- [ ] Testes:

```python
def teste_html_landing():
    resultados = [
        {"porto": {"slug": "lisboa", "nome": "Lisbon", "pais": "PT",
                   "bandeira": "🇵🇹", "latitude": 38.62, "longitude": -9.38},
         "estado_atual": 0, "proxima_verde": "now", "erro": None},
        {"porto": {"slug": "rotterdam", "nome": "Rotterdam", "pais": "NL",
                   "bandeira": "🇳🇱", "latitude": 51.98, "longitude": 4.05},
         "estado_atual": None, "proxima_verde": None,
         "erro": "timeout Open-Meteo"},
    ]
    out = jb.gerar_html_landing(resultados, REGRAS)
    assert "Port Approach Windows — Europe" in out
    assert 'href="ports/lisboa.html"' in out and "Portugal" in out
    assert "no data this run" in out and "Netherlands" in out
    assert "NOT an operational tool" in out
```

- [ ] `python teste_offline.py` → tudo OK.

---

### Tarefa 5 — `main()` multi-porto, CLI, CI e docs

**Ficheiros:** `janelas_barra.py` (`main`, linha ~1415; constantes `SAIDA`
→ `DIR_PORTS`), `.github/workflows/atualizar.yml`, `README.md`,
`CLAUDE.md`, `teste_offline.py` (se necessário).

**Consome:** tudo o anterior.

**Passos:**

- [ ] `main()`: carregar regras + portos; argumento novo
  `--porto <slug>` (repetível; default: todos) para corridas de teste;
  manter `--sem-apl`, `--sem-ais`, `--horas`. Loop:

```python
resultados = []
for porto in portos:
    try:
        previsao = recolher_meteomar(porto, args.horas)
        avaliacoes = [avaliar_hora(h, regras) for h in previsao]
        # APL/AIS só para quem os tem (e sem flags a desligar)
        …
        (RAIZ / "ports").mkdir(exist_ok=True)
        (RAIZ / "ports" / f"{porto['slug']}.html").write_text(
            gerar_html_porto(porto, previsao, avaliacoes, navios,
                             apl, regras, ais=ais), encoding="utf-8")
        resultados.append({"porto": porto, "estado_atual": estado_da_hora_corrente,
                           "proxima_verde": proxima_verde, "erro": None})
    except Exception as exc:            # degrada SÓ este porto
        print(f"[{porto['slug']}] ERRO: {exc}")
        resultados.append({"porto": porto, "estado_atual": None,
                           "proxima_verde": None, "erro": str(exc)})
    time.sleep(0.3)                      # cortesia com o Open-Meteo
(RAIZ / "index.html").write_text(gerar_html_landing(resultados, regras),
                                 encoding="utf-8")
```

  `estado_da_hora_corrente` = estado da primeira hora ≥ agora (hora local
  do porto); `proxima_verde` = «now» se essa hora é verde, senão
  `_fmt_dia_hora` da primeira hora verde, senão `None`. AIS corre no
  máximo uma vez por corrida (só Lisboa tem bbox).
- [ ] Workflow `atualizar.yml`: passo «Preparar artefacto Pages» passa a
  incluir `ports/` além de `index.html`.
- [ ] `.gitignore`/repo: `ports/*.html` são gerados — tratá-los como
  `index.html` (commitados pelo CI no artefacto Pages, não à mão).
- [ ] `README.md` e `CLAUDE.md`: atualizar âmbito (multi-porto Europa),
  estrutura (portos.toml, ports/), convenção nova «UI em inglês; código,
  comentários, commits e docs em PT», comandos (`--porto lisboa`), e mover
  a nota de que limiares são genéricos/PLACEHOLDER por porto. Não remover
  a regra de ouro nem o banner.
- [ ] `python -m py_compile janelas_barra.py` + `python teste_offline.py`
  → tudo OK. Smoke test sem rede não é possível para o loop completo; o
  orquestrador corre `python janelas_barra.py --porto lisboa --porto
  rotterdam --sem-ais` como verificação real.

---

## Verificação final (orquestrador)

1. `python teste_offline.py` — tudo verde.
2. `python janelas_barra.py --porto lisboa --porto rotterdam --sem-ais` —
   inspeção do HTML gerado (inglês, banner, secções condicionais).
3. Corrida completa `python janelas_barra.py --sem-ais` (~48 portos).
4. Revisão do diff, commits (mensagens em PT), push, CI verde.
