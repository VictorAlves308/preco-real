import copy
from datetime import date

from precos.config import Config, Item
from precos.estado import Estado
from precos.rodada import rodar
from precos.zoom import SemDados
from util_html import estado, html_de

HOJE = date(2026, 11, 24)
URL_CPU = "https://www.zoom.com.br/processador/processador-amd-ryzen-7-5700x-3-4ghz-4-6ghz-turbo-am4"


def _cpu(modo="promocao", nome="Ryzen 7 5700X", url=URL_CPU):
    return Item(nome=nome, url=url, tipo="produto", modo=modo)


def _sem_historico():
    est = copy.deepcopy(estado("zoom_produto_5700x.json"))
    for v in est["priceHistory"]["priceHistory"].values():
        v["days"] = []
    return est


class Avisar:
    def __init__(self):
        self.chamadas = []

    def __call__(self, achados):
        self.chamadas.append(achados)


def _rodar(itens, paginas, tmp_path, avisar):
    def baixar(url):
        r = paginas[url]
        if isinstance(r, Exception):
            raise r
        return r

    return rodar(Config(itens=itens), Estado(tmp_path / "e.db"), baixar=baixar, avisar=avisar,
                 hoje=HOJE, dormir=lambda s: None)


def test_produto_maquiado_nao_avisa(tmp_path):
    av = Avisar()
    achados = _rodar([_cpu()], {URL_CPU: html_de(estado("zoom_produto_5700x.json"))}, tmp_path, av)
    assert achados == []
    assert av.chamadas == []


def test_sem_historico_avisa_uma_vez(tmp_path):
    av = Avisar()
    paginas = {URL_CPU: html_de(_sem_historico())}
    a1 = _rodar([_cpu()], paginas, tmp_path, av)
    assert len(a1) == 1
    assert a1[0].veredito == "sem_historico"
    assert a1[0].oferta.loja == "KaBuM!"
    a2 = _rodar([_cpu()], paginas, tmp_path, av)
    assert a2 == []
    assert len(av.chamadas) == 1


def test_item_com_erro_nao_derruba(tmp_path):
    av = Avisar()
    itens = [_cpu(nome="quebrado", url="https://www.zoom.com.br/q"), _cpu()]
    paginas = {"https://www.zoom.com.br/q": SemDados("403"), URL_CPU: html_de(_sem_historico())}
    achados = _rodar(itens, paginas, tmp_path, av)
    assert [a.item for a in achados] == ["Ryzen 7 5700X"]


def test_sem_ofertas_sem_janela(tmp_path):
    av = Avisar()
    est = _sem_historico()
    for o in est["offers"]["offerList"]:
        o["sellerIsMarketplace"] = True
    _rodar([_cpu()], {URL_CPU: html_de(est)}, tmp_path, av)
    assert av.chamadas == []


def test_busca_monitor_top3(tmp_path):
    av = Avisar()
    url = "https://www.zoom.com.br/search?q=monitor%20144hz"
    item = Item(nome="Monitor", url=url, tipo="busca", modo="mais_barato", polegadas_min=23.8,
                polegadas_max=27, hz_min=144, marcas=["LG", "Philips", "Gigabyte", "ASUS"],
                excluir=["TN", "Portátil"])
    achados = _rodar([item], {url: html_de(estado("zoom_busca_monitor.json"))}, tmp_path, av)
    assert len(achados) == 3
    totais = [a.oferta.total_parcelado for a in achados]
    assert totais == sorted(totais)
    assert all(a.veredito == "sem_historico" for a in achados)
    assert "Duex" not in " ".join(a.oferta.nome for a in achados)


def test_varias_buscas_sem_duplicar(tmp_path):
    av = Avisar()
    u1 = "https://www.zoom.com.br/search?q=a"
    u2 = "https://www.zoom.com.br/search?q=b"
    item = Item(nome="Monitor", url=u1, urls=[u2], tipo="busca", modo="mais_barato", polegadas_min=23.8,
                polegadas_max=27, hz_min=144, marcas=["LG", "Philips", "Gigabyte", "ASUS"])
    html = html_de(estado("zoom_busca_monitor.json"))
    achados = _rodar([item], {u1: html, u2: html}, tmp_path, av)
    ids = [a.oferta.offer_id for a in achados]
    assert len(ids) == 3 and len(set(ids)) == 3
    assert all(a.oferta.loja for a in achados)


def test_nao_avisa_mais_caros_nas_rodadas_seguintes(tmp_path):
    av = Avisar()
    url = "https://www.zoom.com.br/search?q=monitor%20144hz"
    item = Item(nome="Monitor", url=url, tipo="busca", modo="mais_barato", polegadas_min=23.8,
                polegadas_max=27, hz_min=144, marcas=["LG", "Philips", "Gigabyte", "ASUS"])
    paginas = {url: html_de(estado("zoom_busca_monitor.json"))}
    assert len(_rodar([item], paginas, tmp_path, av)) == 3
    assert _rodar([item], paginas, tmp_path, av) == []


def test_avisar_todos_informa_resultado(monkeypatch):
    import precos.rodada as r
    monkeypatch.setattr(r, "abrir_janela", lambda *a: None)
    from precos.avisos import Achado
    from precos.zoom import Oferta
    o = Oferta("1", "n", "l", 1.0, 1.0, 10, 0.1, True, False, "http://x")
    res = r.avisar_todos(Config(itens=[]))([Achado("i", o, "real", [])])
    assert res == {"janela": True, "ntfy": False, "whatsapp": False}


def _item_ordem(ordem, url):
    return Item(nome="Monitor", url=url, tipo="busca", modo="mais_barato", polegadas_min=23.8,
                polegadas_max=27, hz_min=144, marcas=["LG", "Philips", "Gigabyte", "ASUS"], ordem=ordem)


def test_ordem_menor_preco_padrao(tmp_path):
    url = "https://www.zoom.com.br/search?q=m"
    est = estado("zoom_busca_monitor.json")
    achados = _rodar([_item_ordem("menor_preco", url)], {url: html_de(est)}, tmp_path, Avisar())
    assert [a.oferta.total_parcelado for a in achados] == [874.79, 876.82, 895.44]


def test_ordem_parcelas_10x_primeiro(tmp_path):
    url = "https://www.zoom.com.br/search?q=m"
    est = copy.deepcopy(estado("zoom_busca_monitor.json"))
    for h in est["hits"]["hits"]:
        if "Evnia 27" in h["name"]:
            h["installments"] = {"amount_months": 10, "price": 105.39, "total_value": 1053.92}
    achados = _rodar([_item_ordem("parcelas", url)], {url: html_de(est)}, tmp_path, Avisar())
    assert achados[0].oferta.parcelas == 10
    assert "Evnia 27" in achados[0].oferta.nome


class FakePesq:
    def __init__(self, reprovar="", vetar="", buscas=()):
        self.reprovar, self.vetar, self.buscas = reprovar, vetar, list(buscas)

    def buscas_para(self, item):
        return self.buscas

    def filtrar(self, item, nomes):
        return {n: (not (self.reprovar and self.reprovar in n), "motivo") for n in nomes}

    def avaliar(self, item, nome):
        if item.pesquisa != "completa":
            return None
        return (2, "defeito crônico", True) if self.vetar and self.vetar in nome else (8, "bem avaliado", False)


def _monitor(pesquisa, url="https://www.zoom.com.br/search?q=m"):
    return Item(nome="Monitor", url=url, tipo="busca", modo="mais_barato", polegadas_min=23.8,
                polegadas_max=27, hz_min=144, marcas=["LG", "Philips", "Gigabyte", "ASUS"], pesquisa=pesquisa)


def _rodar_ia(itens, paginas, tmp_path, pesq):
    return rodar(Config(itens=itens), Estado(tmp_path / "e.db"), baixar=lambda u: paginas[u],
                 avisar=Avisar(), hoje=HOJE, dormir=lambda s: None, pesquisador=pesq)


def test_ia_descarta_reprovados(tmp_path):
    url = "https://www.zoom.com.br/search?q=m"
    achados = _rodar_ia([_monitor("economica")], {url: html_de(estado("zoom_busca_monitor.json"))},
                        tmp_path, FakePesq(reprovar="LG"))
    assert achados and all("LG" not in a.oferta.nome for a in achados)


def test_ia_nenhuma_nao_filtra(tmp_path):
    url = "https://www.zoom.com.br/search?q=m"
    achados = _rodar_ia([_monitor("nenhuma")], {url: html_de(estado("zoom_busca_monitor.json"))},
                        tmp_path, FakePesq(reprovar="LG"))
    assert any("LG" in a.oferta.nome for a in achados)


def test_ia_completa_pula_vetado_e_mostra_nota(tmp_path):
    url = "https://www.zoom.com.br/search?q=m"
    achados = _rodar_ia([_monitor("completa")], {url: html_de(estado("zoom_busca_monitor.json"))},
                        tmp_path, FakePesq(vetar="LG"))
    assert len(achados) == 3
    assert all("LG" not in a.oferta.nome for a in achados)
    assert all(any("nota 8/10" in t for t in a.tags) for a in achados)


def test_ia_item_so_com_descricao_usa_buscas_da_ia(tmp_path):
    url = "https://www.zoom.com.br/search?q=gerada"
    item = _monitor("economica", url="")
    achados = _rodar_ia([item], {url: html_de(estado("zoom_busca_monitor.json"))},
                        tmp_path, FakePesq(buscas=[url]))
    assert len(achados) == 3


def test_achado_leva_historico_do_produto(tmp_path):
    est = copy.deepcopy(estado("zoom_produto_5700x.json"))
    for o in est["offers"]["offerList"]:
        o["price"] = 800.0  # bem abaixo da mediana: promoção real
        o["totalParceledValue"] = 900.0
    achados = _rodar([_cpu()], {URL_CPU: html_de(est)}, tmp_path, Avisar())
    assert achados[0].veredito == "real"
    assert len(achados[0].historico) >= 30
    assert achados[0].oferta.imagem


def _cpu_com_preco(vista, total):
    est = copy.deepcopy(estado("zoom_produto_5700x.json"))
    for o in est["offers"]["offerList"]:
        o["price"], o["totalParceledValue"] = vista, total
    return html_de(est)


def test_menor_preco_visto_exige_abaixo_da_mediana(tmp_path):
    # mediana dos 90 dias do fixture é 1199,99: 1220 é "normal" mas acima do normal -> não avisa
    assert _rodar([_cpu("mais_barato")], {URL_CPU: _cpu_com_preco(1220.0, 1400.0)}, tmp_path, Avisar()) == []


def test_menor_preco_visto_abaixo_da_mediana_avisa(tmp_path):
    achados = _rodar([_cpu("mais_barato")], {URL_CPU: _cpu_com_preco(1150.0, 1300.0)}, tmp_path, Avisar())
    assert [a.veredito for a in achados] == ["normal"]


def test_rodada_guarda_foto_do_item(tmp_path):
    e = Estado(tmp_path / "e.db")
    rodar(Config(itens=[_cpu()]), e, baixar=lambda u: html_de(_sem_historico()), avisar=Avisar(),
          hoje=HOJE, dormir=lambda s: None)
    assert e.cache_ler("imagem:Ryzen 7 5700X").startswith("https://image.zst.com.br/")


def test_rodada_grava_instantaneo(tmp_path):
    import json
    snap = tmp_path / "ultima.json"
    rodar(Config(itens=[_cpu()]), Estado(tmp_path / "e.db"), baixar=lambda u: html_de(estado("zoom_produto_5700x.json")),
          avisar=Avisar(), hoje=HOJE, dormir=lambda s: None, instantaneo=snap)
    d = json.loads(snap.read_text(encoding="utf-8"))
    cartoes = d["itens"]["Ryzen 7 5700X"]
    assert cartoes and cartoes[0]["preco"] == "R$ 1.529,40"
    assert cartoes[0]["veredito"] == "maquiada"  # aparece no painel mesmo sem gerar aviso
    assert d["quando"]
