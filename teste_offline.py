#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste offline — sem rede, sem dependências. Corre: python teste_offline.py
Obrigatório antes de commits que toquem no motor de regras, parser ou HTML."""

from datetime import datetime, timedelta

import janelas_barra as jb

REGRAS = {
    "canal": {"profundidade_zh": 15.0},
    "ukc": {"folga_minima_pct": 0.15, "folga_ambar_pct": 0.30,
            "margem_ondulacao_frac": 0.3},
    "estofa": {"janela_min": 45},
    "regra": [
        {"parametro": "swell_altura", "descricao": "Swell", "ambar": 2.0,
         "vermelho": 3.0, "fonte": "PLACEHOLDER"},
        {"parametro": "vento_kn", "descricao": "Vento do quadrante N",
         "ambar": 16.0, "vermelho": 25.0, "dir_min": 300.0, "dir_max": 60.0,
         "fonte": "PLACEHOLDER"},
        {"parametro": "visibilidade_m", "descricao": "Visibilidade",
         "sentido": "abaixo", "ambar": 3704.0, "vermelho": 1852.0,
         "fonte": "PLACEHOLDER"},
    ],
    "regra_navio": [
        {"id": "roro_vento", "tipos": ["ro-ro", "roro", "ro/ro"],
         "parametro": "vento_kn", "vermelho": 20.0,
         "descricao": "RO-RO interdito com vento forte",
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


def teste_ukc_margem_ondulacao():
    # calado 12.0: sem ondulação folga 29% -> ambar (estado 1)
    sem_onda = jb.avaliar_ukc(12.0, 0.5, REGRAS)
    assert sem_onda[0] == 1
    # com Hs alta (3.0 m), margem = 0.3*3.0 = 0.9 m subtraída à folga
    # folga bruta 3.5 m -> folga efetiva 2.6 m / 12.0 = 21.7% -> ainda ambar,
    # mas o texto deve mostrar a margem e a folga reduzida
    com_onda = jb.avaliar_ukc(12.0, 0.5, REGRAS, onda_altura=3.0)
    assert "ondulação" in com_onda[1]
    assert "2.6 m" in com_onda[1]
    # Hs suficientemente alta degrada o estado: calado 13.0 sem ondulação é
    # ambar (folga 19,2%), com Hs=3.0 m passa a vermelho (folga eff. 12,3%)
    assert jb.avaliar_ukc(13.0, 0.5, REGRAS)[0] == 1
    pior = jb.avaliar_ukc(13.0, 0.5, REGRAS, onda_altura=3.0)
    assert pior[0] == 2
    # sem onda_altura, comportamento inalterado (compatibilidade)
    assert jb.avaliar_ukc(8.0, 0.5, REGRAS, onda_altura=None)[0] == 0


def teste_sentido_abaixo():
    # regra "Visibilidade": sentido abaixo, ambar 3704, vermelho 1852
    hora_boa = dict(previsao_fixa()[0], visibilidade_m=8000.0)
    assert jb.avaliar_hora(hora_boa, REGRAS)[0] == 0
    hora_ambar = dict(previsao_fixa()[0], visibilidade_m=3000.0)
    estado, motivos = jb.avaliar_hora(hora_ambar, REGRAS)
    assert estado == 1 and any("Visibilidade" in m for m in motivos)
    hora_vermelho = dict(previsao_fixa()[0], visibilidade_m=1000.0)
    estado, motivos = jb.avaliar_hora(hora_vermelho, REGRAS)
    assert estado == 2 and any("Visibilidade" in m for m in motivos)


def teste_avaliar_navio_tipo():
    hora = dict(previsao_fixa()[0], vento_kn=22.0, rajada_kn=24.0)
    roro = {"tipo": "Navio RO-RO"}
    resultados = jb.avaliar_navio_tipo(roro, hora, REGRAS)
    assert resultados and resultados[0][0] == 2
    contentor = {"tipo": "Porta-Contentores"}
    assert jb.avaliar_navio_tipo(contentor, hora, REGRAS) == []


def teste_detetar_estofas():
    prev = previsao_fixa()  # PM em 02h/10h (+1.0), BM em 06h (-1.0)
    estofas = jb.detetar_estofas(prev, REGRAS)
    tipos_horas = [(es["tipo"], es["tempo"][11:13]) for es in estofas]
    assert ("PM", "02") in tipos_horas
    assert ("BM", "06") in tipos_horas
    assert ("PM", "10") in tipos_horas


def teste_extrair_navios():
    apl = {"chegadas": {"titulo": "t", "registos": [
        {"navio": "ALFA", "eta": "2026-07-18 10:00:00.0", "ata": "",
         "atd": "", "caladoMaxEntrada": 8.2, "nv_tipoNavio": "Carga",
         "zona": "CAIS X", "imo": "9638147"},
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
    assert navios[0]["imo"] == "9638147" and navios[1]["imo"] is None
    assert jb._imo({"imo": "2224596"}) is None       # checksum IMO inválido
    assert jb.link_marinetraffic("ALFA", "9638147").endswith("imo:9638147")
    assert "keyword=WOOYANG%20CLES" in jb.link_marinetraffic(
        "WOOYANG CLES", None)


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
    assert "marinetraffic.com" in out          # nome do navio é link


def teste_resumo_janelas():
    # 12h sintéticas independentes de previsao_fixa: 0-2 ambar, 3-8 verde
    # (6h contínuas, >= JANELA_MIN_HORAS), 9 vermelho, 10-11 verde (só 2h).
    prev = [{"tempo": f"2026-07-18T{i:02d}:00"} for i in range(12)]
    estados = [1, 1, 1, 0, 0, 0, 0, 0, 0, 2, 0, 0]
    avals = [(s, []) for s in estados]
    frases = jb.resumo_janelas(prev, avals, agora=datetime(2026, 7, 18, 0, 0))
    assert any("03h" in f and "6 h" in f and "GO contínua" in f for f in frases), frases
    assert any("NO-GO" in f and "09h" in f for f in frases), frases
    # a partir da hora 9 (vermelho), a janela de 2h remanescente é curta
    # demais para ser anunciada
    frases2 = jb.resumo_janelas(prev, avals, agora=datetime(2026, 7, 18, 9, 0))
    assert not any("GO contínua" in f for f in frases2), frases2


def teste_avaliar_navio():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    estofas = jb.detetar_estofas(prev, REGRAS)
    # hora 6: swell 2.5 (âmbar) + nível -1.0 -> água 14.0 m; calado 14.0 m
    # esgota a folga UKC -> estado agravado para vermelho (NO-GO)
    navio = {"nome": "TESTE", "sentido": "entrada",
             "momento": datetime(2026, 7, 18, 6, 0), "calado": 14.0,
             "tipo": "Carga"}
    estado, motivos, nota, idx = jb.avaliar_navio(navio, prev, avals, REGRAS, estofas)
    assert estado == 2 and idx == 6, (estado, idx)
    assert any("UKC insuficiente" in m for m in motivos), motivos
    # sem data reconhecida
    sem_data = {"nome": "X", "sentido": "entrada", "momento": None, "calado": None}
    assert jb.avaliar_navio(sem_data, prev, avals, REGRAS, estofas)[0] is None
    # fora do horizonte
    fora = {"nome": "Y", "sentido": "entrada",
            "momento": datetime(2099, 1, 1, 0, 0), "calado": None}
    assert jb.avaliar_navio(fora, prev, avals, REGRAS, estofas)[0] is None


def teste_html_marcadores_navios():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    navios = [{"nome": "ALFA", "sentido": "entrada",
              "momento": datetime(2026, 7, 18, 6, 0), "calado": 8.0,
              "tipo": "Carga", "zona": "", "imo": None}]
    out = jb.gerar_html(prev, avals, navios, {}, REGRAS)
    assert 'id="navio-1"' in out
    assert "nm-marca" in out and "data-alvo='navio-1'" in out
    assert 'aria-label="ALFA' in out
    assert "chip-filtro" in out and "aria-pressed" in out


def teste_html_aviso_apl():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    apl = {"_erros": ["chegadas: timeout"]}
    out = jb.gerar_html(prev, avals, [], apl, REGRAS)
    assert "Dados APL indisponíveis" in out
    assert "chegadas: timeout" in out
    out_ok = jb.gerar_html(prev, avals, [], {}, REGRAS)
    assert "Dados APL indisponíveis" not in out_ok


def teste_dark_mode():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    out = jb.gerar_html(prev, avals, [], {}, REGRAS)
    assert "prefers-color-scheme: dark" in out
    assert out.count('name="theme-color"') == 2


TESTES = [teste_avaliar_hora_basico, teste_setor_circular, teste_ukc,
          teste_ukc_margem_ondulacao, teste_sentido_abaixo,
          teste_avaliar_navio_tipo, teste_detetar_estofas,
          teste_extrair_navios, teste_cardeal_seta,
          teste_html_timeline_interativa, teste_svg_mare,
          teste_filtrar_em_porto, teste_html_em_porto,
          teste_resumo_janelas, teste_avaliar_navio,
          teste_html_marcadores_navios, teste_html_aviso_apl,
          teste_dark_mode]


def main():
    for t in TESTES:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(TESTES)} testes OK")


if __name__ == "__main__":
    main()
