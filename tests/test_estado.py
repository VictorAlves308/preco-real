from precos.estado import Estado


def test_dedupe_mesmo_preco(tmp_path):
    e = Estado(tmp_path / "estado.db")
    assert e.ja_avisado("i", "o1", 700) is False
    e.registrar_aviso("i", "o1", 700)
    assert e.ja_avisado("i", "o1", 700) is True
    assert e.ja_avisado("i", "o1", 690) is True
    assert e.ja_avisado("i", "o1", 680) is False
    assert e.ja_avisado("outro", "o1", 700) is False


def test_menor_visto(tmp_path):
    e = Estado(tmp_path / "estado.db")
    assert e.menor_visto("i") is None
    for p in (800, 750, 900):
        e.registrar_preco("i", p)
    assert e.menor_visto("i") == 750


def test_persiste_entre_aberturas(tmp_path):
    Estado(tmp_path / "estado.db").registrar_aviso("i", "o1", 700)
    assert Estado(tmp_path / "estado.db").ja_avisado("i", "o1", 700) is True
