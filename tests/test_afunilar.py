from datetime import date, timedelta

import pytest

from precos.config import Config, Item
from precos.estado import Estado
from precos.regras import extrair_codigo
from precos.rodada import rodar
from util_html import estado as fixture, html_de

HOJE = date(2026, 11, 24)
TV = Item(nome="TV", url="https://www.zoom.com.br/search?q=smart%20tv%2032", tipo="busca", modo="mais_barato",
          polegadas_min=32, polegadas_max=40, marcas=["Samsung", "TCL", "LG"], exigir=["Smart"])


@pytest.mark.parametrize("nome,codigo", [
    ('Monitor LG 24" IPS 144HZ 1MS 24U411B-B.AWZM', "24U411B"),
    ('Smart TV Samsung 32 Polegadas HD UN32H5000, 32"', "UN32H5000"),
    ("Smart TV 32 Polegadas Samsung LED Tizen Wifi HD LS32H5000FGXZD, 32", "LS32H5000FGXZD"),
    ("Monitor LG UltraGear G4 24 polegadas 24G411AB 144Hz OC Tela IPS FHD 24", "24G411AB"),
    ('Smart TV QLED 32" TCL Full HD 32S5K', "32S5K"),
    ("Monitor Gamer Acer 23.8 Polegadas IPS 144Hz Full HD 1ms Freesync", None),
    ("Processador AMD Ryzen 7 5700X, 3.4GHz (4.6GHz Max Turbo), Cache 36MB", "5700X"),
])
def test_extrair_codigo(nome, codigo):
    assert extrair_codigo(nome) == codigo


def test_historico_proprio_guarda_menor_preco_do_dia(tmp_path):
    e = Estado(tmp_path / "e.db")
    e.registrar_observacao("32S5K", HOJE, 1200.0)
    e.registrar_observacao("32S5K", HOJE, 1150.0)
    e.registrar_observacao("32S5K", HOJE, 1300.0)
    e.registrar_observacao("32S5K", HOJE - timedelta(days=1), 1100.0)
    assert e.historico_proprio("32S5K") == [(HOJE - timedelta(days=1), 1100.0), (HOJE, 1150.0)]


def _hit(nome, url, preco=None, tipo="offer", parcelas=10, loja="Magazine Luiza"):
    h = {"name": nome, "url": url, "type": tipo, "price": preco, "merchantName": loja}
    if preco:
        h["installments"] = {"amount_months": parcelas, "price": round(preco / parcelas, 2), "total_value": preco}
    return h


def _pagina(*hits):
    return html_de({"hits": {"hits": list(hits)}})


PRODUTO = "https://www.zoom.com.br/tv/smart-tv-qled-32-tcl-full-hd-32s5k"


def _rodar(paginas, tmp_path, e=None):
    e = e or Estado(tmp_path / "e.db")
    pedidos = []

    def baixar(u):
        pedidos.append(u)
        return paginas[u]

    achados = rodar(Config(itens=[TV]), e, baixar=baixar, avisar=lambda a: None, hoje=HOJE,
                    dormir=lambda s: None, instantaneo=tmp_path / "u.json")
    import json
    cartoes = json.loads((tmp_path / "u.json").read_text(encoding="utf-8"))["itens"]["TV"]
    return achados, cartoes, pedidos, e


def test_anuncio_solto_usa_produto_do_catalogo_na_mesma_pagina(tmp_path):
    paginas = {
        TV.url: _pagina(_hit("Smart TV QLED 32 TCL 32S5K Google TV", "/lead?oid=9", 1149.0),
                        _hit('Smart TV QLED 32" TCL Full HD 32S5K', "/tv/smart-tv-qled-32-tcl-full-hd-32s5k",
                             tipo="product")),
        PRODUTO: html_de(fixture("zoom_produto_5700x.json")),
    }
    _, cartoes, pedidos, _ = _rodar(paginas, tmp_path)
    assert PRODUTO in pedidos
    assert cartoes and cartoes[0]["historico"]  # agora tem histórico (do produto no catálogo)


def test_anuncio_solto_procura_o_codigo_no_catalogo(tmp_path):
    busca_codigo = "https://www.zoom.com.br/search?q=32S5K"
    paginas = {
        TV.url: _pagina(_hit("Smart TV QLED 32 TCL 32S5K Google TV", "/lead?oid=9", 1149.0)),
        busca_codigo: _pagina(_hit('Smart TV QLED 32" TCL Full HD 32S5K', "/tv/smart-tv-qled-32-tcl-full-hd-32s5k",
                                   tipo="product")),
        PRODUTO: html_de(fixture("zoom_produto_5700x.json")),
    }
    _, cartoes, pedidos, e = _rodar(paginas, tmp_path)
    assert busca_codigo in pedidos and PRODUTO in pedidos
    assert e.cache_ler("catalogo:32S5K") == PRODUTO
    assert cartoes[0]["historico"]


def test_codigo_parecido_nao_conta(tmp_path):
    busca_codigo = "https://www.zoom.com.br/search?q=UN32H5000"
    paginas = {
        TV.url: _pagina(_hit("Smart TV Samsung 32 Polegadas HD UN32H5000", "/lead?oid=7", 1155.9)),
        busca_codigo: _pagina(_hit("Smart TV Samsung 32 UN32H5100", "/tv/outro", tipo="product")),
    }
    _, cartoes, pedidos, e = _rodar(paginas, tmp_path)
    assert "https://www.zoom.com.br/tv/outro" not in pedidos
    assert e.cache_ler("catalogo:UN32H5000") == ""
    assert cartoes[0]["veredito"] == "sem_historico"


def test_historico_proprio_da_veredito_ao_anuncio_solto(tmp_path):
    e = Estado(tmp_path / "e.db")
    for d in range(1, 21):
        e.registrar_observacao("UN32H5000", HOJE - timedelta(days=d), 1300.0)
    e.cache_gravar("catalogo:UN32H5000", "")
    paginas = {TV.url: _pagina(_hit("Smart TV Samsung 32 Polegadas HD UN32H5000", "/lead?oid=7", 1150.0))}
    _, cartoes, _, _ = _rodar(paginas, tmp_path, e)
    assert cartoes[0]["veredito"] == "real" and len(cartoes[0]["historico"]) == 20


def test_rodada_guarda_observacao_de_hoje(tmp_path):
    paginas = {TV.url: _pagina(_hit("Smart TV Samsung 32 Polegadas HD UN32H5000", "/lead?oid=7", 1150.0)),
               "https://www.zoom.com.br/search?q=UN32H5000": _pagina()}
    *_, e = _rodar(paginas, tmp_path)
    assert e.historico_proprio("UN32H5000") == [(HOJE, 1150.0)]


def _hit_cat(nome, url, preco=None, tipo="offer", categoria="tv"):
    h = _hit(nome, url, preco, tipo)
    h["categorySeoUrl"] = categoria
    return h


def _pagina_cat(links, *hits):
    est = {"hits": {"hits": list(hits)},
           "pageSEO": {"data": {"semanticLinks": [{"label": l, "link": "https://www.zoom.com.br" + u} for l, u in links]}}}
    return html_de(est)


def test_descobre_categoria_e_filtros_pelo_cadastro(tmp_path):
    cat32 = "https://www.zoom.com.br/tv/tamanho-32-polegadas?sortBy=price_asc"
    cat40 = "https://www.zoom.com.br/tv/tamanho-40-polegadas?sortBy=price_asc"
    paginas = {
        TV.url: _pagina(_hit_cat("Smart TV Samsung 32 Polegadas HD UN32H5000", "/lead?oid=7", 1155.9)),
        "https://www.zoom.com.br/search?q=UN32H5000": _pagina(),
        "https://www.zoom.com.br/tv": _pagina_cat([('32"', "/tv/tamanho-32-polegadas"), ('40"', "/tv/tamanho-40-polegadas"),
                                                   ('55"', "/tv/tamanho-55-polegadas"), ("240 Hz", "/tv/240-hz")]),
        cat32: _pagina_cat([], _hit_cat('Smart TV QLED 32" TCL Full HD 32S5K', "/tv/smart-tv-qled-32-tcl-full-hd-32s5k",
                                        tipo="product")),
        cat40: _pagina_cat([]),
        PRODUTO: html_de(fixture("zoom_produto_5700x.json")),
    }
    _, cartoes, pedidos, e = _rodar(paginas, tmp_path)
    assert cat32 in pedidos and cat40 in pedidos
    assert "https://www.zoom.com.br/tv/tamanho-55-polegadas?sortBy=price_asc" not in pedidos  # fora de 32-40"
    assert PRODUTO in pedidos
    assert any(c["historico"] for c in cartoes)
    # na próxima rodada não precisa descobrir de novo (guardado por 7 dias)
    _, _, pedidos2, _ = _rodar(paginas, tmp_path, e)
    assert "https://www.zoom.com.br/tv" not in pedidos2 and cat32 in pedidos2


def test_monitor_usa_filtro_de_hz():
    from precos.rodada import escolher_filtros
    mon = Item(nome="M", tipo="busca", hz_min=144, polegadas_min=23.8, polegadas_max=27)
    links = [("144 Hz", "/monitor/144-hz"), ("Monitor 27 Polegadas", "/busca/monitor+27+polegadas"), ("75 Hz", "/monitor/75-hz")]
    assert escolher_filtros(mon, "monitor", links) == ["https://www.zoom.com.br/monitor/144-hz?sortBy=price_asc"]
    sem = Item(nome="X", tipo="busca")
    assert escolher_filtros(sem, "processador", []) == ["https://www.zoom.com.br/processador?sortBy=price_asc"]


def test_filtro_do_zoom_dispensa_hz_no_nome(tmp_path):
    from precos.config import Config
    mon = Item(nome="Monitor", url="https://www.zoom.com.br/search?q=monitor%20144hz", tipo="busca",
               modo="mais_barato", hz_min=144, polegadas_min=23.8, polegadas_max=27, marcas=["LG"])
    cat = "https://www.zoom.com.br/monitor/144-hz?sortBy=price_asc"
    paginas = {
        mon.url: _pagina(_hit_cat("Monitor LG 24 IPS 144Hz 24U411B", "/lead?oid=1", 870.0, categoria="monitor")),
        "https://www.zoom.com.br/search?q=24U411B": _pagina(),
        "https://www.zoom.com.br/monitor": _pagina_cat([("144 Hz", "/monitor/144-hz")]),
        cat: _pagina_cat([], _hit_cat('Monitor Gamer IPS 27" Antirreflexo LG Full HD 27G411', "/monitor/lg-27g411",
                                      tipo="product", categoria="monitor")),
        "https://www.zoom.com.br/monitor/lg-27g411": html_de(fixture("zoom_produto_5700x.json")),
    }
    pedidos = []
    rodar(Config(itens=[mon]), Estado(tmp_path / "e.db"), baixar=lambda u: (pedidos.append(u), paginas[u])[1],
          avisar=lambda a: None, hoje=HOJE, dormir=lambda s: None, instantaneo=tmp_path / "u.json")
    assert "https://www.zoom.com.br/monitor/lg-27g411" in pedidos
