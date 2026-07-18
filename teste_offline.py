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


TESTES = [teste_avaliar_hora_basico, teste_setor_circular, teste_ukc,
          teste_extrair_navios]


def main():
    for t in TESTES:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(TESTES)} testes OK")


if __name__ == "__main__":
    main()
