from datetime import date, timedelta
from pathlib import Path

from precos.config import carregar
from precos.regras import elegivel, ordenar, passa_filtro_nome, veredito
from precos.zoom import Oferta, parse_busca, parse_produto
from util_html import estado

RAIZ = Path(__file__).resolve().parent.parent
CFG = carregar(RAIZ / "config.exemplo.toml", RAIZ / "nao_existe.toml")
MONITOR = next(i for i in CFG.itens if i.nome == "Monitor 144Hz")
TV = next(i for i in CFG.itens if i.nome == "TV 32-40")
HOJE = date(2026, 11, 24)


def oferta(parcelas=10, total=700.0, vista=650.0, sem_juros=True, marketplace=False, oid="1"):
    return Oferta(oid, "x", "Loja", vista, total, parcelas, None, sem_juros, marketplace, "http://l")


def test_filtro_monitor_ok():
    assert passa_filtro_nome('Monitor LG 24" IPS 144HZ 1MS 24U411B-B.AWZM', MONITOR) == (True, [])


def test_filtro_monitor_portatil():
    ok, _ = passa_filtro_nome("Monitor Portátil Full HD 144hz Gamer 1080p 16.1 Polegadas - Arzopa", MONITOR)
    assert ok is False


def test_filtro_monitor_sem_painel():
    r = passa_filtro_nome("Monitor Gamer Gigabyte GS24F14A 23.8 1080p FHD 144Hz Preto", MONITOR)
    assert r == (True, ["painel não confirmado"])


def test_filtro_marca_fora():
    ok, _ = passa_filtro_nome("Monitor Duex Led 24 144Hz Hdmi Gamer Dx240Zg", MONITOR)
    assert ok is False


def test_filtro_hz_baixo():
    ok, _ = passa_filtro_nome('Monitor LG 24" IPS 75Hz 24MR400', MONITOR)
    assert ok is False


def test_filtro_tv():
    assert passa_filtro_nome('Smart TV 32" LG HD webOS 32LB650BPSA', TV)[0] is True
    assert passa_filtro_nome('Smart TV 50" Samsung 4K', TV)[0] is False


def test_juros_ausente_exclui():
    est = {"hits": {"hits": [{"name": "Monitor LG 24 IPS 144Hz", "url": "/x", "price": 700, "type": "offer"}]}}
    hit = parse_busca(est)[0]
    assert hit.sem_juros is False
    assert elegivel(oferta(parcelas=None), MONITOR) is False
    assert elegivel(oferta(sem_juros=False), MONITOR) is False


def test_marketplace_exclui():
    assert elegivel(oferta(marketplace=True), MONITOR) is False


def test_limite_total():
    assert elegivel(oferta(total=1590.0), TV) is False
    assert elegivel(oferta(total=1499.0), TV) is True


def test_veredito_maquiada_5700x():
    p = parse_produto(estado("zoom_produto_5700x.json"), "u")
    assert veredito(1299.99, p.historico, HOJE) == "maquiada"


def _hist(precos):
    return [(HOJE - timedelta(days=len(precos) - i), p) for i, p in enumerate(precos)]


def test_veredito_real():
    assert veredito(890, _hist([1000] * 30 + [880]), HOJE) == "real"


def test_veredito_normal():
    assert veredito(980, _hist([1000] * 30), HOJE) == "normal"


def test_veredito_sem_historico():
    assert veredito(890, _hist([1000] * 10), HOJE) == "sem_historico"


def test_veredito_ignora_mais_de_90_dias():
    velho = [(HOJE - timedelta(days=200 + i), 100.0) for i in range(30)]
    assert veredito(890, velho, HOJE) == "sem_historico"


def test_ordenar():
    a = oferta(parcelas=8, total=600, oid="a")
    b = oferta(parcelas=10, total=700, oid="b")
    c = oferta(parcelas=10, total=650, oid="c")
    assert [o.offer_id for o in ordenar([a, b, c])] == ["c", "b", "a"]


def test_limite_vista():
    from dataclasses import replace
    item = replace(TV, limite_total=None, limite_vista=1200.0)
    assert elegivel(oferta(vista=1250.0, total=1300.0), item) is False
    assert elegivel(oferta(vista=1199.0, total=1300.0), item) is True


def test_limite_vista_e_cartao_juntos():
    from dataclasses import replace
    item = replace(TV, limite_total=1500.0, limite_vista=1300.0)
    assert elegivel(oferta(vista=1290.0, total=1550.0), item) is False  # estoura o cartão
    assert elegivel(oferta(vista=1350.0, total=1450.0), item) is False  # estoura o à vista
    assert elegivel(oferta(vista=1290.0, total=1450.0), item) is True
