#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste offline — sem rede, sem dependências. Corre: python teste_offline.py
Obrigatório antes de commits que toquem no motor de regras, parser ou HTML."""

from datetime import datetime, timedelta

import janelas_barra as jb

REGRAS = {
    "canal": {"profundidade_zh": 15.0},
    "ukc": {"folga_minima_pct": 0.15, "folga_ambar_pct": 0.30},
    "regra": [
        {"parametro": "swell_altura", "descricao": "Swell", "ambar": 2.0,
         "vermelho": 3.0, "fonte": "PLACEHOLDER"},
        {"parametro": "vento_kn", "descricao": "Vento do quadrante N",
         "ambar": 16.0, "vermelho": 25.0, "dir_min": 300.0, "dir_max": 60.0,
         "fonte": "PLACEHOLDER"},
    ],
}


def previsao_fixa() -> list[dict]:
    """12 horas sintéticas: 0–5 verdes, 6–11 âmbar (swell 2.5 ≥ 2.0);
    nível do mar sinusoidal com PM em 02h/10h (+1.0) e BM em 06h (−1.0)."""
    niveis = [0.0, 0.6, 1.0, 0.6, 0.0, -0.6, -1.0, -0.6, 0.0, 0.6, 1.0, 0.6]
    return [{
        "tempo": f"2026-07-18T{i:02d}:00",
        "onda_altura": 1.0, "onda_dir": 300.0, "onda_periodo": 8.0,
        "swell_altura": 0.8 if i < 6 else 2.5,
        "swell_dir": 315.0, "swell_periodo": 12.0,
        "nivel_mar": niveis[i],
        "vento_kn": 10.0, "rajada_kn": 14.0, "vento_dir": 350.0,
    } for i in range(12)]


def teste_avaliar_hora_basico():
    prev = previsao_fixa()
    assert jb.avaliar_hora(prev[0], REGRAS)[0] == 0
    estado, motivos = jb.avaliar_hora(prev[6], REGRAS)
    assert estado == 1 and any("Swell" in m for m in motivos), motivos


def teste_setor_circular():
    # 350° cai no sector 300–060 que cruza o Norte
    hora = dict(previsao_fixa()[0], vento_kn=20.0, vento_dir=350.0)
    estado, motivos = jb.avaliar_hora(hora, REGRAS)
    assert estado == 1, f"vento 350° devia cair no sector 300–060 ({motivos})"
    hora_sul = dict(hora, vento_dir=180.0)
    assert jb.avaliar_hora(hora_sul, REGRAS)[0] == 0


def teste_ukc():
    # profundidade 15.0 + nível 0.5 = 15.5 m de água
    assert jb.avaliar_ukc(8.0, 0.5, REGRAS)[0] == 0    # folga 94 %
    assert jb.avaliar_ukc(12.0, 0.5, REGRAS)[0] == 1   # folga 29 % < 30 %
    assert jb.avaliar_ukc(13.5, 0.5, REGRAS)[0] == 2   # folga 14.8 % < 15 %
    assert jb.avaliar_ukc(None, 0.5, REGRAS) is None


def teste_extrair_navios():
    apl = {"chegadas": {"titulo": "t", "registos": [
        {"navio": "ALFA", "eta": "2026-07-18 10:00:00.0", "ata": "",
         "atd": "", "caladoMaxEntrada": 8.2, "nv_tipoNavio": "Carga",
         "zona": "CAIS X"},
        {"navio": "ALFA", "eta": "2026-07-18 10:00:00.0", "ata": "",
         "atd": "", "caladoMaxEntrada": 8.2},           # duplicado
        {"navio": "BRAVO", "eta": "2026-07-18 12:00:00.0",
         "ata": "2026-07-18 11:50:00.0"},               # já chegou
        {"navio": "CHARLIE", "eta": "data marada", "ata": "",
         "caladoMaxEntrada": "abc"},                    # tolerância a lixo
    ]}}
    navios = jb.extrair_navios(apl)
    assert [n["nome"] for n in navios] == ["ALFA", "CHARLIE"]
    assert navios[0]["calado"] == 8.2
    assert navios[1]["momento"] is None and navios[1]["calado"] is None


def teste_cardeal_seta():
    assert jb.cardeal_seta(315) == ("NW", "↘")   # swell de NW segue para SE
    assert jb.cardeal_seta(0) == ("N", "↓")
    assert jb.cardeal_seta(90) == ("E", "←")
    assert jb.cardeal_seta(None) == ("", "")


def teste_html_timeline_interativa():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    out = jb.gerar_html(prev, avals, [], {}, REGRAS)
    assert "Ferramenta informativa" in out            # aviso obrigatório
    assert 'id="detalhe"' in out
    assert "data-t='2026-07-18T00:00'" in out
    assert "data-estado='ambar'" in out               # horas 6–11
    assert "cel-a" in out                             # contraste no âmbar
    assert "NW↘" in out                               # setas nos data-vals
    assert 'http-equiv="refresh"' in out
    assert "scrollIntoView" in out                    # JS presente


def teste_svg_mare():
    prev = previsao_fixa()
    svg = jb.gerar_svg_mare(prev)
    assert svg.startswith("<svg") and "polyline" in svg
    assert "02h +1.0" in svg and "06h -1.0" in svg     # PM e BM anotadas
    sem_dados = [dict(h, nivel_mar=None) for h in prev]
    assert jb.gerar_svg_mare(sem_dados) == ""
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    assert "<svg" in jb.gerar_html(prev, avals, [], {}, REGRAS)


def teste_filtrar_em_porto():
    agora = datetime(2026, 7, 18, 12, 0)
    registos = [
        {"navio": "DELTA", "ata": "2026-07-17 08:00:00.0", "atd": "",
         "etd": "2026-07-19 10:00:00.0", "nv_tipoNavio": "Carga",
         "zona": "CAIS Y"},
        {"navio": "ECO", "ata": "2020-11-10 14:22:00.0", "atd": ""},   # fóssil
        {"navio": "FOX", "ata": "2026-07-17 09:00:00.0",
         "atd": "2026-07-18 06:00:00.0"},                              # já saiu
        {"navio": "DELTA", "ata": "2026-07-17 08:00:00.0", "atd": ""}, # dup
        {"navio": "GOLF", "ata": "", "atd": ""},                       # sem ATA
    ]
    porto = jb.filtrar_em_porto(registos, agora=agora)
    assert [n["nome"] for n in porto] == ["DELTA"]
    assert porto[0]["etd"] == datetime(2026, 7, 19, 10, 0)


def teste_html_em_porto():
    ata = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S.0")
    apl = {"em_porto": {"titulo": "t", "registos": [
        {"navio": "DELTA", "ata": ata, "atd": "",
         "etd": "2099-01-01 10:00:00.0", "nv_tipoNavio": "Carga",
         "zona": "CAIS Y"}]}}
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    out = jb.gerar_html(prev, avals, [], apl, REGRAS)
    assert "Em porto agora (1)" in out and "DELTA" in out


def teste_dark_mode():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    out = jb.gerar_html(prev, avals, [], {}, REGRAS)
    assert "prefers-color-scheme: dark" in out
    assert out.count('name="theme-color"') == 2


TESTES = [teste_avaliar_hora_basico, teste_setor_circular, teste_ukc,
          teste_extrair_navios, teste_cardeal_seta,
          teste_html_timeline_interativa, teste_svg_mare,
          teste_filtrar_em_porto, teste_html_em_porto, teste_dark_mode]


def main():
    for t in TESTES:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(TESTES)} testes OK")


if __name__ == "__main__":
    main()
