#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANELAS DA BARRA — Porto de Lisboa
==================================
Cruza três fontes e gera um painel mobile-first (index.html):

  1. APL (portodelisboa.pt) ........ chegadas (ETA), navios em porto,
                                     partidas (ETD) — Playwright (JS-rendered)
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

PAGINAS_APL = {
    "chegadas": ("Previsão de Chegadas (ETA)",
                 "https://www.portodelisboa.pt/previsao-de-chegadas"),
    "em_porto": ("Navios em Porto",
                 "https://www.portodelisboa.pt/navios-em-porto"),
    "partidas": ("Previsão de Partidas (ETD)",
                 "https://www.portodelisboa.pt/previsao-de-partidas"),
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
        # setor direcional opcional
        if "dir_min" in r:
            dchave = dir_por_parametro.get(r["parametro"])
            d = hora.get(dchave) if dchave else None
            if d is None or not (r["dir_min"] <= d <= r["dir_max"]):
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
# APL (Playwright) + extração de navios
# ---------------------------------------------------------------------------
def recolher_apl() -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[APL] Playwright em falta: pip install playwright "
              "&& playwright install chromium")
        return {}
    out = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(locale="pt-PT")
        for chave, (titulo, url) in PAGINAS_APL.items():
            print(f"[APL] {titulo} … ", end="", flush=True)
            try:
                page.goto(url, timeout=45000, wait_until="networkidle")
                for sel in ("text=Aceitar", "button:has-text('Aceitar')"):
                    try:
                        page.locator(sel).first.click(timeout=1500)
                        break
                    except Exception:
                        pass
                page.wait_for_timeout(2500)
                tabelas = page.eval_on_selector_all(
                    "table",
                    """ts => ts.map(t => [...t.querySelectorAll('tr')].map(tr =>
                        [...tr.querySelectorAll('th,td')].map(c =>
                            c.innerText.trim()))
                        .filter(r => r.some(x => x)))""")
                melhor = max((t for t in tabelas if len(t) >= 2),
                             key=len, default=None)
                if melhor:
                    out[chave] = {"titulo": titulo, "colunas": melhor[0],
                                  "linhas": melhor[1:]}
                    print(f"{len(melhor) - 1} linhas")
                else:
                    print("sem tabela (estrutura mudou?)")
            except Exception as exc:
                print(f"erro: {exc}")
        browser.close()
    return out


RE_DATA = re.compile(r"(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2,4}))?\s+(\d{1,2}):(\d{2})")
RE_NUM = re.compile(r"(\d+[.,]\d+|\d+)")


def _idx_coluna(colunas: list[str], *palavras) -> int | None:
    for i, c in enumerate(colunas):
        cl = c.lower()
        if any(p in cl for p in palavras):
            return i
    return None


def extrair_navios(apl: dict, ano_defeito: int) -> list[dict]:
    """Converte as tabelas APL em navios com nome, momento (ETA/ETD),
    sentido e calado quando detetável. Tolerante a variações de colunas."""
    navios = []
    for chave, sentido in (("chegadas", "entrada"), ("partidas", "saída")):
        bloco = apl.get(chave)
        if not bloco:
            continue
        cols = bloco["colunas"]
        i_nome = _idx_coluna(cols, "navio", "nome", "vessel", "ship")
        i_hora = _idx_coluna(cols, "eta", "etd", "data", "prev", "hora")
        i_cal = _idx_coluna(cols, "calado", "draft", "draught")
        for linha in bloco["linhas"]:
            def cel(i):
                return linha[i] if i is not None and i < len(linha) else ""
            nome = cel(i_nome) or (linha[0] if linha else "?")
            momento = None
            m = RE_DATA.search(cel(i_hora)) or RE_DATA.search(" ".join(linha))
            if m:
                d, mo, a, h, mi = m.groups()
                a = int(a) if a else ano_defeito
                if a < 100:
                    a += 2000
                try:
                    momento = datetime(a, int(mo), int(d), int(h), int(mi))
                except ValueError:
                    pass
            calado = None
            mc = RE_NUM.search(cel(i_cal))
            if mc:
                calado = float(mc.group(1).replace(",", "."))
            navios.append({"nome": nome, "sentido": sentido,
                           "momento": momento, "calado": calado,
                           "linha": linha})
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
        cartoes.append(f"""
        <div class="navio">
          <span class="farol" style="background:{cor}"></span>
          <div>
            <div class="nnome">{e(n['nome'])}</div>
            <div class="nmeta">{e(n['sentido'])} · {quando}{cal}</div>
            <div class="nmot">{e('; '.join(motivos_n))}</div>
          </div>
        </div>""")
    if not cartoes:
        cartoes = ["<p class='vazio'>Sem navios extraídos da APL nesta "
                   "recolha (corre com APL ativa ou verifica o scraping)."]

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
                   help="saltar scraping APL (só meteo-mar)")
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

    apl = {} if args.sem_apl else recolher_apl()
    ano = datetime.now().year
    navios = extrair_navios(apl, ano)
    print(f"[navios] {len(navios)} extraídos das tabelas APL")

    SAIDA.write_text(gerar_html(previsao, avaliacoes, navios, apl, regras),
                     encoding="utf-8")
    print(f"[OK] Painel: {SAIDA}")


if __name__ == "__main__":
    main()
