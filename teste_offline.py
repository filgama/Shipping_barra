#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste offline — sem rede, sem dependências. Corre: python teste_offline.py
Obrigatório antes de commits que toquem no motor de regras, parser ou HTML."""

from datetime import datetime, timedelta

import janelas_barra as jb

REGRAS = {
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

# Entrada sintética do catálogo portos.toml (profundidade de referência e
# bbox AIS incluídas — como a de Lisboa), para os testes por-porto.
PORTO_TESTE = {"slug": "teste", "nome": "Testport", "pais": "PT",
               "bandeira": "🏳", "latitude": 38.62, "longitude": -9.38,
               "profundidade_zh": 15.0, "apl": True,
               "ais_bbox": [[[38.35, -9.75], [38.95, -8.85]]]}


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
    # profundidade 15.0 (agora argumento, vinda do catálogo portos.toml)
    # + nível 0.5 = 15.5 m de água
    assert jb.avaliar_ukc(8.0, 0.5, REGRAS, profundidade_zh=15.0)[0] == 0
    assert jb.avaliar_ukc(12.0, 0.5, REGRAS, profundidade_zh=15.0)[0] == 1
    assert jb.avaliar_ukc(13.5, 0.5, REGRAS, profundidade_zh=15.0)[0] == 2
    assert jb.avaliar_ukc(None, 0.5, REGRAS, profundidade_zh=15.0) is None
    # porto sem profundidade no catálogo -> avaliação "sem dados" (âmbar)
    sem_prof = jb.avaliar_ukc(8.0, 0.5, REGRAS)
    assert sem_prof[0] == 1 and "no reference depth" in sem_prof[1]


def teste_ukc_margem_ondulacao():
    # calado 12.0: sem ondulação folga 29% -> ambar (estado 1)
    sem_onda = jb.avaliar_ukc(12.0, 0.5, REGRAS, profundidade_zh=15.0)
    assert sem_onda[0] == 1
    # com Hs alta (3.0 m), margem = 0.3*3.0 = 0.9 m subtraída à folga
    # folga bruta 3.5 m -> folga efetiva 2.6 m / 12.0 = 21.7% -> ainda ambar,
    # mas o texto deve mostrar a margem e a folga reduzida
    com_onda = jb.avaliar_ukc(12.0, 0.5, REGRAS, onda_altura=3.0,
                              profundidade_zh=15.0)
    assert "swell allowance" in com_onda[1]
    assert "2.6 m" in com_onda[1]
    # Hs suficientemente alta degrada o estado: calado 13.0 sem ondulação é
    # ambar (folga 19,2%), com Hs=3.0 m passa a vermelho (folga eff. 12,3%)
    assert jb.avaliar_ukc(13.0, 0.5, REGRAS, profundidade_zh=15.0)[0] == 1
    pior = jb.avaliar_ukc(13.0, 0.5, REGRAS, onda_altura=3.0,
                          profundidade_zh=15.0)
    assert pior[0] == 2
    # sem onda_altura, comportamento inalterado (compatibilidade)
    assert jb.avaliar_ukc(8.0, 0.5, REGRAS, onda_altura=None,
                          profundidade_zh=15.0)[0] == 0


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
    out = jb.gerar_html_porto(PORTO_TESTE, prev, avals, [], {}, REGRAS)
    assert "NOT an operational tool" in out           # aviso obrigatório
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
    assert "<svg" in jb.gerar_html_porto(PORTO_TESTE, prev, avals, [], {}, REGRAS)


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
    out = jb.gerar_html_porto(PORTO_TESTE, prev, avals, [], apl, REGRAS)
    assert "In port now (1)" in out and "DELTA" in out
    assert "marinetraffic.com" in out          # nome do navio é link


def teste_resumo_janelas():
    # 12h sintéticas independentes de previsao_fixa: 0-2 ambar, 3-8 verde
    # (6h contínuas, >= JANELA_MIN_HORAS), 9 vermelho, 10-11 verde (só 2h).
    prev = [{"tempo": f"2026-07-18T{i:02d}:00"} for i in range(12)]
    estados = [1, 1, 1, 0, 0, 0, 0, 0, 0, 2, 0, 0]
    avals = [(s, []) for s in estados]
    frases = jb.resumo_janelas(prev, avals, agora=datetime(2026, 7, 18, 0, 0))
    assert any("03:00" in f and "6 h" in f and "GO window" in f for f in frases), frases
    assert any("NO-GO" in f and "09:00" in f for f in frases), frases
    # a partir da hora 9 (vermelho), a janela de 2h remanescente é curta
    # demais para ser anunciada
    frases2 = jb.resumo_janelas(prev, avals, agora=datetime(2026, 7, 18, 9, 0))
    assert not any("GO window" in f for f in frases2), frases2


def teste_avaliar_navio():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    estofas = jb.detetar_estofas(prev, REGRAS)
    # hora 6: swell 2.5 (âmbar) + nível -1.0 -> água 14.0 m; calado 14.0 m
    # esgota a folga UKC -> estado agravado para vermelho (NO-GO)
    navio = {"nome": "TESTE", "sentido": "entrada",
             "momento": datetime(2026, 7, 18, 6, 0), "calado": 14.0,
             "tipo": "Carga"}
    estado, motivos, nota, idx = jb.avaliar_navio(
        navio, prev, avals, REGRAS, estofas,
        profundidade_zh=PORTO_TESTE["profundidade_zh"])
    assert estado == 2 and idx == 6, (estado, idx)
    assert any("insufficient UKC" in m for m in motivos), motivos
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
    out = jb.gerar_html_porto(PORTO_TESTE, prev, avals, navios, {}, REGRAS)
    assert 'id="navio-1"' in out
    assert "nm-marca" in out and "data-alvo='navio-1'" in out
    assert 'aria-label="ALFA' in out
    assert "chip-filtro" in out and "aria-pressed" in out


def teste_html_aviso_apl():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    apl = {"_erros": ["chegadas: timeout"]}
    out = jb.gerar_html_porto(PORTO_TESTE, prev, avals, [], apl, REGRAS)
    assert "APL data unavailable" in out
    assert "chegadas: timeout" in out
    out_ok = jb.gerar_html_porto(PORTO_TESTE, prev, avals, [], {}, REGRAS)
    assert "APL data unavailable" not in out_ok


def teste_ws_parse_frame():
    # texto curto, não mascarado: "hello"
    buf = bytes([0x81, 5]) + b"hello"
    opcode, payload, resto = jb._ws_parse_frame(buf)
    assert opcode == 0x1 and payload == b"hello" and resto == b""
    # comprimento 16-bit (>=126): payload de 200 bytes
    corpo = b"x" * 200
    buf16 = bytes([0x81, 126]) + (200).to_bytes(2, "big") + corpo
    opcode, payload, resto = jb._ws_parse_frame(buf16)
    assert opcode == 0x1 and payload == corpo and resto == b""
    # frame incompleto (falta payload) -> None
    assert jb._ws_parse_frame(bytes([0x81, 5]) + b"hel") is None
    assert jb._ws_parse_frame(bytes([0x81])) is None
    # ping sem payload
    opcode, payload, resto = jb._ws_parse_frame(bytes([0x89, 0]))
    assert opcode == 0x9 and payload == b"" and resto == b""
    # dois frames concatenados: o resto do primeiro é exatamente o segundo
    dois = bytes([0x81, 2]) + b"ab" + bytes([0x81, 2]) + b"cd"
    opcode, payload, resto = jb._ws_parse_frame(dois)
    assert payload == b"ab"
    opcode2, payload2, resto2 = jb._ws_parse_frame(resto)
    assert payload2 == b"cd" and resto2 == b""


def teste_haversine():
    # 1 grau de latitude ~ 60 MN (tolerância generosa: 55-65 MN)
    d = jb._haversine_mn(38.0, -9.0, 39.0, -9.0)
    assert 55.0 < d < 65.0, d
    # mesma coordenada -> 0
    assert jb._haversine_mn(38.6, -9.4, 38.6, -9.4) == 0.0


def teste_agregar_ais():
    porto = PORTO_TESTE
    mensagens = [
        {"MessageType": "PositionReport",
         "MetaData": {"MMSI": 111, "ShipName": "ALFA",
                      "latitude": 38.62, "longitude": -9.40},
         "Message": {"PositionReport": {"Sog": 12.3, "Cog": 45.0,
                                        "Latitude": 38.62, "Longitude": -9.40}}},
        {"MessageType": "ShipStaticData",
         "MetaData": {"MMSI": 111, "ShipName": "ALFA"},
         "Message": {"ShipStaticData": {
             "ImoNumber": 9638147, "Destination": "LISBOA",
             "MaximumStaticDraught": 8.2,
             "Dimension": {"A": 100, "B": 50, "C": 15, "D": 15}}}},
        # navio mais longe, só posição (sem ficha estática)
        {"MessageType": "PositionReport",
         "MetaData": {"MMSI": 222, "ShipName": "BRAVO",
                      "latitude": 38.90, "longitude": -8.90},
         "Message": {"PositionReport": {"Sog": 5.0, "Cog": 200.0,
                                        "Latitude": 38.90, "Longitude": -8.90}}},
    ]
    navios = jb._agregar_ais(mensagens, porto)
    assert [n["mmsi"] for n in navios] == [111, 222]   # ordenado por distância
    alfa = navios[0]
    assert alfa["nome"] == "ALFA" and alfa["sog"] == 12.3 and alfa["cog"] == 45.0
    assert alfa["imo"] == "9638147" and alfa["destino"] == "LISBOA"
    assert alfa["loa"] == 150 and alfa["boca"] == 30
    assert alfa["distancia_mn"] is not None


def teste_html_ais_ativo():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    ais = {"erro": None, "quando": datetime(2026, 7, 18, 12, 0), "segundos": 60,
           "navios": [{"mmsi": 111, "nome": "ALFA", "sog": 12.3, "cog": 45.0,
                      "imo": "9638147", "destino": "LISBOA",
                      "loa": 200, "boca": 30, "calado": 8.2,
                      "distancia_mn": 3.4}]}
    out = jb.gerar_html_porto(PORTO_TESTE, prev, avals, [], {}, REGRAS, ais=ais)
    assert 'id="ais-titulo"' in out and "Live AIS snapshot" in out
    assert "ALFA" in out and "3.4 NM off the entrance" in out
    assert "SOG 12.3 kn" in out
    assert "LOA >" not in out  # limiar não definido nesta REGRAS de teste
    reg_com_dim = dict(REGRAS, dimensoes={"loa_atracacao_estofa": 150.0})
    out2 = jb.gerar_html_porto(PORTO_TESTE, prev, avals, [], {}, reg_com_dim,
                               ais=ais)
    assert "LOA >150" in out2 and "slack water" in out2


def teste_html_ais_inativo():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    out = jb.gerar_html_porto(PORTO_TESTE, prev, avals, [], {}, REGRAS, ais=None)
    assert "AIS inactive" in out and "AISSTREAM_KEY" in out
    out_erro = jb.gerar_html_porto(PORTO_TESTE, prev, avals, [], {}, REGRAS,
                                   ais={"erro": "timeout", "navios": [],
                                        "quando": datetime.now(), "segundos": 60})
    assert "AIS capture failed" in out_erro and "timeout" in out_erro


def teste_fusao_apl_ais():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    navios = [{"nome": "ALFA", "sentido": "entrada",
              "momento": datetime(2026, 7, 18, 6, 0), "calado": 8.0,
              "tipo": "Carga", "zona": "", "imo": "9638147"}]
    ais = {"erro": None, "quando": datetime.now(), "segundos": 60,
           "navios": [{"mmsi": 111, "nome": "ALFA", "sog": 12.3, "cog": 45.0,
                      "imo": "9638147", "distancia_mn": 3.4}]}
    out = jb.gerar_html_porto(PORTO_TESTE, prev, avals, navios, {}, REGRAS,
                              ais=ais)
    assert "AIS: 3.4 NM off the entrance, SOG 12.3 kn" in out


def teste_html_porto_sem_apl():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    porto_min = {"slug": "rotterdam", "nome": "Rotterdam", "pais": "NL",
                 "bandeira": "🇳🇱", "latitude": 51.98, "longitude": 4.05}
    out = jb.gerar_html_porto(porto_min, prev, avals, [], {}, REGRAS)
    assert "Rotterdam" in out and "Arrivals" not in out
    assert "APL ETA/ETD" not in out and "In port now" not in out
    assert "Live AIS snapshot" not in out
    assert "NOT an operational tool" in out           # banner obrigatório
    assert "All ports" in out                          # link para a landing


def teste_carregar_portos():
    portos = jb.carregar_portos()
    assert len(portos) >= 45
    slugs = [p["slug"] for p in portos]
    assert len(slugs) == len(set(slugs))
    lisboa = next(p for p in portos if p["slug"] == "lisboa")
    assert lisboa.get("apl") is True and lisboa.get("ais_bbox")
    assert all("latitude" in p and "longitude" in p for p in portos)


def teste_html_landing():
    resultados = [
        {"porto": {"slug": "lisboa", "nome": "Lisbon", "pais": "PT",
                   "bandeira": "🇵🇹", "latitude": 38.62, "longitude": -9.38},
         "estado_atual": 0, "proxima_verde": "now", "erro": None},
        {"porto": {"slug": "rotterdam", "nome": "Rotterdam", "pais": "NL",
                   "bandeira": "🇳🇱", "latitude": 51.98, "longitude": 4.05},
         "estado_atual": None, "proxima_verde": None,
         "erro": "timeout Open-Meteo"},
        {"porto": {"slug": "hamburg", "nome": "Hamburg", "pais": "DE",
                   "bandeira": "🇩🇪", "latitude": 53.98, "longitude": 8.65},
         "estado_atual": 1, "proxima_verde": "Sat 14:00", "erro": None},
    ]
    out = jb.gerar_html_landing(resultados, REGRAS)
    assert "Port Approach Windows — Europe" in out
    assert "href='ports/lisboa.html'" in out and "Portugal" in out
    assert "green window: now" in out
    assert "no data this run" in out and "Netherlands" in out
    assert "next green window: Sat 14:00" in out and "Germany" in out
    assert "NOT an operational tool" in out            # banner obrigatório
    assert 'id="filtro"' in out                        # filtro client-side
    # países ordenados por nome EN: Germany < Netherlands < Portugal
    assert out.index("Germany") < out.index("Netherlands") < out.index("Portugal")


def teste_dark_mode():
    prev = previsao_fixa()
    avals = [jb.avaliar_hora(h, REGRAS) for h in prev]
    out = jb.gerar_html_porto(PORTO_TESTE, prev, avals, [], {}, REGRAS)
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
          teste_ws_parse_frame, teste_haversine, teste_agregar_ais,
          teste_html_ais_ativo, teste_html_ais_inativo, teste_fusao_apl_ais,
          teste_carregar_portos, teste_html_porto_sem_apl,
          teste_html_landing, teste_dark_mode]


def main():
    for t in TESTES:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(TESTES)} testes OK")


if __name__ == "__main__":
    main()
