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
    assert "Menor <b>R$ 679,00</b>" in html


def test_escapa_texto():
    html = html_janela("t", [dict(ITEM, nome="<script>alert(1)</script>")], "00:00")
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html


def test_sparkline():
    svg = sparkline([3.0, 1.0, 2.0], 200, 40)
    assert svg.startswith("<svg") and svg.count(",") >= 3
    assert sparkline([], 200, 40) == ""
    assert sparkline([5.0, 5.0], 200, 40).startswith("<svg")  # linha reta não divide por zero


def test_sparkline_colorido_com_marcadores():
    svg = sparkline([900.0, 700.0, 1000.0, 800.0], 400, 60)
    assert svg.count("<clipPath") == 3          # verde abaixo da mediana, laranja acima, vermelho muito acima
    assert 'class="m-min"' in svg and 'class="m-hoje"' in svg


def test_legenda_do_grafico():
    html = html_janela("t", [ITEM], "00:00")
    assert "Hoje" in html and "Menor" in html and "Mediana" in html


def test_tema_escolhido():
    for tema in ("sistema", "claro", "escuro"):
        assert f'<html lang="pt-BR" data-tema="{tema}">' in html_janela("t", [ITEM], "00:00", tema)
    assert '<html lang="pt-BR" data-tema="sistema">' in html_janela("t", [ITEM], "00:00", "roxo")
    assert 'data-escolha="escuro"' in html_janela("t", [ITEM], "00:00")  # seletor no topo


def test_preferencia_de_tema(tmp_path):
    from precos.janela_web import ler_tema, salvar_tema
    arq = tmp_path / "pref.json"
    assert ler_tema(arq, "claro") == "claro"
    salvar_tema(arq, "escuro")
    assert ler_tema(arq, "claro") == "escuro"
    salvar_tema(arq, "invalido")
    assert ler_tema(arq, "claro") == "escuro"


def test_trecho_muito_alto_vermelho():
    svg = sparkline([1000.0] * 10 + [1300.0], 400, 60)
    assert "var(--muito-alto)" in svg
    assert 'fill="var(--muito-alto)"' in svg  # hoje muito acima: ponto vermelho
    html = html_janela("t", [dict(ITEM, historico=[1000.0] * 10, vista_num=1300.0)], "00:00")
    assert "muito acima do normal" in html and 'class="ponto muito"' in html
