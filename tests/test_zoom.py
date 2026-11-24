from datetime import date

import pytest

from precos.zoom import SemDados, baixar, extrair_estado, parse_busca, parse_produto
from util_html import Resp, SessaoFake, estado, html_de

URL_CPU = "https://www.zoom.com.br/processador/processador-amd-ryzen-7-5700x-3-4ghz-4-6ghz-turbo-am4"


def test_parse_produto_5700x():
    p = parse_produto(estado("zoom_produto_5700x.json"), URL_CPU)
    assert len(p.ofertas) >= 1
    kabum = next(o for o in p.ofertas if o.loja == "KaBuM!")
    assert kabum.preco_vista == 1299.99
    assert kabum.total_parcelado == 1529.4
    assert kabum.parcelas == 10
    assert kabum.sem_juros is True
    assert kabum.marketplace is False
    assert kabum.link == "https://www.zoom.com.br/lead?oid=" + kabum.offer_id
    assert len(p.historico) >= 30
    assert dict(p.historico)[date(2026, 11, 10)] == 929.99


def test_parse_busca_monitor():
    hits = parse_busca(estado("zoom_busca_monitor.json"))
    assert len(hits) == 12
    assert "GS25F14" in hits[0].nome
    assert hits[0].parcelas == 7
    assert hits[0].total_parcelado == 895.44
    assert hits[0].url.startswith("https://www.zoom.com.br/")


def test_extrair_sem_next_data():
    with pytest.raises(SemDados):
        extrair_estado("<html></html>")


def test_extrair_estado_ok():
    est = estado("zoom_produto_5700x.json")
    assert extrair_estado(html_de(est))["offers"] == est["offers"]


def test_fetch_fallback_buscape():
    html = html_de(estado("zoom_produto_5700x.json"))
    s = SessaoFake({"www.zoom.com.br": Resp(403), "www.buscape.com.br": Resp(200, html)})
    assert baixar(URL_CPU, sessao=s) == html
    assert "www.buscape.com.br" in s.urls[1]


def test_fetch_falha_total():
    s = SessaoFake({"www.zoom.com.br": Resp(403), "www.buscape.com.br": Resp(200, "<html>captcha</html>")})
    with pytest.raises(SemDados):
        baixar(URL_CPU, sessao=s)


def test_parse_busca_loja():
    est = {"hits": {"hits": [{"name": "M", "url": "/lead?oid=1", "price": 1, "type": "offer",
                              "merchantName": "Magazine Luiza", "bestOffer": {"merchantName": "X"}},
                             {"name": "P", "url": "/p", "price": 1, "type": "product",
                              "bestOffer": {"merchantName": "KaBuM!"}}]}}
    hits = parse_busca(est)
    assert hits[0].loja == "Magazine Luiza"
    assert hits[1].loja == "KaBuM!"


def test_imagem_do_produto_e_da_busca():
    p = parse_produto(estado("zoom_produto_5700x.json"), URL_CPU)
    assert p.ofertas[0].imagem.startswith("https://image.zst.com.br/")
    hits = parse_busca(estado("zoom_busca_monitor.json"))
    assert hits[0].imagem.startswith("https://")
