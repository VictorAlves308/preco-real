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
