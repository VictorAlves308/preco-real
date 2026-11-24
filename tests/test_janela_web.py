from precos.janela_web import html_janela, sparkline

ITEM = {
    "item": "Monitor 144Hz", "nome": 'Monitor AOC 27" IPS', "loja": "KaBuM!", "preco": "R$ 679,00",
    "parcelas": "em 10x sem juros", "pix": "PIX R$ 679,00", "veredito": "real", "rotulo": "Promoção real",
    "tags": ["painel não confirmado"], "frete": "frete: confira na loja", "link": "https://www.zoom.com.br/x",
    "imagem": "https://image.zst.com.br/a.jpg", "historico": [800.0, 760.0, 700.0, 679.0],
    "minimo": "R$ 679,00", "mediana": "R$ 730,00",
}


def test_um_cartao_por_oferta():
    html = html_janela("2 ofertas", [ITEM, dict(ITEM, historico=[], imagem="")], "12:56")
    assert html.count('class="cartao"') == 2
    assert html.count("<svg") == 1  # só quem tem histórico ganha gráfico
    assert "Verificado às 12:56" in html
    assert "mín. R$ 679,00" in html


def test_escapa_texto():
    html = html_janela("t", [dict(ITEM, nome="<script>alert(1)</script>")], "00:00")
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html


def test_sparkline():
    svg = sparkline([3.0, 1.0, 2.0], 200, 40)
    assert svg.startswith("<svg") and svg.count(",") >= 3
    assert sparkline([], 200, 40) == ""
    assert sparkline([5.0, 5.0], 200, 40).startswith("<svg")  # linha reta não divide por zero
