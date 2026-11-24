import tomllib

import pytest

from precos.cadastro import Api, form_de_item, html_cadastro, item_do_form, para_toml
from precos.config import carregar, url_busca


def test_url_busca():
    assert url_busca("ryzen 7 5700x") == "https://www.zoom.com.br/search?q=ryzen%207%205700x"


def test_carregar_item_com_buscas(tmp_path):
    c = tmp_path / "c.toml"
    c.write_text('[[itens]]\nnome = "CPU"\nbuscas = ["ryzen 7 5700x", "5700x box"]\n', encoding="utf-8")
    item = carregar(c, tmp_path / "s.toml").itens[0]
    assert item.tipo == "busca"
    assert item.url == url_busca("ryzen 7 5700x")
    assert item.urls == [url_busca("5700x box")]


def test_para_toml_ida_e_volta():
    dados = {
        "aparencia": {"tema": "escuro"},
        "ia": {"provedor": "claude", "limite_gasto_mensal": 5.0},
        "itens": [
            {"nome": 'TV "boa"', "buscas": ["smart tv 32"], "limite_total": 1500.0, "polegadas_min": 32},
            {"nome": "Ação ç", "url": "https://www.zoom.com.br/x", "tipo": "produto"},
        ],
    }
    assert tomllib.loads(para_toml(dados)) == dados


def test_item_do_form_valida():
    with pytest.raises(ValueError, match="nome"):
        item_do_form({"nome": " ", "buscas": "x"})
    with pytest.raises(ValueError, match="buscar"):
        item_do_form({"nome": "CPU", "buscas": ""})
    with pytest.raises(ValueError, match="preço"):
        item_do_form({"nome": "CPU", "buscas": "x", "limite_total": "abc"})


def test_item_do_form_converte():
    it = item_do_form({"nome": "TV", "buscas": "smart tv 32, smart tv 40", "limite_total": "1.500,00",
                       "modo": "promocao", "ordem": "parcelas", "pesquisa": "nenhuma",
                       "marcas": "Samsung, LG", "polegadas_min": "32", "polegadas_max": "40",
                       "hz_min": "", "exigir_palavras": True})
    assert it == {"nome": "TV", "buscas": ["smart tv 32", "smart tv 40"], "limite_total": 1500.0,
                  "modo": "promocao", "ordem": "parcelas", "marcas": ["Samsung", "LG"],
                  "exigir": ["smart", "tv", "32"], "polegadas_min": 32.0, "polegadas_max": 40.0}


def test_form_de_item_deriva_termos_do_link():
    f = form_de_item({"nome": "Monitor", "url": url_busca("monitor 144hz"), "urls": [url_busca("monitor aoc")]})
    assert f["buscas"] == "monitor 144hz, monitor aoc"
    f = form_de_item({"nome": "CPU", "url": "https://www.zoom.com.br/processador/x", "tipo": "produto"})
    assert f["buscas"] == "" and f["produto_fixo"] is True


def test_item_de_produto_fixo_mantem_link_se_busca_vazia():
    antigo = {"nome": "CPU", "url": "https://www.zoom.com.br/processador/x", "tipo": "produto", "modo": "mais_barato"}
    it = item_do_form({"nome": "CPU", "buscas": "", "modo": "mais_barato"}, antigo)
    assert it["url"] == antigo["url"] and it["tipo"] == "produto"


def _api(tmp_path):
    (tmp_path / "config.toml").write_text("", encoding="utf-8")
    (tmp_path / "segredos.toml").write_text('cep = "00000-000"\nanthropic_api_key = "sk-velha"\n', encoding="utf-8")
    return Api(tmp_path / "config.toml", tmp_path / "segredos.toml")


def test_api_salvar_editar_excluir(tmp_path):
    api = _api(tmp_path)
    r = api.salvar_item({"nome": "CPU", "buscas": "ryzen 7 5700x", "modo": "mais_barato"}, None)
    assert r["ok"] and len(r["dados"]["itens"]) == 1
    r = api.salvar_item({"nome": "CPU 2", "buscas": "ryzen 7 5700x", "modo": "mais_barato"}, 0)
    assert r["dados"]["itens"][0]["nome"] == "CPU 2"
    assert carregar(tmp_path / "config.toml", tmp_path / "x").itens[0].nome == "CPU 2"
    assert api.salvar_item({"nome": "", "buscas": "x"}, None) == {"ok": False, "erro": "Dê um nome ao produto."}
    assert api.excluir_item(0)["dados"]["itens"] == []


def test_api_config_geral_nao_vaza_nem_apaga_chave(tmp_path):
    api = _api(tmp_path)
    d = api.dados()
    assert "sk-velha" not in str(d)
    assert d["geral"]["tem_chave_claude"] is True
    api.salvar_geral({"ntfy_topico": "precos-abc", "provedor": "claude", "chave": "", "limite_gasto_mensal": "3",
                      "tema": "claro"})
    seg = tomllib.loads((tmp_path / "segredos.toml").read_text(encoding="utf-8"))
    assert seg == {"cep": "00000-000", "anthropic_api_key": "sk-velha", "ntfy_topico": "precos-abc"}
    cfg = carregar(tmp_path / "config.toml", tmp_path / "segredos.toml")
    assert cfg.ia.provedor == "claude" and cfg.ia.limite_gasto_mensal == 3.0 and cfg.tema == "claro"


def test_html_cadastro():
    html = html_cadastro()
    for trecho in ('data-aba="produtos"', 'data-aba="config"', 'id="f-buscas"', 'id="verificar"',
                   'aria-label="Tema escuro"'):
        assert trecho in html
