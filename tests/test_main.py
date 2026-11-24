import logging

import precos.__main__ as m


def test_erro_vai_para_o_log(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "DADOS", tmp_path)
    def quebra(*a):
        raise TypeError("chave desconhecida: limite")
    monkeypatch.setattr(m, "carregar", quebra)
    assert m.main([]) == 1
    logging.shutdown()
    assert "chave desconhecida: limite" in (tmp_path / "precos.log").read_text(encoding="utf-8")


def test_teste_aviso_mostra_falha(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(m, "DADOS", tmp_path)
    monkeypatch.setattr(m, "carregar", lambda *a: m.Config(itens=[]))
    monkeypatch.setattr(m, "avisar_todos", lambda cfg: (lambda achados: {"janela": True, "ntfy": False, "whatsapp": False}))
    m.main(["--teste-aviso"])
    out = capsys.readouterr().out
    assert "ntfy: FALHOU" in out
    assert "janela: ok" in out
