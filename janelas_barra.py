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
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).parent
SAIDA = RAIZ / "index.html"

# API JSON do portal APL (Liferay). Serviços descobertos no JS público das
# páginas "Previsão de chegadas/partidas"; datas em YYYY-MM-DD.
API_APL = "https://www.portodelisboa.pt/api/jsonws/invoke"
SERVICOS_APL = {
    "chegadas": ("Previsão de Chegadas (ETA)", "/apl.processosweb/get-chegadas"),
    "partidas": ("Previsão de Partidas (ETD)", "/apl.processosweb/get-partidas"),
}

ESTADOS = {"verde": 0, "ambar": 1, "vermelho": 2}
ESTADO_NOME = {0: "verde", 1: "ambar", 2: "vermelho"}


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
    vento_kn, rajada_kn, vento_dir."""
    lat = regras["local"]["latitude"]
    lon = regras["local"]["longitude"]
    dias = max(2, min(7, (horas // 24) + 1))

    marine = _get_json(
        "https://marine-api.open-meteo.com/v1/marine"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=wave_height,wave_direction,wave_period,"
        "swell_wave_height,swell_wave_direction,swell_wave_period,"
        "sea_level_height_msl"
        f"&timezone=Europe%2FLisbon&forecast_days={dias}"
    )
    vento = _get_json(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=wind_speed_10m,wind_gusts_10m,wind_direction_10m"
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
        linhas.append({
            "tempo": t,
            "onda_altura": g(hm, "wave_height"),
            "onda_dir": g(hm, "wave_direction"),
            "onda_periodo": g(hm, "wave_period"),
            "swell_altura": g(hm, "swell_wave_height"),
            "swell_dir": g(hm, "swell_wave_direction"),
            "swell_periodo": g(hm, "swell_wave_period"),
            "nivel_mar": g(hm, "sea_level_height_msl"),
            "vento_kn": g(hv, "wind_speed_10m"),
            "rajada_kn": g(hv, "wind_gusts_10m"),
            "vento_dir": g(hv, "wind_direction_10m"),
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
        if val >= r["vermelho"]:
            estado = max(estado, 2)
            motivos.append(f"{r['descricao']}: {val:g} ≥ {r['vermelho']:g}")
        elif val >= r["ambar"]:
            estado = max(estado, 1)
            motivos.append(f"{r['descricao']}: {val:g} ≥ {r['ambar']:g}")
    return estado, motivos


def avaliar_ukc(calado: float, nivel_mar, regras: dict):
    """UKC estático simplificado. nivel_mar da Open-Meteo é relativo ao MSL;
    usamos profundidade ZH + nível como aproximação de altura de água.
    Devolve (estado, texto) ou None se faltar informação."""
    if calado is None or nivel_mar is None:
        return None
    prof = regras["canal"]["profundidade_zh"]
    altura_agua = prof + nivel_mar
    folga = altura_agua - calado
    if calado <= 0:
        return None
    pct = folga / calado
    u = regras["ukc"]
    txt = (f"água ≈{altura_agua:.1f} m, folga {folga:.1f} m "
           f"({pct:.0%} do calado)")
    if pct < u["folga_minima_pct"]:
        return 2, "UKC insuficiente: " + txt
    if pct < u["folga_ambar_pct"]:
        return 1, "UKC marginal: " + txt
    return 0, "UKC ok: " + txt


# ---------------------------------------------------------------------------
# APL (API JSON) + extração de navios
# ---------------------------------------------------------------------------
def recolher_apl(horas: int) -> dict:
    """Consulta a API JSON pública da APL para o horizonte pedido.
    Devolve {chave: {"titulo": ..., "registos": [dict, ...]}}."""
    from datetime import timedelta
    hoje = datetime.now().date()
    fim = hoje + timedelta(days=(horas // 24) + 1)
    params = {"dataIni": hoje.isoformat(), "dataFim": fim.isoformat()}
    out = {}
    for chave, (titulo, servico) in SERVICOS_APL.items():
        print(f"[APL] {titulo} … ", end="", flush=True)
        try:
            corpo = json.dumps({servico: params}).encode()
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
        except Exception as exc:
            print(f"erro: {exc}")
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
                           "zona": (reg.get("zona") or "").strip()})
    return navios


# ---------------------------------------------------------------------------
# Painel HTML (mobile-first)
# ---------------------------------------------------------------------------
COR = {0: "#1E7A5A", 1: "#E2B93B", 2: "#C0392B"}


def gerar_html(previsao, avaliacoes, navios, apl, regras) -> str:
    e = html.escape
    agora = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")

    # --- timeline: uma célula por hora -----------------------------------
    celulas = []
    for hora, (estado, motivos) in zip(previsao, avaliacoes):
        t = hora["tempo"]  # "2026-07-18T14:00"
        dia, hh = t[8:10], t[11:13]
        tip = f"{dia}/{t[5:7]} {hh}h — {ESTADO_NOME[estado]}"
        if motivos:
            tip += " · " + "; ".join(motivos)
        extra = []
        for chave, rot in (("swell_altura", "swell"), ("nivel_mar", "nível"),
                           ("vento_kn", "vento")):
            v = hora.get(chave)
            if v is not None:
                extra.append(f"{rot} {v:g}")
        tip += " · " + ", ".join(extra)
        marca_dia = f"<span class='dia'>{dia}</span>" if hh == "00" else ""
        celulas.append(
            f"<div class='cel' style='background:{COR[estado]}' "
            f"title=\"{e(tip)}\">{marca_dia}<span class='hh'>{hh}</span></div>")

    # --- navios ------------------------------------------------------------
    cartoes = []
    for n in sorted(navios, key=lambda x: (x["momento"] or datetime.max)):
        if n["momento"] is None:
            estado_n, motivos_n = None, ["sem data reconhecida na tabela APL"]
        else:
            alvo = n["momento"].strftime("%Y-%m-%dT%H:00")
            idx = next((i for i, h in enumerate(previsao)
                        if h["tempo"] == alvo), None)
            if idx is None:
                estado_n, motivos_n = None, ["fora do horizonte da previsão"]
            else:
                estado_n, motivos_n = avaliacoes[idx]
                motivos_n = list(motivos_n) or ["condições dentro dos limiares"]
                ukc = avaliar_ukc(n["calado"], previsao[idx]["nivel_mar"],
                                  regras)
                if ukc:
                    estado_n = max(estado_n, ukc[0])
                    motivos_n.append(ukc[1])
                elif n["calado"] is None:
                    motivos_n.append("calado não detetado — UKC não avaliado")
        cor = COR.get(estado_n, "#5C6E7C")
        quando = (n["momento"].strftime("%d/%m %H:%M")
                  if n["momento"] else "—")
        cal = f" · calado {n['calado']:g} m" if n["calado"] else ""
        tipo = f" · {e(n['tipo'])}" if n.get("tipo") else ""
        zona = (f"<div class='nmeta'>{e(n['zona'])}</div>"
                if n.get("zona") else "")
        cartoes.append(f"""
        <div class="navio">
          <span class="farol" style="background:{cor}"></span>
          <div>
            <div class="nnome">{e(n['nome'])}</div>
            <div class="nmeta">{e(n['sentido'])} · {quando}{cal}{tipo}</div>
            {zona}
            <div class="nmot">{e('; '.join(motivos_n))}</div>
          </div>
        </div>""")
    if not cartoes:
        cartoes = ["<p class='vazio'>Sem navios devolvidos pela API da APL "
                   "nesta recolha (corre com APL ativa ou verifica a API)."]

    # --- regras em vigor ----------------------------------------------------
    linhas_regras = "".join(
        f"<tr><td>{e(r['descricao'])}</td>"
        f"<td>≥ {r['ambar']:g}</td><td>≥ {r['vermelho']:g}</td>"
        f"<td class='fonte-{'ph' if 'PLACEHOLDER' in r['fonte'] else 'ok'}'>"
        f"{e(r['fonte'])}</td></tr>"
        for r in regras.get("regra", []))
    notas = "".join(f"<li>{e(x)}</li>" for x in
                    regras.get("notas_regulamentares", {}).get("itens", []))

    return f"""<!DOCTYPE html>
<html lang="pt"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Janelas da Barra · Lisboa</title>
<style>
 :root {{ --tinta:#1B2A38; --agua:#DCEBF1; --papel:#F7F5EF; --mag:#B0257C; }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; background:var(--agua); color:var(--tinta);
        font-family:system-ui,-apple-system,sans-serif; }}
 header {{ padding:16px 16px 8px; }}
 h1 {{ margin:0; font-size:24px; }}
 .sub {{ font-size:12px; color:#5C6E7C; margin-top:4px; }}
 .aviso {{ background:var(--tinta); color:var(--papel); font-size:12px;
          padding:8px 16px; }}
 section {{ background:var(--papel); border:2px solid var(--tinta);
           border-radius:12px; margin:12px; padding:12px; }}
 h2 {{ font-size:16px; margin:0 0 8px; }}
 .timeline {{ display:flex; overflow-x:auto; gap:2px; padding-bottom:6px; }}
 .cel {{ min-width:22px; height:46px; border-radius:4px; position:relative;
        color:#fff; }}
 .cel .hh {{ position:absolute; bottom:2px; left:0; right:0;
            text-align:center; font-size:9px; opacity:.9; }}
 .cel .dia {{ position:absolute; top:2px; left:0; right:0; text-align:center;
             font-size:9px; font-weight:700; }}
 .legenda {{ font-size:11px; color:#5C6E7C; margin-top:6px; }}
 .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%;
        margin:0 3px 0 8px; }}
 .navio {{ display:flex; gap:10px; padding:10px 0;
          border-bottom:1px solid #D7DFE4; }}
 .navio:last-child {{ border-bottom:none; }}
 .farol {{ flex:0 0 12px; height:12px; border-radius:50%; margin-top:4px; }}
 .nnome {{ font-weight:600; font-size:15px; }}
 .nmeta {{ font-size:12px; color:#5C6E7C; }}
 .nmot {{ font-size:12px; margin-top:2px; }}
 table {{ border-collapse:collapse; width:100%; font-size:12px; }}
 th,td {{ border:1px solid #B9C6CF; padding:5px 6px; text-align:left; }}
 th {{ background:var(--tinta); color:var(--papel); }}
 .fonte-ph {{ color:var(--mag); font-weight:600; }}
 .fonte-ok {{ color:#1E7A5A; }}
 ul {{ margin:6px 0 0; padding-left:18px; font-size:12px; }}
 .vazio {{ color:#5C6E7C; font-style:italic; font-size:13px; }}
 footer {{ font-size:11px; color:#5C6E7C; padding:0 16px 20px; }}
</style></head>
<body>
<header>
 <h1>Janelas da Barra — Lisboa</h1>
 <div class="sub">Atualizado: {agora} · APL + Open-Meteo Marine ·
 limiares em regras.toml</div>
</header>
<div class="aviso">⚠ Ferramenta informativa. Não substitui JUP, VTS-Lisboa,
Capitania nem o juízo profissional do piloto. Limiares a magenta são
PLACEHOLDERS por validar.</div>

<section>
 <h2>Próximas {len(celulas)} horas</h2>
 <div class="timeline">{''.join(celulas)}</div>
 <div class="legenda">Toca/paira numa hora para ver os motivos.
  <span class="dot" style="background:{COR[0]}"></span>verde
  <span class="dot" style="background:{COR[1]}"></span>âmbar
  <span class="dot" style="background:{COR[2]}"></span>vermelho</div>
</section>

<section>
 <h2>Navios (ETA/ETD da APL) na janela prevista</h2>
 {''.join(cartoes)}
</section>

<section>
 <h2>Regras em vigor</h2>
 <table><thead><tr><th>Regra</th><th>Âmbar</th><th>Vermelho</th>
 <th>Fonte</th></tr></thead><tbody>{linhas_regras}</tbody></table>
 <ul>{notas}</ul>
</section>

<footer>Nível do mar: modelo Open-Meteo (não são as tabelas oficiais do
Instituto Hidrográfico). Dados APL © Administração do Porto de Lisboa.
Projeto pessoal, código aberto.</footer>
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
