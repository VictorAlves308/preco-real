import requests

from precos.avisos import Achado, enviar_ntfy, enviar_whatsapp, formatar, moeda
from precos.config import Config
from precos.zoom import Oferta


def _oferta(loja="KaBuM!", parcelas=10):
    return Oferta("743605209", "Ryzen 7 5700X", loja, 1299.99, 1529.4, parcelas, 152.94, True, False,
                  "https://www.zoom.com.br/lead?oid=743605209")


class Captura:
    def __init__(self, erro=None):
        self.chamadas = []
        self.erro = erro

    def post(self, url, **kw):
        if self.erro:
            raise self.erro
        self.chamadas.append((url, kw))
        return type("R", (), {"status_code": 200})()

    get = post


def test_moeda():
    assert moeda(1529.4) == "R$ 1.529,40"
    assert moeda(679) == "R$ 679,00"


def test_formatar():
    titulo, corpo = formatar([Achado("Ryzen 7 5700X", _oferta(), "sem_historico", [])])
    assert "R$ 1.529,40 em 10x sem juros" in corpo
    assert "PIX R$ 1.299,99" in corpo
    assert "Sem histórico, não confirmado" in corpo
    assert "✅" not in corpo and "⚠️" not in corpo
    assert "Frete: confira na loja" in corpo
    assert "https://www.zoom.com.br/lead?oid=743605209" in corpo
    assert "1" in titulo


def test_formatar_mercado_livre_e_parcelas_longas():
    _, corpo = formatar([Achado("x", _oferta(loja="Mercado Livre", parcelas=18), "real", ["painel não confirmado"])])
    assert "Frete grátis (Meli+)" in corpo
    assert "em 18x (confira sem juros na loja)" in corpo
    assert "Promoção real" in corpo
    assert "painel não confirmado" in corpo


def test_ntfy_payload():
    s = Captura()
    cfg = Config(itens=[], ntfy_topico="t")
    assert enviar_ntfy(cfg, "Titulo", "corpo", "http://link", sessao=s) is True
    url, kw = s.chamadas[0]
    assert url == "https://ntfy.sh"
    assert kw["json"]["topic"] == "t"
    assert kw["json"]["click"] == "http://link"
    assert kw["json"]["message"] == "corpo"


def test_ntfy_falha_nao_derruba():
    cfg = Config(itens=[], ntfy_topico="t")
    assert enviar_ntfy(cfg, "T", "c", None, sessao=Captura(erro=requests.ConnectionError())) is False


def test_ntfy_sem_topico():
    s = Captura()
    assert enviar_ntfy(Config(itens=[]), "T", "c", None, sessao=s) is False
    assert s.chamadas == []


def test_whatsapp_nao_configurado():
    s = Captura()
    assert enviar_whatsapp(Config(itens=[]), "c", sessao=s) is False
    assert s.chamadas == []


def test_dados_janela():
    from precos.avisos import dados_janela
    d = dados_janela([Achado("Ryzen 7 5700X", _oferta(), "real", ["painel não confirmado"])])[0]
    assert d.items() >= {
        "item": "Ryzen 7 5700X", "nome": "Ryzen 7 5700X", "loja": "KaBuM!",
        "preco": "R$ 1.529,40", "parcelas": "Em 10x sem juros", "pix": "PIX R$ 1.299,99",
        "veredito": "real", "rotulo": "Promoção real", "tags": ["Painel não confirmado"],
        "frete": "Frete: confira na loja", "link": "https://www.zoom.com.br/lead?oid=743605209",
    }.items()


def test_janela_monta_um_cartao_por_oferta():
    import tkinter as tk
    from precos.avisos import dados_janela
    from precos import janela
    itens = dados_janela([Achado("A", _oferta(), "real", []), Achado("B", _oferta(), "sem_historico", [])])
    root = tk.Tk()
    root.withdraw()
    try:
        cartoes = janela.construir(root, "2 ofertas", itens, "claro")
        assert len(cartoes) == 2
    finally:
        root.destroy()


def test_dados_janela_resumo_historico():
    from precos.avisos import dados_janela
    a = Achado("x", _oferta(), "real", [], historico=[1000.0] * 20 + [900.0, 1100.0])
    d = dados_janela([a])[0]
    assert d["historico"][-1] == 1100.0
    assert d["minimo"] == "R$ 900,00"
    assert d["mediana"] == "R$ 1.000,00"
    assert dados_janela([Achado("x", _oferta(), "real", [])])[0]["historico"] == []
