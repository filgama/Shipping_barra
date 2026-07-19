# Port Approach Windows — Europa

Painel informal de janelas de aproximação/manobra para ~50 portos europeus
(site em inglês). Cruza a previsão de swell, vento e nível do mar
(Open-Meteo, por porto) com regras editáveis em `regras.toml` e classifica
cada hora como verde / âmbar / vermelho. Com a chave `AISSTREAM_KEY`
configurada, TODOS os portos mostram uma secção "Live movements
(AIS-derived)" — navios a entrar/sair/em porto ou fundeados, classificados
por rumo AIS em direto (snapshot, não um horário agendado; a caixa de
recolha é derivada automaticamente da coordenada de aproximação quando o
porto não tem `ais_bbox` explícito no catálogo). Lisboa, o porto original
do projeto, tem ainda chegadas/partidas/em-porto autoritativas da APL e o
snapshot AIS legado ("Live AIS snapshot").

> ⚠ **Ferramenta informativa.** Em nenhum porto substitui a autoridade
> portuária, o VTS, a pilotagem, as tabelas de maré oficiais nem os
> regulamentos locais. Todos os limiares são genéricos (PLACEHOLDER),
> não validados para porto nenhum.

## Correr no PC

Basta Python 3.11+ — sem dependências externas:

```bash
python janelas_barra.py                          # todos os portos
python janelas_barra.py --porto lisboa           # só um (teste rápido)
```

Gera `index.html` (landing com todos os portos) e `ports/<slug>.html`
(página de detalhe por porto). Opções: `--sem-apl`, `--sem-ais`,
`--horas 96`.

### Ativar o AIS (movimentos em direto, todos os portos)

A variável de ambiente `AISSTREAM_KEY` (chave grátis, registo em
[aisstream.io](https://aisstream.io)) ativa a recolha AIS em produção —
sem ela, o site continua a funcionar na mesma (meteo-mar + regras + APL de
Lisboa), mas as secções de movimentos AIS mostram "AIS inactive".

**Local**: definir a variável de ambiente antes de correr o script.

```bash
# bash
export AISSTREAM_KEY="a-tua-chave"
python janelas_barra.py
```

```powershell
# PowerShell
$env:AISSTREAM_KEY = "a-tua-chave"
python janelas_barra.py
```

**GitHub Actions**: o workflow (`.github/workflows/atualizar.yml`) já está
ligado a `secrets.AISSTREAM_KEY` — só falta criar o secret no repositório
(ver secção seguinte).

## Publicar para o telemóvel (GitHub Pages, grátis)

1. Criar um repositório no GitHub e enviar esta pasta completa.
2. No repositório: **Settings → Pages → Source: GitHub Actions**; em
   **Settings → Secrets → Actions**, criar `AISSTREAM_KEY` (opcional, ativa
   os movimentos AIS em direto em todos os portos — sem ela o site publica
   na mesma, só sem essas secções).
3. Separador **Actions** → workflow "Atualizar Port Approach Windows" →
   **Run workflow** (primeira execução manual).
4. O site fica em `https://<utilizador>.github.io/<repositório>/` e
   atualiza-se sozinho a cada 30 minutos. No Android/iPhone: abrir o link →
   menu do browser → **Adicionar ao ecrã principal**.

Na landing, usa o campo "Filter ports…" para encontrar um porto; em cada
porto, toca numa hora da timeline para veres os motivos e valores.

## Acrescentar ou afinar portos

Tudo em `portos.toml` — acrescentar um porto é acrescentar uma entrada
`[[porto]]` com slug, nome, país, bandeira e a coordenada de aproximação.
Campos opcionais: `profundidade_zh` (ativa o UKC), `ais_bbox` (caixa AIS
afinada à mão; quando ausente, é derivada automaticamente da coordenada de
aproximação — todos os portos têm movimentos AIS, com ou sem este campo),
`apl = true` (só faz sentido para Lisboa).

## Afinar as regras

Tudo em `regras.toml` — cada limiar tem um campo `fonte`. Os valores
PLACEHOLDER aparecem a magenta no site até serem validados por quem
conhece cada porto. Editar o número **e** a fonte. Nota: os campos
`descricao` estão em inglês porque aparecem tal-e-qual na UI.

## Documentação técnica

Ver `CLAUDE.md` (arquitetura, convenções, dívidas conhecidas e roadmap) e
`docs/2026-07-19-expansao-europa-design.md` (design da expansão Europa).
