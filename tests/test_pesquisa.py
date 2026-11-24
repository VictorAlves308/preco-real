from datetime import date

from precos.config import Config, ConfigIA, Item
from precos.estado import Estado
from precos.ia import Resposta
from precos.pesquisa import Pesquisador

HOJE = date(2026, 11, 24)
ITEM = Item(nome="Air fryer", url="", tipo="busca", pesquisa="economica", descricao="air fryer boa até 500")
COMPLETO = Item(nome="Air fryer", url="", tipo="busca", pesquisa="completa", descricao="air fryer boa")


class FakeIA:
    def __init__(self, respostas, custo=0.01):
        self.respostas = list(respostas)
        self.chamadas = []
        self.custo = custo

    def gerar(self, sistema, prompt, web=False):
        self.chamadas.append((sistema, prompt, web))
        return Resposta(self.respostas.pop(0), self.custo)


def _pesq(tmp_path, eco=None, comp=None, limite=5.0, avisos=None):
    cfg = Config(itens=[], ia=ConfigIA(provedor="claude", limite_gasto_mensal=limite))
    return Pesquisador(cfg, Estado(tmp_path / "e.db"), {"economica": eco, "completa": comp},
                       hoje=HOJE, notificar=(avisos.append if avisos is not None else None))


def test_estado_cache_e_gastos(tmp_path):
    e = Estado(tmp_path / "e.db")
    assert e.cache_ler("k") is None
    e.cache_gravar("k", "v")
    assert e.cache_ler("k") == "v"
    e.somar_gasto("2026-11", 0.5)
    e.somar_gasto("2026-11", 0.25)
    assert e.gasto("2026-11") == 0.75
    assert e.gasto("2026-12") == 0.0


def test_buscas_para_gera_urls_e_cacheia(tmp_path):
    ia = FakeIA(['Aqui: ["air fryer mondial", "air fryer philco 4l"]'])
    p = _pesq(tmp_path, eco=ia)
    urls = p.buscas_para(ITEM)
    assert urls == ["https://www.zoom.com.br/search?q=air%20fryer%20mondial",
                    "https://www.zoom.com.br/search?q=air%20fryer%20philco%204l"]
    assert p.buscas_para(ITEM) == urls
    assert len(ia.chamadas) == 1


def test_filtrar_usa_cache(tmp_path):
    ia = FakeIA(['[{"i": 1, "ok": true, "motivo": "boa"}, {"i": 2, "ok": false, "motivo": "ruim"}]',
                 '[{"i": 1, "ok": true, "motivo": "nova"}]'])
    p = _pesq(tmp_path, eco=ia)
    r = p.filtrar(ITEM, ["Mondial AF-30", "Genérica X"])
    assert r == {"Mondial AF-30": (True, "boa"), "Genérica X": (False, "ruim")}
    r2 = p.filtrar(ITEM, ["Mondial AF-30", "Philco PFR15"])
    assert r2["Mondial AF-30"] == (True, "boa")
    assert r2["Philco PFR15"] == (True, "nova")
    assert len(ia.chamadas) == 2
    assert "Mondial AF-30" not in ia.chamadas[1][1]


def test_filtrar_json_invalido_aprova(tmp_path):
    p = _pesq(tmp_path, eco=FakeIA(["não sei"]))
    assert p.filtrar(ITEM, ["A"]) == {"A": (True, "")}


def test_sem_orcamento_aprova_tudo_e_avisa_uma_vez(tmp_path):
    ia = FakeIA([])
    avisos = []
    p = _pesq(tmp_path, eco=ia, limite=0, avisos=avisos)
    assert p.filtrar(ITEM, ["A", "B"]) == {"A": (True, ""), "B": (True, "")}
    assert p.buscas_para(ITEM) == []
    assert ia.chamadas == []
    assert len(avisos) == 1
    _pesq(tmp_path, eco=ia, limite=0, avisos=avisos).filtrar(ITEM, ["C"])
    assert len(avisos) == 1


def test_gasto_e_registrado(tmp_path):
    p = _pesq(tmp_path, eco=FakeIA(['[{"i": 1, "ok": true, "motivo": ""}]'], custo=0.3))
    p.filtrar(ITEM, ["A"])
    assert p.estado.gasto("2026-11") == 0.3


def test_avaliar_veto_e_cache(tmp_path):
    ia = FakeIA(['{"nota": 3, "resumo": "queima a resistência fácil", "veto": true}'])
    p = _pesq(tmp_path, comp=ia)
    assert p.avaliar(COMPLETO, "Genérica X") == (3, "queima a resistência fácil", True)
    assert p.avaliar(COMPLETO, "Genérica X") == (3, "queima a resistência fácil", True)
    assert len(ia.chamadas) == 1
    assert ia.chamadas[0][2] is True  # usa busca na web


def test_avaliar_so_no_completo(tmp_path):
    ia = FakeIA([])
    assert _pesq(tmp_path, comp=ia).avaliar(ITEM, "X") is None
    assert ia.chamadas == []


def test_ia_falha_nao_derruba(tmp_path):
    class Quebra:
        def gerar(self, *a, **k):
            raise RuntimeError("401")
    p = _pesq(tmp_path, eco=Quebra())
    assert p.filtrar(ITEM, ["A"]) == {"A": (True, "")}
