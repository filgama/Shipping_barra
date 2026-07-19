# Movimentos AIS para todos os portos — design

Data: 2026-07-19
Estado: aprovado para implementação (orquestração Fable → implementação Sonnet)

## Problema

Hoje só **Lisboa** mostra chegadas e partidas de navios, porque a única
fonte de escalas (ETA/ETD) é a **API da APL**, específica do Porto de
Lisboa. O objetivo do utilizador é ter **entradas e saídas em todos os
portos** do catálogo (~50).

## Restrição incontornável

**Não existe uma API pública universal de ETA/ETD para portos europeus.**
Cada autoridade portuária tem (ou não) o seu próprio portal, sem formato
comum; comerciais como o MarineTraffic são pagos. Isto já estava assumido
no `CLAUDE.md` (Roadmap #7). Logo, "escalas agendadas para todos os portos"
não é alcançável com as fontes gratuitas/stdlib do projeto.

## Decisão

Usar **AIS em direto (aisstream.io)** — já integrado para Lisboa — como
fonte **universal** de movimentos. A partir de cada `PositionReport`
(posição, SOG, COG) + `ShipStaticData` (nome, IMO, destino, calado,
dimensões), classificar cada navio perto de um porto como:

- **A entrar (arriving)** — a navegar em direção ao porto;
- **A sair (departing)** — a navegar a afastar-se do porto;
- **Em porto / fundeado (in port)** — praticamente parado junto ao porto;
- **Indeterminado (manoeuvring)** — em movimento mas sem direção clara.

Isto dá "entradas e saídas de todos os portos" na leitura honesta que o
projeto permite: um **snapshot** de movimentos em direto, **não** um
horário agendado. Lisboa mantém, por cima, o ETA/ETD autoritativo da APL
(secções "Arrivals/Departures (APL)" e "In port now").

Encaixe no projeto: universal, gratuito, só stdlib, degrada com aviso
(nunca crash), e o banner obrigatório já avisa que não é ferramenta
operacional. Coerente com a "regra de ouro".

## Arquitetura

### 1. Uma ligação AIS para todos os portos (não uma por porto)

O campo `BoundingBoxes` do aisstream **já aceita uma lista de caixas**.
Fazemos **uma** subscrição com as caixas de TODOS os portos gerados nesta
corrida, escutamos ~60–90 s, e depois repartimos as mensagens por porto
(teste ponto-em-caixa). Isto é obrigatório: 50 ligações de 60 s
sequenciais não cabem no ciclo de 30 min do CI; uma só janela cabe.

Nova função: `recolher_ais_global(chave, portos, segundos) -> dict`
devolve `{slug: {"navios": [...], "erro": None, "quando": dt,
"segundos": n}}`. Falha global (rede/handshake/sem chave) → cada porto
recebe o mesmo `erro`, o painel degrada. `recolher_ais` (single-porto)
pode ser mantida como wrapper fino ou reaproveitada internamente.

### 2. Caixa por porto derivada da coordenada de aproximação

Só Lisboa tem `ais_bbox` à mão (estuário do Tejo). Para os restantes,
`carregar_portos` **deriva** uma caixa quadrada de ±`MARGEM_BBOX_GRAUS`
em torno de (`latitude`, `longitude`) quando `ais_bbox` está ausente.
`MARGEM_BBOX_GRAUS` é geometria de recolha (como as próprias coordenadas
de aproximação, já assumidas aproximadas ~±0,1°), **não** um limiar de
decisão — fica como constante documentada no código. Um `ais_bbox`
explícito no catálogo tem precedência (Lisboa fica com a caixa afinada).

### 3. Classificação de movimento (função pura, testável)

`classificar_movimento(navio, porto, regras) -> str` em
{"entrada", "saida", "em_porto", "indeterminado"}:

- rumo do navio para o porto = `bearing(navio → porto)`;
- **em_porto**: SOG < `sog_parado_kn`;
- **entrada**: SOG ≥ `sog_a_navegar_kn` E COG a ±`cog_tolerancia_graus`
  do bearing-para-o-porto;
- **saida**: SOG ≥ `sog_a_navegar_kn` E COG a ±`cog_tolerancia_graus` do
  bearing oposto (a afastar-se);
- caso contrário: **indeterminado**.

Opcional: só considerar navios a menos de `raio_movimento_mn` do porto
(usa `distancia_mn` já calculada em `_agregar_ais`).

### 4. Limiares em regras.toml (regra de ouro)

Nova secção `[ais]`, todos `fonte = "PLACEHOLDER"`:

```toml
[ais]
sog_parado_kn = 0.5        # abaixo disto: parado/fundeado/atracado
sog_a_navegar_kn = 3.0     # acima disto: a navegar (entrada/saída)
cog_tolerancia_graus = 90  # meia-abertura do cone COG vs bearing ao porto
raio_movimento_mn = 20     # só classifica navios a menos disto do porto
fonte = "PLACEHOLDER — heurística de snapshot AIS, validar com piloto/prática"
```

### 5. HTML por porto

Nova secção **"Live movements (AIS-derived)"** em TODOS os portos com
caixa AIS (i.e. todos), com três grupos: Arriving / Departing / In port,
cada navio com nome (link MarineTraffic), distância, SOG+seta de rumo,
destino/dimensões/calado quando disponíveis. Reutilizar o estilo dos
cartões AIS existentes. Cabeçalho diz que é snapshot de ~N s e que a
direção é inferida do rumo instantâneo (aviso de incerteza).

Lisboa: **mantém** as secções APL (ETA/ETD + In port now) e a atual
"Live AIS snapshot"; a nova secção de movimentos classificados também
aparece (é a mesma fonte AIS, agora organizada por direção).

## O que NÃO muda

- Motor de regras verde/âmbar/vermelho, UKC, estofa, meteo-mar.
- APL/AIS de Lisboa como estão (a AIS de Lisboa passa a vir da recolha
  global, mesmo resultado).
- Banner obrigatório, UI em inglês, código/comentários em PT-PT.

## Dívidas assumidas (a registar no CLAUDE.md)

- Direção (entrada/saída) inferida de um rumo **instantâneo** — um navio a
  manobrar ou a fundear pode ser mal classificado; é snapshot, não
  tracking.
- Caixas derivadas por margem fixa podem apanhar portos vizinhos ou falhar
  bacias — aproximação, a refinar (mesma dívida das coordenadas).
- Volume AIS de ~50 caixas numa janela fixa é best-effort: se o tráfego
  for alto, o snapshot fica parcial (aceitável, é o que a janela apanhou).
- Limiares `[ais]` são PLACEHOLDER globais, por validar.

## Critérios de aceitação

1. `python teste_offline.py` passa (com novos testes).
2. `python -m py_compile janelas_barra.py` sem erros.
3. Uma página de porto sem APL (ex. Rotterdam) mostra a secção de
   movimentos AIS quando há `ais` com navios; degrada com aviso sem chave.
4. Lisboa continua a mostrar APL (ETA/ETD + In port) além dos movimentos.
5. Nenhum número de decisão novo no `.py` — tudo em `[ais]` de regras.toml.
