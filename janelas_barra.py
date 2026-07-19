#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANELAS DA BARRA — Porto de Lisboa
==================================
Cruza três fontes e gera um painel mobile-first (index.html):

  1. APL (portodelisboa.pt) ........ chegadas (ETA) e partidas (ETD) via a
                                     API JSON pública do portal (Liferay
                                     /api/jsonws/invoke) — sem browser
  2. Open-Meteo Marine + Forecast .. swell, mar total, período, direção,
                                     nível do mar (maré modelada) e vento —
                                     grátis, sem chave
  3. regras.toml ................... motor de regras com limiares editáveis,
                                     cada um com fonte identificada

Estados por hora: verde / âmbar / vermelho + motivos. Navios da lista APL
são posicionados na timeline pela ETA/ETD e recebem avaliação de UKC se o
calado for detetável.

USO:
    python janelas_barra.py                # recolha completa -> index.html
    python janelas_barra.py --sem-apl      # só meteo-mar (teste rápido)
    python janelas_barra.py --horas 96     # horizonte da previsão (defeito 72)

Ver CLAUDE.md para arquitetura e convenções. AVISO: ferramenta informativa;
não substitui JUP, VTS, Capitania nem o juízo do piloto.
"""

import argparse
import html
import json
import re
import sys
import tomllib
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).parent
SAIDA = RAIZ / "index.html"

# API JSON do portal APL (Liferay). Serviços descobertos no JS público das
# páginas "Previsão de chegadas/partidas"; datas em YYYY-MM-DD.
API_APL = "https://www.portodelisboa.pt/api/jsonws/invoke"
SERVICOS_APL = {
    "chegadas": ("Previsão de Chegadas (ETA)",
                 "/apl.processosweb/get-chegadas", True),
    "partidas": ("Previsão de Partidas (ETD)",
                 "/apl.processosweb/get-partidas", True),
    "em_porto": ("Navios em Porto",
                 "/apl.processoswebemporto/get-navios-em-porto", False),
}

ESTADOS = {"verde": 0, "ambar": 1, "vermelho": 2}
ESTADO_NOME = {0: "verde", 1: "ambar", 2: "vermelho"}
# Semântica GO/NO-GO (doc de análise, secção 8) para os textos de detalhe;
# as cores/estados internos 0/1/2 e os nomes verde/ambar/vermelho mantêm-se.
ESTADO_ROTULO = {0: "GO", 1: "GO condicional", 2: "NO-GO"}


# ---------------------------------------------------------------------------
# Regras
# ---------------------------------------------------------------------------
def carregar_regras() -> dict:
    with open(RAIZ / "regras.toml", "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# Meteo-mar (Open-Meteo — sem chave)
# ---------------------------------------------------------------------------
def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "janelas-barra"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def recolher_meteomar(regras: dict, horas: int) -> list[dict]:
    """Lista de dicts por hora: tempo, onda_altura, swell_*, nivel_mar,
    vento_kn, rajada_kn, vento_dir, corrente_kn, corrente_dir,
    visibilidade_m, e_dia."""
    lat = regras["local"]["latitude"]
    lon = regras["local"]["longitude"]
    dias = max(2, min(7, (horas // 24) + 1))

    marine = _get_json(
        "https://marine-api.open-meteo.com/v1/marine"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=wave_height,wave_direction,wave_period,"
        "swell_wave_height,swell_wave_direction,swell_wave_period,"
        "sea_level_height_msl,ocean_current_velocity,ocean_current_direction"
        f"&timezone=Europe%2FLisbon&forecast_days={dias}"
    )
    vento = _get_json(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=wind_speed_10m,wind_gusts_10m,wind_direction_10m,"
        "visibility,is_day"
        "&wind_speed_unit=kn"
        f"&timezone=Europe%2FLisbon&forecast_days={dias}"
    )

    hm, hv = marine["hourly"], vento["hourly"]
    linhas = []
    for i, t in enumerate(hm["time"][:horas]):
        def g(bloco, chave):
            try:
                return bloco[chave][i]
            except (KeyError, IndexError):
                return None
        corrente_kmh = g(hm, "ocean_current_velocity")
        linhas.append({
            "tempo": t,
            "onda_altura": g(hm, "wave_height"),
            "onda_dir": g(hm, "wave_direction"),
            "onda_periodo": g(hm, "wave_period"),
            "swell_altura": g(hm, "swell_wave_height"),
            "swell_dir": g(hm, "swell_wave_direction"),
            "swell_periodo": g(hm, "swell_wave_period"),
            "nivel_mar": g(hm, "sea_level_height_msl"),
            "corrente_kn": (round(corrente_kmh * 0.539957, 1)
                            if corrente_kmh is not None else None),
            "corrente_dir": g(hm, "ocean_current_direction"),
            "vento_kn": g(hv, "wind_speed_10m"),
            "rajada_kn": g(hv, "wind_gusts_10m"),
            "vento_dir": g(hv, "wind_direction_10m"),
            "visibilidade_m": g(hv, "visibility"),
            "e_dia": g(hv, "is_day"),
        })
    return linhas


# ---------------------------------------------------------------------------
# Motor de regras
# ---------------------------------------------------------------------------
def avaliar_hora(hora: dict, regras: dict) -> tuple[int, list[str]]:
    """Devolve (estado 0/1/2, motivos) para uma hora de previsão."""
    estado, motivos = 0, []
    dir_por_parametro = {"swell_altura": "swell_dir", "onda_altura": "onda_dir",
                         "vento_kn": "vento_dir", "rajada_kn": "vento_dir"}
    for r in regras.get("regra", []):
        val = hora.get(r["parametro"])
        if val is None:
            continue
        # setor direcional opcional (suporta sectores que cruzam o Norte,
        # ex.: dir_min=300, dir_max=60)
        if "dir_min" in r:
            dchave = dir_por_parametro.get(r["parametro"])
            d = hora.get(dchave) if dchave else None
            if d is None:
                continue
            if r["dir_min"] <= r["dir_max"]:
                dentro = r["dir_min"] <= d <= r["dir_max"]
            else:
                dentro = d >= r["dir_min"] or d <= r["dir_max"]
            if not dentro:
                continue
        # sentido "abaixo": o valor é mau quando está ABAIXO do limiar
        # (ex.: visibilidade). Por defeito ("acima"), mau é quando ≥ limiar.
        if r.get("sentido") == "abaixo":
            if val <= r["vermelho"]:
                estado = max(estado, 2)
                motivos.append(f"{r['descricao']}: {val:g} ≤ {r['vermelho']:g}")
            elif val <= r["ambar"]:
                estado = max(estado, 1)
                motivos.append(f"{r['descricao']}: {val:g} ≤ {r['ambar']:g}")
        else:
            if val >= r["vermelho"]:
                estado = max(estado, 2)
                motivos.append(f"{r['descricao']}: {val:g} ≥ {r['vermelho']:g}")
            elif val >= r["ambar"]:
                estado = max(estado, 1)
                motivos.append(f"{r['descricao']}: {val:g} ≥ {r['ambar']:g}")
    return estado, motivos


def avaliar_ukc(calado: float, nivel_mar, regras: dict, onda_altura=None):
    """UKC estático simplificado. nivel_mar da Open-Meteo é relativo ao MSL;
    usamos profundidade ZH + nível como aproximação de altura de água.
    Se `onda_altura` (Hs) for fornecida, subtrai à folga uma margem de
    ondulação (fração empírica configurável em regras.toml, aproximação tipo
    PIANC de resposta vertical do navio à ondulação). Devolve (estado, texto)
    ou None se faltar informação."""
    if calado is None or nivel_mar is None:
        return None
    prof = regras["canal"]["profundidade_zh"]
    altura_agua = prof + nivel_mar
    folga = altura_agua - calado
    if calado <= 0:
        return None
    u = regras["ukc"]
    folga_efetiva = folga
    margem_txt = ""
    if onda_altura is not None:
        frac = u.get("margem_ondulacao_frac")
        if frac:
            margem = frac * onda_altura
            folga_efetiva = folga - margem
            margem_txt = f" (−{margem:.1f} m ondulação)"
    pct = folga_efetiva / calado
    txt = (f"água ≈{altura_agua:.1f} m, folga {folga_efetiva:.1f} m"
           f"{margem_txt} ({pct:.0%} do calado)")
    if pct < u["folga_minima_pct"]:
        return 2, "UKC insuficiente: " + txt
    if pct < u["folga_ambar_pct"]:
        return 1, "UKC marginal: " + txt
    return 0, "UKC ok: " + txt


def avaliar_navio_tipo(navio: dict, hora: dict, regras: dict) -> list[tuple[int, str]]:
    """Regras específicas por tipo de navio (ex.: RO-RO vs vento), definidas
    em regras.toml como `[[regra_navio]]`. Para vento, considera também a
    rajada quando disponível e usa o pior dos dois. Devolve lista de
    (estado, motivo)."""
    tipo = (navio.get("tipo") or "").lower()
    resultados = []
    for r in regras.get("regra_navio", []):
        tipos = [t.lower() for t in r.get("tipos", [])]
        if not any(t in tipo for t in tipos):
            continue
        val = hora.get(r["parametro"])
        raj = hora.get("rajada_kn") if r["parametro"] == "vento_kn" else None
        candidatos = [v for v in (val, raj) if v is not None]
        if not candidatos:
            continue
        pior = max(candidatos)
        vermelho, ambar = r.get("vermelho"), r.get("ambar")
        if vermelho is not None and pior >= vermelho:
            resultados.append((2, f"{r['descricao']}: {pior:g} ≥ {vermelho:g}"))
        elif ambar is not None and pior >= ambar:
            resultados.append((1, f"{r['descricao']}: {pior:g} ≥ {ambar:g}"))
    return resultados


def detetar_estofas(previsao: list[dict], regras: dict) -> list[dict]:
    """Deteta preia-mares/baixa-mares (máximos/mínimos locais) na curva de
    nivel_mar — mesma lógica de deteção usada em gerar_svg_mare. Devolve
    lista de {"indice", "tipo": "PM"/"BM", "tempo"}. `regras` é aceite para
    consistência de assinatura (janela_min de [estofa] é usada pelos
    chamadores, não aqui). NOTA: a estofa da CORRENTE não coincide
    necessariamente com a PM/BM do nível modelado (ver [estofa] em
    regras.toml) — desfasamento local não calibrado."""
    valores = [h.get("nivel_mar") for h in previsao]
    pares = [(i, v) for i, v in enumerate(valores) if v is not None]
    estofas = []
    for k in range(1, len(pares) - 1):
        i, v = pares[k]
        antes, depois = pares[k - 1][1], pares[k + 1][1]
        pm = v >= antes and v > depois
        bm = v <= antes and v < depois
        if pm or bm:
            estofas.append({"indice": i, "tipo": "PM" if pm else "BM",
                            "tempo": previsao[i]["tempo"]})
    return estofas


def avaliar_navio(n: dict, previsao: list[dict], avaliacoes: list[tuple],
                   regras: dict, estofas: list[dict]):
    """Avalia um navio cruzando a hora da ETA/ETD com a previsão/regras
    (UKC + regras por tipo) e a proximidade a uma estofa. Partilhada pelos
    cartões e pelos marcadores da timeline — para não duplicar a lógica.
    Devolve (estado, motivos, nota_estofa, idx_na_previsao); estado é None
    se não houver hora reconhecida ou esta cair fora do horizonte."""
    if n["momento"] is None:
        return None, ["sem data reconhecida na tabela APL"], None, None
    alvo = n["momento"].strftime("%Y-%m-%dT%H:00")
    idx = next((i for i, h in enumerate(previsao) if h["tempo"] == alvo), None)
    if idx is None:
        return None, ["fora do horizonte da previsão"], None, None
    estado_n, motivos_n = avaliacoes[idx]
    motivos_n = list(motivos_n) or ["condições dentro dos limiares"]
    ukc = avaliar_ukc(n["calado"], previsao[idx]["nivel_mar"], regras,
                      previsao[idx].get("onda_altura"))
    if ukc:
        estado_n = max(estado_n, ukc[0])
        motivos_n.append(ukc[1])
    elif n["calado"] is None:
        motivos_n.append("calado não detetado — UKC não avaliado")
    for est_nav, motivo_nav in avaliar_navio_tipo(n, previsao[idx], regras):
        estado_n = max(estado_n, est_nav)
        motivos_n.append(motivo_nav)
    nota_estofa = None
    if estofas:
        janela_estofa = regras.get("estofa", {}).get("janela_min")
        prox = min(estofas, key=lambda es: abs(es["indice"] - idx))
        delta_min = abs(prox["indice"] - idx) * 60
        hh_estofa = prox["tempo"][11:13]
        if janela_estofa and delta_min <= janela_estofa:
            nota_estofa = (f"ETA a {delta_min:g} min da estofa "
                           f"({prox['tipo']} {hh_estofa}h)")
        else:
            nota_estofa = (f"ETA fora de janela de estofa "
                           f"({prox['tipo']} {hh_estofa}h)")
    return estado_n, motivos_n, nota_estofa, idx


# Duração mínima de uma sequência de horas GO para ser destacada no resumo
# textual do topo da timeline — é um parâmetro de APRESENTAÇÃO (evita
# anunciar "janelas" de 1h que não servem de nada na prática), não um
# limiar de decisão náutica; não vive em regras.toml por isso mesmo.
JANELA_MIN_HORAS = 3

DIAS_SEMANA_ABREV = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _fmt_dia_hora(tempo_iso: str) -> str:
    dt = datetime.strptime(tempo_iso, "%Y-%m-%dT%H:%M")
    return f"{DIAS_SEMANA_ABREV[dt.weekday()]} {dt.strftime('%H')}h"


def resumo_janelas(previsao: list[dict], avaliacoes: list[tuple],
                    agora: datetime | None = None) -> list[str]:
    """Frases de resumo calculadas a partir de 'agora': a próxima sequência
    contínua de horas verdes (GO) com duração >= JANELA_MIN_HORAS, e a
    próxima hora vermelha (NO-GO). Devolve 0-2 frases."""
    agora = agora or datetime.now()
    agora_iso = agora.strftime("%Y-%m-%dT%H:00")
    inicio = next((i for i, h in enumerate(previsao) if h["tempo"] >= agora_iso), 0)
    n = len(previsao)
    frases = []
    i = inicio
    while i < n:
        if avaliacoes[i][0] != 0:
            i += 1
            continue
        j = i
        while j < n and avaliacoes[j][0] == 0:
            j += 1
        if j - i >= JANELA_MIN_HORAS:
            frases.append(
                f"Próxima janela GO contínua: {_fmt_dia_hora(previsao[i]['tempo'])}"
                f"–{previsao[j - 1]['tempo'][11:13]}h ({j - i} h)")
            break
        i = j
    prox_no_go = next((h for h, a in zip(previsao[inicio:], avaliacoes[inicio:])
                       if a[0] == 2), None)
    if prox_no_go:
        frases.append(f"Próximo NO-GO: {_fmt_dia_hora(prox_no_go['tempo'])}")
    return frases


SETORES = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def cardeal_seta(graus) -> tuple[str, str]:
    """Direção meteorológica (proveniência) → (ponto cardeal, seta do rumo).
    Convenção náutica: 'swell de NW' — o nome diz de onde vem; a seta
    aponta para onde o fluxo segue (proveniência + 180°)."""
    if graus is None:
        return "", ""
    g = float(graus) % 360
    nome = SETORES[int((g + 11.25) // 22.5) % 16]
    rumo = (g + 180) % 360
    seta = "↑↗→↘↓↙←↖"[int(((rumo + 22.5) % 360) // 45)]
    return nome, seta


# ---------------------------------------------------------------------------
# APL (API JSON) + extração de navios
# ---------------------------------------------------------------------------
def recolher_apl(horas: int) -> dict:
    """Consulta a API JSON pública da APL para o horizonte pedido.
    Devolve {chave: {"titulo": ..., "registos": [dict, ...]}}, mais uma
    chave "_erros" (lista de strings) se alguma consulta falhar — chave
    à parte para não confundir extrair_navios/filtrar_em_porto, que só
    olham para os serviços conhecidos."""
    from datetime import timedelta
    hoje = datetime.now().date()
    fim = hoje + timedelta(days=(horas // 24) + 1)
    params = {"dataIni": hoje.isoformat(), "dataFim": fim.isoformat()}
    out = {}
    for chave, (titulo, servico, com_datas) in SERVICOS_APL.items():
        print(f"[APL] {titulo} … ", end="", flush=True)
        try:
            corpo = json.dumps({servico: params if com_datas else {}}).encode()
            req = urllib.request.Request(
                API_APL, data=corpo,
                headers={"User-Agent": "janelas-barra",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                registos = json.loads(r.read().decode())
            if isinstance(registos, list):
                out[chave] = {"titulo": titulo, "registos": registos}
                print(f"{len(registos)} registos")
            else:
                print(f"resposta inesperada: {str(registos)[:80]}")
                out.setdefault("_erros", []).append(f"{titulo}: resposta inesperada")
        except Exception as exc:
            print(f"erro: {exc}")
            out.setdefault("_erros", []).append(f"{titulo}: {exc}")
    return out


RE_DATA_APL = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})")


def _momento(texto) -> datetime | None:
    """'2026-07-21 10:00:00.0' -> datetime, tolerante a variações."""
    m = RE_DATA_APL.search(str(texto or ""))
    if not m:
        return None
    try:
        return datetime(*map(int, m.groups()))
    except ValueError:
        return None


def _imo(reg: dict) -> str | None:
    """Número IMO do registo APL, validado (7 dígitos + dígito de controlo:
    soma dos 6 primeiros × pesos 7..2, mod 10). A APL às vezes devolve ids
    internos neste campo; o checksum filtra-os."""
    imo = str(reg.get("imo") or reg.get("nv_imo") or "").strip()
    if not (imo.isdigit() and len(imo) == 7):
        return None
    controlo = sum(int(d) * p for d, p in zip(imo[:6], range(7, 1, -1))) % 10
    return imo if controlo == int(imo[6]) else None


def link_marinetraffic(nome: str, imo: str | None) -> str:
    """URL MarineTraffic do navio: ficha por IMO se conhecido,
    senão pesquisa pelo nome."""
    if imo:
        return f"https://www.marinetraffic.com/pt/ais/details/ships/imo:{imo}"
    return ("https://www.marinetraffic.com/pt/ais/index/search/all?keyword="
            + urllib.parse.quote(nome))


def extrair_navios(apl: dict) -> list[dict]:
    """Converte os registos JSON da APL em navios com nome, momento (ETA/ETD),
    sentido, calado e tipo. Ignora escalas já concretizadas (ATA/ATD).
    Deduplica por (nome, momento), como faz o próprio portal."""
    navios, vistos = [], set()
    por_sentido = (("chegadas", "entrada", "eta", "ata", "caladoMaxEntrada"),
                   ("partidas", "saída", "etd", "atd", "caladoMaxSaida"))
    for chave, sentido, c_prev, c_real, c_calado in por_sentido:
        bloco = apl.get(chave)
        if not bloco:
            continue
        for reg in bloco["registos"]:
            if str(reg.get(c_real) or "").strip():
                continue  # já entrou/saiu — não é previsão
            nome = (reg.get("navio") or reg.get("nv_nome") or "?").strip()
            momento = _momento(reg.get(c_prev))
            marca = (nome, sentido, momento)
            if marca in vistos:
                continue
            vistos.add(marca)
            calado = reg.get(c_calado) or reg.get("nv_caladoMax")
            try:
                calado = float(calado) if calado else None
            except (TypeError, ValueError):
                calado = None
            navios.append({"nome": nome, "sentido": sentido,
                           "momento": momento, "calado": calado,
                           "tipo": (reg.get("nv_tipoNavio") or "").strip(),
                           "zona": (reg.get("zona") or "").strip(),
                           "imo": _imo(reg)})
    return navios


# Filtro técnico (não é limiar de decisão náutica): o serviço "em porto"
# devolve escalas históricas antigas; só mostramos ATAs recentes.
JANELA_PORTO_DIAS = 30


def filtrar_em_porto(registos, agora=None) -> list[dict]:
    """Navios atracados: ATA preenchida, ATD vazia, ATA recente.
    Deduplica por nome; ordena da chegada mais recente para a mais antiga."""
    agora = agora or datetime.now()
    out, vistos = [], set()
    for reg in registos:
        ata = _momento(reg.get("ata"))
        if ata is None or str(reg.get("atd") or "").strip():
            continue
        if (agora - ata).days > JANELA_PORTO_DIAS:
            continue
        nome = (reg.get("navio") or reg.get("nv_nome") or "?").strip()
        if nome in vistos:
            continue
        vistos.add(nome)
        out.append({"nome": nome, "ata": ata,
                    "etd": _momento(reg.get("etd")),
                    "tipo": (reg.get("nv_tipoNavio") or "").strip(),
                    "zona": (reg.get("zona") or "").strip(),
                    "imo": _imo(reg)})
    out.sort(key=lambda n: n["ata"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Painel HTML (mobile-first)
# ---------------------------------------------------------------------------
def gerar_svg_serie(previsao, campo, classe, altura=56, passo=24,
                    marcar_extremos=False, linha_zero=False,
                    extra_campo=None) -> str:
    """Sparkline genérica alinhada à timeline (um `passo` px por hora, mesmo
    grid das células). `campo`: chave numérica em cada hora de `previsao`.
    `extra_campo`: 2ª série opcional desenhada tracejada na mesma escala
    (ex.: rajada sobreposta ao vento médio). `marcar_extremos`: anota
    máximos/mínimos locais com hora+valor (usado pela maré). `linha_zero`:
    desenha uma linha de referência no valor 0. Devolve "" se faltarem
    dados. Generaliza a antiga gerar_svg_mare (ver wrapper abaixo)."""
    valores = [h.get(campo) for h in previsao]
    pares = [(i, v) for i, v in enumerate(valores) if v is not None]
    if len(pares) < 3:
        return ""
    extra_pares = ([(i, h.get(extra_campo)) for i, h in enumerate(previsao)
                    if h.get(extra_campo) is not None] if extra_campo else [])
    todos = [v for _, v in pares] + [v for _, v in extra_pares]
    vmin, vmax = min(todos), max(todos)
    amp = (vmax - vmin) or 1.0
    m_topo, m_base = 14, 8
    util = altura - m_topo - m_base

    def xy(i, v):
        return i * passo + passo / 2, m_topo + (vmax - v) / amp * util

    def polilinha(lista, cls):
        pontos = " ".join(f"{x:.0f},{y:.1f}"
                          for x, y in (xy(i, v) for i, v in lista))
        return f"<polyline points='{pontos}' class='{cls}'/>"

    marcas = []
    if marcar_extremos:
        for k in range(1, len(pares) - 1):
            i, v = pares[k]
            antes, depois = pares[k - 1][1], pares[k + 1][1]
            pm = v >= antes and v > depois
            bm = v <= antes and v < depois
            if not (pm or bm):
                continue
            x, y = xy(i, v)
            dy = -4 if pm else 12
            marcas.append(f"<text x='{x:.0f}' y='{y + dy:.1f}' "
                          f"text-anchor='middle' class='{classe}-rot'>"
                          f"{previsao[i]['tempo'][11:13]}h {v:+.1f}</text>")
    largura = len(previsao) * passo
    linha0 = ""
    if linha_zero and vmin <= 0 <= vmax:
        y0 = m_topo + vmax / amp * util
        linha0 = (f"<line x1='0' y1='{y0:.1f}' x2='{largura}' "
                  f"y2='{y0:.1f}' class='{classe}-msl'/>")
    extra_svg = polilinha(extra_pares, f"{classe}-linha2") if extra_pares else ""
    return (f"<svg class='{classe}' width='{largura}' height='{altura}' "
            f"viewBox='0 0 {largura} {altura}'>{linha0}"
            f"{polilinha(pares, classe + '-linha')}{extra_svg}"
            f"{''.join(marcas)}</svg>")


def gerar_svg_mare(previsao, passo=24, alto=56) -> str:
    """Curva do nível do mar (modelo, rel. MSL) alinhada à timeline, com
    PM/BM anotadas — wrapper de compatibilidade sobre gerar_svg_serie
    (output idêntico ao da implementação original)."""
    return gerar_svg_serie(previsao, "nivel_mar", "mare", altura=alto,
                           passo=passo, marcar_extremos=True, linha_zero=True)


COR = {0: "#1E7A5A", 1: "#E2B93B", 2: "#C0392B"}

# Favicon inline (sem ficheiros externos): círculo verde/âmbar simples.
_FAVICON_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
                "<circle cx='16' cy='16' r='14' fill='#1E7A5A'/>"
                "<path d='M16 2a14 14 0 0 1 0 28z' fill='#E2B93B'/>"
                "<circle cx='16' cy='16' r='14' fill='none' stroke='#1B2A38' "
                "stroke-width='2'/></svg>")
FAVICON_HREF = "data:image/svg+xml," + urllib.parse.quote(_FAVICON_SVG)

# JS vanilla do painel (string normal — inserida no f-string via {JS_PAINEL}):
# toque/Enter numa célula (agora <button>) abre o detalhe estruturado;
# marcador de "agora" pela hora do dispositivo (correto mesmo com página em
# cache) + auto-scroll. prefers-reduced-motion é tratado em CSS.
JS_PAINEL = """
<script>
(function () {
  var det = document.getElementById('detalhe');
  var cels = Array.prototype.slice.call(document.querySelectorAll('.cel'));
  function linha(rotulo, valor) {
    return valor ? '<div class="det-linha"><b>' + rotulo + ':</b> ' +
           valor + '</div>' : '';
  }
  function mostrar(c) {
    cels.forEach(function (x) { x.classList.remove('sel'); });
    c.classList.add('sel');
    var t = c.dataset.t;
    var partes = ['<div class="det-cab"><b>' + t.slice(8, 10) + '/' +
                  t.slice(5, 7) + ' ' + t.slice(11, 13) + 'h</b> — ' +
                  c.dataset.rotulo + '</div>'];
    if (c.dataset.motivos) {
      partes.push('<div class="det-mot">' + c.dataset.motivos + '</div>');
    }
    partes.push(linha('Mar', c.dataset.mar));
    partes.push(linha('Nível', c.dataset.nivel));
    partes.push(linha('Vento', c.dataset.vento));
    partes.push(linha('Corrente', c.dataset.corrente));
    partes.push(linha('Visibilidade', c.dataset.vis));
    det.innerHTML = partes.join('');
    det.hidden = false;
  }
  cels.forEach(function (c) {
    c.addEventListener('click', function () { mostrar(c); });
  });
  var ag = new Date();
  function p2(n) { return String(n).padStart(2, '0'); }
  var iso = ag.getFullYear() + '-' + p2(ag.getMonth() + 1) + '-' +
            p2(ag.getDate()) + 'T' + p2(ag.getHours()) + ':00';
  var atual = document.querySelector('.cel[data-t="' + iso + '"]');
  if (atual) {
    atual.classList.add('agora');
    atual.scrollIntoView({ inline: 'center', block: 'nearest' });
    mostrar(atual);
  }

  // marcadores de navios na timeline: toque leva ao cartão e destaca-o
  Array.prototype.slice.call(document.querySelectorAll('.nm-marca'))
    .forEach(function (b) {
      b.addEventListener('click', function () {
        var alvo = document.getElementById(b.dataset.alvo);
        if (!alvo) { return; }
        alvo.scrollIntoView({ behavior: 'smooth', block: 'center' });
        alvo.classList.add('destaque');
        setTimeout(function () { alvo.classList.remove('destaque'); }, 1600);
      });
    });

  // chips de filtro por estado dos navios
  var chipsF = Array.prototype.slice.call(document.querySelectorAll('.chip-filtro'));
  var cartoesN = Array.prototype.slice.call(document.querySelectorAll('.navio[data-estado]'));
  chipsF.forEach(function (b) {
    b.addEventListener('click', function () {
      chipsF.forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
      b.setAttribute('aria-pressed', 'true');
      var f = b.dataset.filtro;
      cartoesN.forEach(function (c) {
        c.classList.toggle('hide', f !== 'todos' && c.dataset.estado !== f);
      });
    });
  });
})();
</script>"""


def gerar_html(previsao, avaliacoes, navios, apl, regras) -> str:
    e = html.escape
    agora = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")

    # --- estofas (PM/BM), calculadas uma vez e partilhadas com a timeline
    # e os cartões de navios ------------------------------------------------
    estofas_globais = detetar_estofas(previsao, regras)
    estofa_por_indice = {es["indice"]: es["tipo"] for es in estofas_globais}
    janela_estofa = regras.get("estofa", {}).get("janela_min")

    # --- resumo do estado atual, para o topo da secção timeline -----------
    agora_dt = datetime.now()
    agora_iso = agora_dt.strftime("%Y-%m-%dT%H:00")
    idx_agora = next((i for i, h in enumerate(previsao)
                      if h["tempo"] == agora_iso), None)
    resumo_agora = ""
    if idx_agora is not None:
        est_a, mot_a = avaliacoes[idx_agora]
        rot_a = ESTADO_ROTULO[est_a]
        detalhe_a = mot_a[0] if mot_a else "condições dentro dos limiares"
        resumo_agora = f"Agora: {rot_a} — {detalhe_a}"
    resumo_janelas_txt = " · ".join(resumo_janelas(previsao, avaliacoes, agora_dt))
    if resumo_janelas_txt:
        resumo_agora = (resumo_agora + " · " + resumo_janelas_txt
                        if resumo_agora else resumo_janelas_txt)

    # --- timeline: um botão por hora ----------------------------------------
    celulas = []
    for i, (hora, (estado, motivos)) in enumerate(zip(previsao, avaliacoes)):
        t = hora["tempo"]  # "2026-07-18T14:00"
        dia, hh = t[8:10], t[11:13]
        mar_txt = ""
        if hora.get("swell_altura") is not None:
            nome, seta = cardeal_seta(hora.get("swell_dir"))
            per = (f" · {hora['swell_periodo']:g} s"
                   if hora.get("swell_periodo") is not None else "")
            mar_txt = f"swell {hora['swell_altura']:g} m {nome}{seta}{per}"
        nivel_txt = (f"{hora['nivel_mar']:+g} m"
                     if hora.get("nivel_mar") is not None else "")
        vento_txt = ""
        if hora.get("vento_kn") is not None:
            nome, seta = cardeal_seta(hora.get("vento_dir"))
            raj = (f" · rajada {hora['rajada_kn']:g} kn"
                   if hora.get("rajada_kn") is not None else "")
            vento_txt = f"{hora['vento_kn']:g} kn {nome}{seta}{raj}"
        corrente_txt = ""
        if hora.get("corrente_kn") is not None:
            nome, seta = cardeal_seta(hora.get("corrente_dir"))
            corrente_txt = f"{hora['corrente_kn']:g} kn {nome}{seta}"
        vis_txt = (f"{hora['visibilidade_m'] / 1000:.1f} km"
                   if hora.get("visibilidade_m") is not None else "")
        mot_txt = "; ".join(motivos)
        if estado == 1 and mot_txt:
            mot_txt = "Condicionantes: " + mot_txt
        rotulo = ESTADO_ROTULO[estado]
        marca_dia = f"<span class='dia'>{dia}</span>" if hh == "00" else ""
        extra_cls = " cel-a" if estado == 1 else ""
        noite_cls = " cel-noite" if hora.get("e_dia") == 0 else ""
        estofa_tipo = estofa_por_indice.get(i)
        estofa_cls = (f" cel-estofa cel-{estofa_tipo.lower()}"
                     if estofa_tipo else "")
        # indicador não-cromático de estado (daltonismo): ▲ vermelho, ~ âmbar
        glifo = ""
        if estado == 2:
            glifo = "<span class='glifo' aria-hidden='true'>▲</span>"
        elif estado == 1:
            glifo = "<span class='glifo' aria-hidden='true'>~</span>"
        marca_estofa = (f"<span class='marca-estofa' aria-hidden='true'>"
                        f"{estofa_tipo}</span>" if estofa_tipo else "")
        aria = f"{dia}/{t[5:7]} {hh}h — {rotulo}"
        if mot_txt:
            aria += ". " + mot_txt
        if estofa_tipo:
            aria += f". {estofa_tipo} (estofa)"
        if hora.get("e_dia") == 0:
            aria += ". Noite"
        celulas.append(
            f"<button type='button' class='cel{extra_cls}{noite_cls}"
            f"{estofa_cls}' style='background:{COR[estado]}' data-t='{t}' "
            f"data-estado='{ESTADO_NOME[estado]}' data-rotulo='{e(rotulo)}' "
            f"data-motivos=\"{e(mot_txt)}\" data-mar=\"{e(mar_txt)}\" "
            f"data-nivel=\"{e(nivel_txt)}\" data-vento=\"{e(vento_txt)}\" "
            f"data-corrente=\"{e(corrente_txt)}\" data-vis=\"{e(vis_txt)}\" "
            f"aria-label=\"{e(aria)}\">"
            f"{marca_dia}{glifo}{marca_estofa}"
            f"<span class='hh'>{hh}</span></button>")

    # --- navios: avaliação partilhada por cartões e marcadores da timeline -
    navios_avaliados = []
    for k, n in enumerate(
            sorted(navios, key=lambda x: (x["momento"] or datetime.max)), start=1):
        estado_n, motivos_n, nota_estofa, idx = avaliar_navio(
            n, previsao, avaliacoes, regras, estofas_globais)
        navios_avaliados.append({**n, "id": f"navio-{k}", "estado_n": estado_n,
                                 "motivos_n": motivos_n,
                                 "nota_estofa": nota_estofa, "idx": idx})

    cartoes = []
    contagens = {"verde": 0, "ambar": 0, "vermelho": 0, "none": 0}
    for nv in navios_avaliados:
        estado_chave = ESTADO_NOME.get(nv["estado_n"], "none")
        contagens[estado_chave] += 1
        cor = COR.get(nv["estado_n"], "#5C6E7C")
        rot_n = ESTADO_ROTULO.get(nv["estado_n"], "sem avaliação")
        quando = (nv["momento"].strftime("%d/%m %H:%M")
                  if nv["momento"] else "—")
        chips = []
        if nv.get("tipo"):
            chips.append(f"<span class='chip'>{e(nv['tipo'])}</span>")
        if nv["calado"]:
            chips.append(f"<span class='chip'>calado {nv['calado']:g} m</span>")
        if nv.get("zona"):
            chips.append(f"<span class='chip'>{e(nv['zona'])}</span>")
        chips_html = (f"<div class='chips'>{''.join(chips)}</div>"
                     if chips else "")
        itens_mot = list(nv["motivos_n"])
        if nv["nota_estofa"]:
            itens_mot.append(nv["nota_estofa"])
        mot_html = (("<ul class='nmot'>" +
                    "".join(f"<li>{e(m)}</li>" for m in itens_mot) +
                    "</ul>") if itens_mot else "")
        cartoes.append(f"""
        <div class="navio" id="{nv['id']}" data-estado="{estado_chave}">
          <span class="farol" style="background:{cor}" aria-hidden="true"></span>
          <div class="navio-corpo">
            <div class="nnome-linha"><a class="nnome"
            href="{e(link_marinetraffic(nv['nome'], nv.get('imo')))}"
            target="_blank" rel="noopener">{e(nv['nome'])}</a>
            <span class="nestado">{e(rot_n)}</span></div>
            <div class="nmeta">{e(nv['sentido'])} · {quando}</div>
            {chips_html}
            {mot_html}
          </div>
        </div>""")
    if not cartoes:
        cartoes = ["<p class='vazio'>Sem navios devolvidos pela API da APL "
                   "nesta recolha (corre com APL ativa ou verifica a API)."]

    # --- chips de filtro por estado (JS liga-os aos data-estado acima) -----
    chips_filtro_html = ""
    if navios_avaliados:
        defs = [("todos", "Todos", len(navios_avaliados)),
                ("verde", "GO", contagens["verde"]),
                ("ambar", "GO condicional", contagens["ambar"]),
                ("vermelho", "NO-GO", contagens["vermelho"]),
                ("none", "Sem avaliação", contagens["none"])]
        partes = []
        for chave, rot, n_c in defs:
            pressed = "true" if chave == "todos" else "false"
            partes.append(f"<button type='button' class='chip-filtro' "
                          f"data-filtro='{chave}' aria-pressed='{pressed}'>"
                          f"{e(rot)} ({n_c})</button>")
        chips_filtro_html = f"<div class='chips-filtro'>{''.join(partes)}</div>"

    # --- marcadores de navios na timeline (▼ chegada / ▲ partida) ----------
    por_indice = {}
    for nv in navios_avaliados:
        if nv["idx"] is not None:
            por_indice.setdefault(nv["idx"], []).append(nv)
    marcadores = []
    for i in range(len(previsao)):
        grupo = por_indice.get(i)
        if not grupo:
            marcadores.append("<span class='nm-slot' aria-hidden='true'></span>")
            continue
        primeiro = grupo[0]
        seta = "▼" if primeiro["sentido"] == "entrada" else "▲"
        cor_m = COR.get(primeiro["estado_n"], "#5C6E7C")
        extra = f"+{len(grupo) - 1}" if len(grupo) > 1 else ""
        nomes = ", ".join(g["nome"] for g in grupo)
        aria_m = f"{nomes} — {previsao[i]['tempo'][11:13]}h"
        marcadores.append(
            f"<button type='button' class='nm-slot nm-marca' "
            f"style='color:{cor_m}' data-alvo='{primeiro['id']}' "
            f"aria-label=\"{e(aria_m)}\">{seta}<sup>{extra}</sup></button>")

    # --- regras em vigor ----------------------------------------------------
    linhas_regras = "".join(
        f"<tr><td>{e(r['descricao'])}</td>"
        f"<td>{'≤' if r.get('sentido') == 'abaixo' else '≥'}</td>"
        f"<td>{r['ambar']:g}</td><td>{r['vermelho']:g}</td>"
        f"<td class='fonte-{'ph' if 'PLACEHOLDER' in r['fonte'] else 'ok'}'>"
        f"{e(r['fonte'])}</td></tr>"
        for r in regras.get("regra", []))
    notas = "".join(f"<li>{e(x)}</li>" for x in
                    regras.get("notas_regulamentares", {}).get("itens", []))

    # --- curva de maré + sparklines de vento/mar, alinhadas à timeline -----
    svg_mare = gerar_svg_mare(previsao)
    legenda_mare = (" · curva: nível modelado (rel. MSL)" if svg_mare else "")
    svg_vento = gerar_svg_serie(previsao, "vento_kn", "vento", altura=34,
                                extra_campo="rajada_kn")
    svg_ondas = gerar_svg_serie(previsao, "onda_altura", "onda", altura=34)
    faixa_vento = (f"<div class='faixa-serie'><span class='faixa-rotulo'>"
                   f"vento kn</span>{svg_vento}</div>" if svg_vento else "")
    faixa_ondas = (f"<div class='faixa-serie'><span class='faixa-rotulo'>"
                   f"mar m</span>{svg_ondas}</div>" if svg_ondas else "")

    # --- tabela de próximas marés (PM/BM, nível modelado) -------------------
    linhas_mares = "".join(
        f"<tr><td>{e(es['tempo'][8:10])}/{e(es['tempo'][5:7])} "
        f"{e(es['tempo'][11:13])}h</td><td>{es['tipo']} "
        f"{previsao[es['indice']]['nivel_mar']:+.1f} m</td></tr>"
        for es in estofas_globais)
    seccao_mares = ""
    if linhas_mares:
        seccao_mares = (
            "<div class='scroll'><table class='mares'><thead><tr>"
            "<th>Quando</th><th>PM/BM</th></tr></thead>"
            f"<tbody>{linhas_mares}</tbody></table></div>"
            "<p class='ressalva-mare'>Nível modelado Open-Meteo, relativo ao "
            "MSL — não é a tabela oficial de marés do Instituto Hidrográfico.</p>")

    # --- aviso de fonte APL em falha (painel parcial, nunca enganador) -----
    erros_apl = apl.get("_erros") or []
    aviso_apl = ""
    if erros_apl:
        hm = agora.split(" ")[-1]
        aviso_apl = (f"<div class='aviso-apl' role='note'>⚠ Dados APL "
                    f"indisponíveis nesta recolha ({e(hm)}): painel parcial "
                    f"({e('; '.join(erros_apl))}).</div>")

    # --- em porto agora ----------------------------------------------------
    em_porto = filtrar_em_porto(
        apl.get("em_porto", {}).get("registos", []))
    linhas_porto = []
    for n in em_porto:
        etd = n["etd"].strftime("%d/%m %H:%M") if n["etd"] else "—"
        chips = [f"<span class='chip'>{e(x)}</span>"
                for x in (n["tipo"], n["zona"]) if x]
        chips_html = f"<div class='chips'>{''.join(chips)}</div>" if chips else ""
        linhas_porto.append(
            f"<div class='navio'><span class='farol' "
            f"style='background:#5C6E7C' aria-hidden='true'></span>"
            f"<div class='navio-corpo'>"
            f"<div class='nnome-linha'><a class='nnome' "
            f"href=\"{e(link_marinetraffic(n['nome'], n.get('imo')))}\" "
            f"target='_blank' rel='noopener'>{e(n['nome'])}"
            f"</a></div>{chips_html}"
            f"<div class='nmeta'>ETD prevista: {etd}</div></div></div>")
    seccao_porto = ("".join(linhas_porto) or
                    "<p class='vazio'>Sem navios em porto nesta recolha.</p>")

    resumo_html = (f"<p id='resumo-agora' class='resumo-agora'>{e(resumo_agora)}</p>"
                  if resumo_agora else "")

    return f"""<!DOCTYPE html>
<html lang="pt"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="900">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#DCEBF1" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0D1720" media="(prefers-color-scheme: dark)">
<meta name="description" content="Painel informativo de janelas de manobra na barra do Porto de Lisboa: cruza APL, Open-Meteo e regras editáveis — não substitui JUP, VTS nem o piloto.">
<meta property="og:title" content="Janelas da Barra · Lisboa">
<meta property="og:description" content="Timeline verde/âmbar/vermelho da barra de Lisboa, maré, vento e navios da APL — informativo, não operacional.">
<link rel="icon" href="{FAVICON_HREF}">
<title>Janelas da Barra · Lisboa</title>
<style>
 :root {{ --tinta:#1B2A38; --agua:#DCEBF1; --papel:#F7F5EF; --mag:#B0257C;
         --verde:#1E7A5A; --ambar:#E2B93B; --vermelho:#C0392B; }}
 * {{ box-sizing:border-box; }}
 html {{ scroll-behavior:smooth; }}
 body {{ margin:0; background:var(--agua); color:var(--tinta);
        font-family:system-ui,-apple-system,sans-serif; line-height:1.4; }}
 header {{ padding:16px 16px 8px; }}
 h1 {{ margin:0; font-size:24px; }}
 .sub {{ font-size:12px; color:#5C6E7C; margin-top:4px; }}
 .aviso {{ background:var(--tinta); color:var(--papel); font-size:12px;
          padding:8px 16px; }}
 main {{ display:block; max-width:720px; margin:0 auto; }}
 section {{ background:var(--papel); border:2px solid var(--tinta);
           border-radius:12px; margin:12px; padding:12px; }}
 h2 {{ font-size:16px; margin:0 0 8px; }}
 .resumo-agora {{ margin:0 0 10px; font-size:14px; font-weight:600;
                 padding:8px 10px; background:var(--agua);
                 border-radius:8px; border:1px solid var(--tinta); }}
 .scroll {{ overflow-x:auto; padding-bottom:6px; }}
 .timeline {{ display:flex; gap:2px; }}
 button.cel {{ border:none; font:inherit; color:#fff; cursor:pointer;
              padding:0; -webkit-tap-highlight-color:transparent; }}
 .cel:focus-visible {{ outline:3px solid var(--tinta); outline-offset:2px;
                       position:relative; z-index:1; }}
 .cel.agora {{ outline:3px solid var(--mag); outline-offset:-1px; }}
 .cel.sel {{ box-shadow:inset 0 0 0 2px var(--tinta); }}
 .cel-a, .cel-a .hh, .cel-a .dia, .cel-a .glifo, .cel-a .marca-estofa {{
   color:#1B2A38; }}
 .cel-noite {{ filter:saturate(.55) brightness(.88); }}
 .cel-noite::before {{ content:''; position:absolute; top:0; left:0;
                       right:0; height:3px; background:rgba(0,0,0,.35); }}
 #detalhe {{ margin-top:8px; padding:8px 10px; border:1.5px dashed var(--tinta);
            border-radius:8px; font-size:13px; line-height:1.5; }}
 #detalhe .det-cab {{ margin-bottom:4px; }}
 #detalhe .det-mot {{ margin-bottom:4px; }}
 #detalhe .det-linha {{ font-size:12px; }}
 .mare, .vento, .onda {{ display:block; }}
 .mare-linha {{ fill:none; stroke:#3B7EA1; stroke-width:2; }}
 .mare-rot {{ font-size:9px; fill:currentColor; }}
 .mare-msl {{ stroke:#5C6E7C; stroke-dasharray:3 3; }}
 .vento-linha {{ fill:none; stroke:#3B7EA1; stroke-width:1.6; }}
 .vento-linha2 {{ fill:none; stroke:#3B7EA1; stroke-width:1.2;
                  stroke-dasharray:3 2; opacity:.7; }}
 .onda-linha {{ fill:none; stroke:#5C6E7C; stroke-width:1.6; }}
 .faixa-serie {{ display:flex; align-items:center; gap:6px; margin-top:2px; }}
 .faixa-rotulo {{ font-size:10px; color:#5C6E7C; min-width:44px;
                  flex:0 0 auto; }}
 .marcadores-navios {{ display:flex; gap:2px; margin-bottom:2px; }}
 .nm-slot {{ min-width:24px; height:15px; font-size:10px; text-align:center;
            line-height:15px; }}
 button.nm-marca {{ border:none; background:none; font:inherit; padding:0;
                    cursor:pointer; -webkit-tap-highlight-color:transparent; }}
 .nm-marca sup {{ font-size:7px; }}
 table.mares {{ min-width:auto; width:auto; }}
 .ressalva-mare {{ font-size:11px; color:#5C6E7C; margin:4px 0 0; }}
 .navio.destaque {{ outline:3px solid var(--mag); outline-offset:2px;
                    border-radius:8px; }}
 .aviso-apl {{ background:var(--ambar); color:#1B2A38; font-size:12px;
              padding:8px 16px; }}
 .chips-filtro {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px; }}
 .chip-filtro {{ font:inherit; font-size:12px; border:1px solid var(--tinta);
                background:var(--papel); color:var(--tinta); border-radius:999px;
                padding:4px 10px; cursor:pointer; }}
 .chip-filtro[aria-pressed="true"] {{ background:var(--tinta); color:var(--papel); }}
 .navio.hide {{ display:none; }}
 .cel {{ min-width:24px; height:54px; border-radius:4px; position:relative; }}
 .cel .hh {{ position:absolute; bottom:2px; left:0; right:0;
            text-align:center; font-size:9px; opacity:.9; }}
 .cel .dia {{ position:absolute; top:2px; left:0; right:0; text-align:center;
             font-size:9px; font-weight:700; }}
 .cel .glifo {{ position:absolute; top:2px; right:3px; font-size:9px; }}
 .cel .marca-estofa {{ position:absolute; bottom:15px; left:0; right:0;
                       text-align:center; font-size:7px; font-weight:700;
                       letter-spacing:.02em; }}
 .legenda {{ font-size:11px; color:#5C6E7C; margin-top:6px; }}
 .legenda-item {{ display:inline-block; margin-right:10px; }}
 .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%;
        margin:0 3px 0 0; vertical-align:-1px; }}
 .navio {{ display:flex; gap:10px; padding:10px 0;
          border-bottom:1px solid #D7DFE4; }}
 .navio:last-child {{ border-bottom:none; }}
 .farol {{ flex:0 0 12px; height:12px; border-radius:50%; margin-top:4px; }}
 .navio-corpo {{ min-width:0; flex:1; }}
 .nnome-linha {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:6px; }}
 .nnome {{ font-weight:600; font-size:15px; }}
 a.nnome {{ color:inherit; text-decoration:underline;
           text-decoration-color:#8FA6B5; text-underline-offset:2px; }}
 a.nnome:hover, a.nnome:focus-visible {{ text-decoration-color:currentColor; }}
 .nestado {{ font-size:11px; font-weight:700; color:#5C6E7C; }}
 .nmeta {{ font-size:12px; color:#5C6E7C; }}
 .chips {{ margin-top:4px; display:flex; flex-wrap:wrap; gap:4px; }}
 .chip {{ font-size:11px; background:var(--agua); border:1px solid #B9C6CF;
         border-radius:999px; padding:1px 8px; white-space:nowrap; }}
 .nmot {{ font-size:12px; margin:4px 0 0; padding-left:16px; }}
 .nmot li {{ margin-bottom:2px; }}
 table {{ border-collapse:collapse; width:100%; font-size:12px;
         min-width:480px; }}
 th,td {{ border:1px solid #B9C6CF; padding:5px 6px; text-align:left; }}
 th {{ background:var(--tinta); color:var(--papel); }}
 .fonte-ph {{ color:var(--mag); font-weight:600; }}
 .fonte-ok {{ color:#1E7A5A; }}
 ul {{ margin:6px 0 0; padding-left:18px; font-size:12px; }}
 .vazio {{ color:#5C6E7C; font-style:italic; font-size:13px; }}
 footer {{ font-size:11px; color:#5C6E7C; padding:0 16px 20px;
          max-width:720px; margin:0 auto; }}
 @media (prefers-color-scheme: dark) {{
  :root {{ --tinta:#E6EDF3; --agua:#0D1720; --papel:#15222D; --mag:#E464AE; }}
  section {{ border-color:#33475A; }}
  th {{ background:#0D1720; }}
  th, td {{ border-color:#33475A; }}
  .navio {{ border-bottom-color:#243442; }}
  .aviso {{ background:#15222D; color:#E6EDF3;
           border-bottom:1px solid #33475A; }}
  .fonte-ok {{ color:#4CC38A; }}
  .chip {{ border-color:#33475A; }}
 }}
 @media (prefers-reduced-motion: reduce) {{
  html {{ scroll-behavior:auto; }}
  * {{ animation-duration:0.01ms !important; animation-iteration-count:1 !important;
      transition-duration:0.01ms !important; scroll-behavior:auto !important; }}
 }}
</style></head>
<body>
<header>
 <h1>Janelas da Barra — Lisboa</h1>
 <div class="sub">Atualizado: {agora} · APL + Open-Meteo Marine ·
 limiares em regras.toml</div>
</header>
<div class="aviso" role="note">⚠ Ferramenta informativa. Não substitui JUP,
VTS-Lisboa, Capitania nem o juízo profissional do piloto. Limiares a magenta
são PLACEHOLDERS por validar.</div>
{aviso_apl}

<main aria-label="Painel de janelas da barra">
<section aria-labelledby="tl-titulo">
 <h2 id="tl-titulo">Próximas {len(celulas)} horas</h2>
 {resumo_html}
 <div class="scroll">
  <div class="marcadores-navios"{'' if por_indice else " aria-hidden='true'"}>{''.join(marcadores)}</div>
  <div class="timeline">{''.join(celulas)}</div>
  {svg_mare}
  {faixa_vento}
  {faixa_ondas}
 </div>
 <div id="detalhe" aria-live="polite" hidden></div>
 <div class="legenda">
  <div>Toca ou navega por teclado numa hora para ver os detalhes.{legenda_mare}</div>
  <div>
   <span class="legenda-item"><span class="dot" style="background:{COR[0]}"></span>GO</span>
   <span class="legenda-item"><span class="dot" style="background:{COR[1]}"></span>GO condicional (~)</span>
   <span class="legenda-item"><span class="dot" style="background:{COR[2]}"></span>NO-GO (▲)</span>
   <span class="legenda-item">faixa escura no topo = noite</span>
   <span class="legenda-item">PM/BM = estofa (preia-mar/baixa-mar)</span>
   <span class="legenda-item">▼ chegada · ▲ partida (marcador de navio)</span>
  </div>
 </div>
 {seccao_mares}
</section>

<section aria-labelledby="nav-titulo">
 <h2 id="nav-titulo">Navios (ETA/ETD da APL) na janela prevista</h2>
 {chips_filtro_html}
 {''.join(cartoes)}
</section>

<section aria-labelledby="porto-titulo">
 <h2 id="porto-titulo">Em porto agora ({len(em_porto)})</h2>
 {seccao_porto}
</section>

<section aria-labelledby="regras-titulo">
 <h2 id="regras-titulo">Regras em vigor</h2>
 <div class="scroll">
 <table><thead><tr><th>Regra</th><th>Sentido</th><th>Âmbar</th>
 <th>Vermelho</th><th>Fonte</th></tr></thead>
 <tbody>{linhas_regras}</tbody></table>
 </div>
 <ul>{notas}</ul>
</section>
</main>

<footer>Nível do mar: modelo Open-Meteo (não são as tabelas oficiais do
Instituto Hidrográfico). Dados APL © Administração do Porto de Lisboa.
Projeto pessoal, código aberto.</footer>
{JS_PAINEL}
</body></html>"""


# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description="Janelas da Barra")
    p.add_argument("--sem-apl", action="store_true",
                   help="saltar consulta à API APL (só meteo-mar)")
    p.add_argument("--horas", type=int, default=72,
                   help="horizonte de previsão em horas (defeito 72)")
    args = p.parse_args()

    regras = carregar_regras()
    print("[meteo] Open-Meteo Marine + vento …")
    try:
        previsao = recolher_meteomar(regras, args.horas)
    except Exception as exc:
        print(f"[meteo] ERRO: {exc}")
        sys.exit(1)
    avaliacoes = [avaliar_hora(h, regras) for h in previsao]

    apl = {} if args.sem_apl else recolher_apl(args.horas)
    navios = extrair_navios(apl)
    print(f"[navios] {len(navios)} extraídos da API APL")

    SAIDA.write_text(gerar_html(previsao, avaliacoes, navios, apl, regras),
                     encoding="utf-8")
    print(f"[OK] Painel: {SAIDA}")


if __name__ == "__main__":
    main()
